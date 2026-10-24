#!/usr/bin/env python3
"""
Servidor de tiles vectoriales + proxy de geocodificacion para el MBTiles de Peru.

Solo usa la libreria estandar de Python (http.server + sqlite3), por lo que la
imagen es minima y no depende de npm/pip.

Endpoints
---------
  GET /                         pagina de demostracion
  GET /style.json               estilo MapLibre (URLs ajustadas al host actual)
  GET /tiles/{z}/{x}/{y}.pbf    tile vectorial (MVT, gzip)
  GET /tiles/{z}/{x}/{y}.json   tilejson del tile
  GET /data.json                tilejson del conjunto de datos
  GET /glyphs/{font}/{r}.pbf    glifos de texto
  GET /geocode?q=...            autocompletado (proxy a Photon)
  GET /reverse?lat=..&lon=..    geocodificacion inversa (proxy a Photon)
  GET /health                   estado del servicio
"""

import json
import os
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MBTILES_PATH = os.environ.get("MBTILES_PATH", "/data/peru.mbtiles")
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")
PORT = int(os.environ.get("PORT", "8080"))
PHOTON_URL = os.environ.get("PHOTON_URL", "").rstrip("/")
TILES_URL_PATH = os.environ.get("TILES_URL_PATH", "/tiles")
TILE_SIZE = 256

_local = threading.local()


def db():
    """Conexion SQLite (solo lectura) por hilo."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        uri = "file:" + urllib.parse.quote(MBTILES_PATH) + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.execute("PRAGMA query_only=1")
        _local.conn = conn
    return conn


def get_metadata():
    try:
        rows = db().execute("SELECT name, value FROM metadata").fetchall()
        return {k: v for k, v in rows}
    except sqlite3.Error:
        return {}


def tile_bounds(z, x, y):
    n = 2 ** z
    lon1, lat1 = x / n * 360.0 - 180.0, _lat(y / n)
    lon2, lat2 = (x + 1) / n * 360.0 - 180.0, _lat((y + 1) / n)
    return [min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2)]


def _lat(yy):
    import math
    r = math.pi * (1 - 2 * yy)
    return math.degrees(math.atan(math.sinh(r)))


class Handler(BaseHTTPRequestHandler):
    server_version = "PeruTiles/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- helpers
    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _not_found(self, msg="not found"):
        self._json({"error": msg}, 404)

    def _file(self, path, ctype):
        if not os.path.isfile(path):
            return self._not_found("archivo no encontrado: %s" % os.path.basename(path))
        with open(path, "rb") as fh:
            data = fh.read()
        self._send(200, data, ctype, {"Cache-Control": "public, max-age=3600"})

    def base_url(self):
        host = self.headers.get("Host", "localhost:%d" % PORT)
        return "http://%s" % host

    # -------------------------------------------------------------------- GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            return self._file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            if ".." in rel:
                return self._not_found("ruta invalida")
            ctype = "text/plain; charset=utf-8"
            if rel.endswith(".js"):
                ctype = "application/javascript; charset=utf-8"
            elif rel.endswith(".css"):
                ctype = "text/css; charset=utf-8"
            elif rel.endswith(".html"):
                ctype = "text/html; charset=utf-8"
            elif rel.endswith(".json"):
                ctype = "application/json; charset=utf-8"
            elif rel.endswith(".pbf"):
                ctype = "application/x-protobuf"
            return self._file(os.path.join(STATIC_DIR, *rel.split("/")), ctype)

        if path == "/style.json":
            return self._serve_style()

        if path == "/data.json":
            return self._serve_datajson()

        if path == "/health":
            return self._health()

        m = re.fullmatch(r"/tiles/(\d+)/(\d+)/(\d+)\.pbf", path)
        if m:
            return self._serve_tile(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        m = re.fullmatch(r"/tiles/(\d+)/(\d+)/(\d+)\.json", path)
        if m:
            return self._serve_tilejson(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        m = re.fullmatch(r"/glyphs/([^/]+)/(\d+-\d+)\.pbf", path)
        if m:
            font = urllib.parse.unquote(m.group(1))
            rng = m.group(2)
            safe_font = re.sub(r"[^A-Za-z0-9 _-]", "", font)
            return self._file(os.path.join(STATIC_DIR, "glyphs", safe_font, rng + ".pbf"),
                              "application/x-protobuf")

        if path == "/geocode":
            return self._proxy("/api", query)

        if path == "/reverse":
            return self._proxy("/reverse", query)

        self._not_found("ruta desconocida: %s" % path)

    # --------------------------------------------------------------- handlers
    def _serve_tile(self, z, x, y):
        n = 2 ** z
        if not (0 <= z <= 20 and 0 <= x < n and 0 <= y < n):
            return self._not_found("tile fuera de rango")
        # MBTiles guarda las filas en orden TMS: tmsY = 2^z - 1 - y
        tms_y = n - 1 - y
        row = db().execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, tms_y)).fetchone()
        if not row or not row[0]:
            return self._send(204, b"", "application/vnd.mapbox-vector-tile")
        data = row[0]
        self._send(200, data, "application/vnd.mapbox-vector-tile", {
            "Content-Encoding": "gzip",
            "Cache-Control": "public, max-age=86400",
            "ETag": '"%d-%d-%d"' % (z, x, y),
        })

    def _serve_tilejson(self, z, x, y):
        n = 2 ** z
        if not (0 <= z <= 20 and 0 <= x < n and 0 <= y < n):
            return self._not_found("tile fuera de rango")
        self._json({
            "tile": "%s/tiles/%d/%d/%d.pbf" % (self.base_url(), z, x, y),
            "minzoom": z, "maxzoom": z,
            "bounds": tile_bounds(z, x, y),
        })

    def _serve_datajson(self):
        meta = get_metadata()
        bounds = meta.get("bounds")
        out = {
            "tilejson": meta.get("tilejson", "2.2.0"),
            "tiles": ["%s%s/{z}/{x}/{y}.pbf" % (self.base_url(), TILES_URL_PATH)],
            "minzoom": int(meta.get("minzoom", 0)),
            "maxzoom": int(meta.get("maxzoom", 14)),
            "name": meta.get("name", "Peru OSM"),
            "description": meta.get("description", ""),
            "attribution": meta.get("attribution", "<a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>"),
            "format": "pbf",
            "scheme": "xyz",
            "type": "baselayer",
            "vector_layers": json.loads(meta["json"])["vector_layers"] if "json" in meta else [],
        }
        if bounds:
            out["bounds"] = [float(v) for v in bounds.split(",")]
        self._json(out)

    def _serve_style(self):
        path = os.path.join(STATIC_DIR, "style.json")
        if not os.path.isfile(path):
            return self._not_found("style.json no encontrado")
        with open(path, "r", encoding="utf-8") as fh:
            style = json.load(fh)
        base = self.base_url()
        style.setdefault("sources", {})["peru"] = {
            "type": "vector",
            "tiles": ["%s%s/{z}/{x}/{y}.pbf" % (base, TILES_URL_PATH)],
            "minzoom": 0,
            "maxzoom": 14,
            "attribution": "<a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>",
        }
        style["glyphs"] = "%s/glyphs/{fontstack}/{range}.pbf" % base
        self._json(style)

    def _proxy(self, endpoint, query):
        if not PHOTON_URL:
            return self._json({"error": "geocodificador no configurado (PHOTON_URL vacio)"}, 503)
        params = {k: v[0] for k, v in query.items()}
        url = "%s%s?%s" % (PHOTON_URL, endpoint,
                           urllib.parse.urlencode(params))
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            self._send(200, data, "application/json; charset=utf-8",
                       {"Cache-Control": "public, max-age=60"})
        except Exception as exc:  # noqa: BLE001
            self._json(
                {"error": "geocodificador no disponible: %s" % exc}, 502)

    def _health(self):
        info = {"status": "ok", "mbtiles": MBTILES_PATH,
                "photon": PHOTON_URL or None}
        try:
            info["tiles"] = db().execute(
                "SELECT COUNT(*) FROM tiles").fetchone()[0]
            info["zoom_levels"] = [
                r[0] for r in db().execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY 1")]
        except sqlite3.Error as exc:
            info["status"] = "error"
            info["error"] = str(exc)
        if PHOTON_URL:
            try:
                urllib.request.urlopen(
                    PHOTON_URL + "/api?q=test&limit=1", timeout=8).read()
                info["geocoder"] = "up"
            except Exception as exc:  # noqa: BLE001
                info["geocoder"] = "down: %s" % exc
        self._json(info)

    def log_message(self, fmt, *args):
        if os.environ.get("VERBOSE", "0") == "1":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("Servidor de tiles escuchando en 0.0.0.0:%d  (mbtiles=%s)" %
          (PORT, MBTILES_PATH))
    srv.serve_forever()

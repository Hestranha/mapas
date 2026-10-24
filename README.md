# Mapa de Perú: servicio de tiles + geocodificación (Docker)

Servicio autocontenido que convierte el extracto OSM de Perú (`peru-261020.osm.pbf`) en:

1. **Tiles vectoriales (MVT)** servidos por HTTP, con estilo MapLibre propio.
2. **Geocodificación tipo Google** (autocompletado "escribo un lugar → me salen opciones")
   y geocodificación inversa (coordenada → dirección), vía Photon.
3. **Geocodificación inversa y búsqueda** sobre base de datos PostgreSQL/PostGIS (Nominatim).

Todo corre en Docker Compose, sin servicios externos.

---

## Arquitectura

```
                    ┌──────────────────────────────┐
                    │  Nominatim v5.3.3 (import)    │
   peru-261020      │  osm2pgsql + PostgreSQL      │
   .osm.pbf  ─────► │  → placex / address / ...    │
                    └───────────────┬──────────────┘
                                    │ SQL
                    ┌───────────────▼──────────────┐
   photon-data      │  Photon 1.3.0 (OpenSearch)   │
   (índice)  ◄───── │  import-from-nominatim       │
                    │  → /api  /reverse            │
                    └───────────────┬──────────────┘
                                    │ HTTP :2322
   peru.mbtiles ───►┌───────────────▼──────────────┐
   (data/)          │  Servidor de tiles (Python)  │  → http://localhost:8080
                    │  /tiles/{z}/{x}/{y}.pbf       │
                    │  /style.json  /geocode       │
                    └──────────────────────────────┘

  db         PostgreSQL 16 + PostGIS 3.4   (volumen: dbdata)
  photon     Geocodificador                 (volumen: photon-data)
  tileserver Servidor de mapa + proxy       (puerto 8080)
```

| Servicio | Puerto | Función |
|---|---|---|
| `tileserver` | **8080** | Tiles vectoriales, estilo, demo web y proxy del geocodificador |
| `photon` | **2322** | API de geocodificación (Photon) |
| `db` | 5433 → 5432 | PostgreSQL + PostGIS (datos de Nominatim) |

> El puerto 5433 del host es el que publica la base de datos; el 5432 interno del
> contenedor es el estándar de PostgreSQL. Si el 5432 del host está libre, cambia
> `5433:5432` por `5432:5432` en `docker-compose.yml`.

---

## Puesta en marcha

```bash
cd Mapas

# 1) (solo la primera vez) generar los tiles desde el .osm.pbf
docker run --rm -v "$PWD:/data" ubuntu:24.04 bash -c \
  "apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq curl unzip >/dev/null 2>&1 && \
   bash /data/scripts/01-descargar-base.sh /data/external"
bash scripts/02-generar-mbtiles.sh          # ~6-10 min -> data/peru.mbtiles (366 MB)

# 2) Levantar todo (la primera vez importa el OSM en la BD: ~30-60 min)
docker compose up -d --build

# 3) Ver estado
docker compose ps
curl http://localhost:8080/health
```

La primera ejecución hace el import completo del PBF en Nominatim (~15-25 min) y luego
el índice de Photon (~1-2 min). Los contenedores `nominatim-import` y `photon-import`
**detectan si ya está importado y no lo repiten**; para reimportar:

```bash
FORCE_IMPORT=1 docker compose up --force-recreate nominatim-import photon-import
```

Los servicios de importación quedan en estado `Exited (0)` cuando terminan (es lo
esperado: son jobs, no servicios). Para verlos: `docker compose logs -f nominatim-import`.

### Demo web

`http://localhost:8080/` → mapa de Perú con buscador de lugares (autocompletado):

- escribe en el buscador y aparecen sugerencias (mismo motor que Google Maps);
- botones de filtro: **Todo / Ciudades / Barrios / Calles / Direcciones / Lugares (POI)**;
- el resultado se ordena priorizando ciudades, provincias y departamentos por encima
  de calles y POI;
- las sugerencias se priorizan por **cercanía al centro del mapa** (sesgo `lat`/`lon`);
- al hacer clic en el mapa se muestra la **dirección** (geocodificación inversa);
- enlace profundo con la vista: `http://localhost:8080/#-71.9789/-13.5183/12`
  (`#lon/lat/zoom`), se actualiza solo al mover el mapa.

---

## API

### Tiles (MVT)

```
GET http://localhost:8080/tiles/{z}/{x}/{y}.pbf     tile vectorial (gzip)
GET http://localhost:8080/tiles/{z}/{x}/{y}.json    tilejson
GET http://localhost:8080/data.json                tilejson del dataset
GET http://localhost:8080/style.json               estilo MapLibre (URLs dinámicas)
GET http://localhost:8080/glyphs/{font}/{r}.pbf    glifos de texto
```

Esquema XYZ. Para MapLibre GL JS:

```js
const map = new maplibregl.Map({
  container: 'map',
  style: 'http://localhost:8080/style.json',
  center: [-75.0152, -9.19],
  zoom: 5
});
```

### Geocodificación (Photon)

```bash
# autocompletado (como el buscador de Google Maps)
curl "http://localhost:8080/geocode?q=cu&limit=8&lang=es"
# -> {"type":"FeatureCollection","features":[{"geometry":{"coordinates":[-71.9678,-13.532],"type":"Point"},
#     "properties":{"osm_key":"place","osm_value":"city","name":"Cusco",...}}]}

# geocodificacion inversa: coordenada -> direccion
curl "http://localhost:8080/reverse?lat=-12.0464&lon=-77.0428"
```

También disponible directo en `http://localhost:2322/api?q=...` y `/reverse?lat=..&lon=..`.

Photon admite los parámetros: `q`, `limit`, `lang`, `lat`/`lon` (sesgo por cercanía),
`osm_tag` (filtro), `bbox`, `layer`, `dedupe`.

Filtro `layer` (uno o varios, repitiendo el parámetro). Valores admitidos:
`house, street, locality, district, city, county, state, country, other`.

```bash
# solo ciudades, con sesgo de proximidad en Lima
curl "http://localhost:8080/geocode?q=Cusco&layer=city&layer=state&lat=-13.5&lon=-71.9&limit=5"

# solo direcciones (números de casa / POIs con calle)
curl "http://localhost:8080/geocode?q=hospital&osm_tag=amenity&lat=-12.05&lon=-77.04&limit=5"
```

---

## Estructura del proyecto

```
Mapas/
├── peru-261020.osm.pbf        extracto OSM de Perú (Geofabrik, 20-10-2026)
├── docker-compose.yml          definición de los servicios
├── data/
│   ├── peru.mbtiles            tiles vectoriales (generado)
│   └── external/               Natural Earth 10m (ocean + urban areas)
├── tilemaker/
│   ├── config-peru.json        config de capas (esquema OpenMapTiles)
│   └── process-openmaptiles.lua
├── tileserver/
│   ├── Dockerfile
│   ├── server.py               servidor de tiles (solo stdlib)
│   ├── build-style.py          genera static/style.json (expresiones MapLibre válidas)
│   └── static/
│       ├── style.json          estilo MapLibre (generado, no editar a mano)
│       ├── index.html          demo con buscador, filtros y geocodificación inversa
│       ├── maplibre-gl.js/css  librería MapLibre (servida localmente)
│       └── glyphs/             glifos de texto
├── geocoder/
│   ├── nominatim/              imagen con Nominatim v5.3.3 (import OSM -> BD)
│   └── photon/                 imagen con Photon 1.3.0 (BD -> índice de búsqueda)
└── scripts/
    ├── 01-descargar-base.sh    descarga Natural Earth (ocean/urban areas)
    └── 02-generar-mbtiles.sh   genera data/peru.mbtiles con tilemaker
```

### Imágenes

| Imagen | Contenido |
|---|---|
| `mapas-tileserver:1.0.0` | servidor de tiles + demo web (Python stdlib) |
| `mapas-nominatim:5.3.3` | Nominatim 5.3.3 + osm2pgsql (PostgreSQL 16 / PostGIS 3.4) |
| `mapas-photon:1.3.0` | Photon 1.3.0 con OpenSearch embebido (Java 21) |

El estilo se genera con `python tileserver/build-style.py` (o `docker compose build tileserver`),
porque las expresiones de MapLibre no admiten `match` con número impar de argumentos,
varias interpolaciones de zoom en la misma expresión ni data-expressions en
`line-dasharray`. El `style.json` del repositorio es la salida de ese generador.

---

## Actualizar los datos

```bash
# 1) descarga el extracto actual de Perú (~245 MB)
curl -L --retry 10 --retry-all-errors -o peru-latest.osm.pbf \
  https://download.geofabrik.de/south-america/peru-latest.osm.pbf

# 2) regenera los tiles
bash scripts/02-generar-mbtiles.sh

# 3) reimporta en la base de datos y en Photon
FORCE_IMPORT=1 docker compose up --force-recreate nominatim-import photon-import
docker compose restart photon
```

El PBF se monta en el contenedor como `/data/peru-261020.osm.pbf` (ver
`docker-compose.yml`): si descargas una versión nueva, renómbrala o actualiza
`PBF_FILE`. El tile server lee `data/peru.mbtiles` montado en volumen, así que los
tiles nuevos se sirven sin reconstruir la imagen.

Para cambiar el estilo: edita `tileserver/build-style.py`, ejecuta
`python tileserver/build-style.py` y reconstruye (`docker compose build tileserver`).

---

## Despliegue en un VPS

Hay un paquete listo para subir a un servidor con solo terminal:

```bash
bash scripts/03-empaquetar-vps.sh          # Linux/macOS
powershell -ExecutionPolicy Bypass -File scripts\03-empaquetar-vps.ps1   # Windows
```

Genera `dist/vps/` con las 3 imágenes Docker ya construidas (`mapa-imagenes.tar.gz`),
el proyecto y las sumas SHA256. En el VPS:

```bash
scp -r dist/vps/* usuario@TU_VPS:/opt/mapas/
ssh usuario@TU_VPS
cd /opt/mapas/proyecto && sudo bash deploy/vps/iniciar.sh
```

`iniciar.sh` carga las imágenes, ajusta `vm.max_map_count` (necesario para
OpenSearch/Photon) y levanta el stack. Los detalles, requisitos (RAM, disco, sysctl),
HTTPS con Nginx y resolución de problemas están en **[VPS.md](VPS.md)**.

El compose del VPS es un *override* (`docker-compose.vps.yml`) que se fusiona con el
normal: **el stack local no cambia**, solo se aplica en el servidor.

---

## Notas y limitaciones

- **Alcance geográfico**: el geocodificador cubre **solo Perú** (el PBF es el extracto
  peruano). Para buscar en todo el mundo hay que usar un planet.osm.pbf (import de ~2 días)
  o un servicio público (p. ej. `https://photon.komoot.io`).
- **Nombres**: se indexan el nombre principal y las variantes `name:en/es/de/fr`. Los
  nombres alternos que OSM no marca como variantes (`official_name`, `name:it`, …) no
  se indexan: por eso la ciudad de **Cusco** aparece como *Cuzco* (nombre `name` en OSM)
  y "Cusco" devuelve el departamento, la provincia y la ciudad (`Distrito de Cusco`).
- **Costera**: la capa `ocean` usa los polígonos *Natural Earth 10m*, no la coastline exacta
  de OSM (`osmdata.openstreetmap.de` no es accesible desde esta red), por lo que la línea
  de costa puede desviarse some cientos de metros respecto a OSM. Para usar la coastline
  exacta: `WITH_OSM_COASTLINE=1 bash scripts/01-descargar-base.sh` y cambia la capa
  `ocean` de `tilemaker/config-peru.json` para que apunte a `water_polygons.shp`.
- **Zoom**: los tiles se generan de z0 a z14 (sobrezoom hasta z20 en el cliente).
- **Actualizaciones automáticas**: no está configurado el replicado de Geofabrik; hay que
  repetir manualmente el paso de actualización.
- **Puertos expuestos**: 8080 (mapa), 2322 (Photon), 5433 (BD). Para uso en red local
  restringe o quita el mapeo del puerto 5433 en `docker-compose.yml`.

## Créditos

- Datos: © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright) (ODbL).
- Tiles: [tilemaker](https://github.com/systemed/tilemaker) (esquema OpenMapTiles).
- Geocodificador: [Photon](https://github.com/komoot/photon) + [Nominatim](https://nominatim.org).
- Mapa base: [Natural Earth](https://www.naturalearthdata.com) (10m, dominio público).

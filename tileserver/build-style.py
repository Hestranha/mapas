#!/usr/bin/env python3
"""Genera tileserver/static/style.json (estilo MapLibre para el esquema OpenMapTiles).

Las expresiones se construyen con funciones auxiliares que garantizan una sintaxis
valida para MapLibre (p.ej. "match" necesita un numero PAR de argumentos).
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "style.json")

FONT = ["Noto Sans Regular"]


def match(expr, pairs, fallback):
    """['match', expr, label, value, ..., fallback] (numero par de argumentos)."""
    out = ["match", expr]
    for label, value in pairs:
        out += [label, value]
    out.append(fallback)
    return out


def get(field):
    return ["get", field]


def zoom_width(stops):
    """width por zoom: stops = [(z, width), ...]"""
    out = ["interpolate", ["linear"], ["zoom"]]
    for z, w in stops:
        out += [z, w]
    return out


def zoom_size(stops):
    out = ["interpolate", ["linear"], ["zoom"]]
    for z, s in stops:
        out += [z, s]
    return out


def klass(field="class"):
    return get(field)


def fill(layer_id, source_layer, color, opacity=1.0, minzoom=None, outline=None):
    layer = {
        "id": layer_id,
        "type": "fill",
        "source": "peru",
        "source-layer": source_layer,
        "paint": {"fill-color": color, "fill-opacity": opacity},
    }
    if minzoom is not None:
        layer["minzoom"] = minzoom
    if outline:
        layer["paint"]["fill-outline-color"] = outline
    return layer


def line(layer_id, source_layer, color, width, minzoom=None, opacity=1.0, dash=None):
    paint = {"line-color": color, "line-width": width, "line-opacity": opacity}
    if dash:
        paint["line-dasharray"] = dash
    layer = {
        "id": layer_id,
        "type": "line",
        "source": "peru",
        "source-layer": source_layer,
        "paint": paint,
    }
    if minzoom is not None:
        layer["minzoom"] = minzoom
    return layer


def symbol(layer_id, source_layer, layout, paint=None, minzoom=None):
    layer = {
        "id": layer_id,
        "type": "symbol",
        "source": "peru",
        "source-layer": source_layer,
        "layout": layout,
    }
    if minzoom is not None:
        layer["minzoom"] = minzoom
    if paint:
        layer["paint"] = paint
    return layer


style = {
    "version": 8,
    "name": "Perú OSM (OpenMapTiles)",
    "metadata": {
        "openmaptiles:version": "3.15",
        "openmaptiles:layers": [
            "place", "boundary", "poi", "housenumber", "waterway", "transportation",
            "transportation_name", "building", "water", "ocean", "water_name", "aeroway",
            "aerodrome_label", "park", "landuse", "landcover", "mountain_peak",
        ],
    },
    "center": [-75.0152, -9.19],
    "zoom": 5,
    "bearing": 0,
    "pitch": 0,
    "sources": {
        "peru": {
            "type": "vector",
            "tiles": ["/tiles/{z}/{x}/{y}.pbf"],
            "minzoom": 0,
            "maxzoom": 14,
            "attribution": '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }
    },
    "sprite": "",
    "glyphs": "/glyphs/{fontstack}/{range}.pbf",
    "layers": [],
}

L = style["layers"]

# ------------------------------------------------------------------ fondo
L.append({
    "id": "background",
    "type": "background",
    "paint": {"background-color": "#f7f3ef"},
})

# ------------------------------------------------------------------ cobertura de suelo
L.append(fill(
    "landcover", "landcover",
    match(klass(), [
        ("wood", "#cfe0bd"),
        ("grass", "#dfe9c9"),
        ("farmland", "#ece5d2"),
        ("sand", "#f3ecdc"),
        ("wetland", "#d7e6d2"),
        ("rock", "#dedcd6"),
        ("ice", "#eef4f7"),
    ], "#f7f3ef"),
    0.9,
))

# ------------------------------------------------------------------ usos del suelo
L.append(fill(
    "landuse", "landuse",
    match(klass(), [
        ("residential", "#e6e4e1"),
        ("commercial", "#f3e3cc"),
        ("retail", "#f4e0d9"),
        ("industrial", "#e5e0dd"),
        ("hospital", "#f4dde2"),
        ("school", "#eae0ee"),
        ("university", "#eae0ee"),
        ("kindergarten", "#eae0ee"),
        ("cemetery", "#dde4ca"),
        ("military", "#e5e0dd"),
        ("airfield", "#e2e0dc"),
        ("railway", "#e3e0dd"),
        ("quarry", "#dbd9d4"),
        ("farmland", "#ece5d2"),
        ("allotments", "#dbe6c8"),
        ("orchard", "#d9e8c4"),
        ("vineyard", "#dce7c6"),
        ("meadow", "#dfe9c9"),
        ("grass", "#dfe9c9"),
        ("park", "#d9e8c4"),
        ("garden", "#dbe8c8"),
        ("golf_course", "#cfe4c6"),
        ("pitch", "#d6e8c6"),
        ("playground", "#d6e8c6"),
        ("stadium", "#d6e8c6"),
        ("pedestrian", "#eee9e2"),
        ("village_green", "#d9e8c4"),
        ("bus_station", "#e8e4de"),
        ("port", "#c9dbe6"),
        ("beach", "#f3ecdc"),
    ], "#f7f3ef"),
    0.85,
))

# ------------------------------------------------------------------ Areas verdes
L.append(fill(
    "park", "park",
    match(klass(), [
        ("national_park", "#cfe4c4"),
        ("protected_area", "#d6e7c4"),
        ("nature_reserve", "#d6e7c4"),
        ("park", "#d6e7c4"),
        ("garden", "#dbe8c8"),
        ("golf_course", "#cfe4c6"),
        ("picnic_area", "#dbe8c8"),
        ("playground", "#d6e8c6"),
        ("stadium", "#d6e8c6"),
        ("allotments", "#dbe6c8"),
        ("cemetery", "#dde4ca"),
    ], "#dbe8c8"),
    0.9,
))

# ------------------------------------------------------------------ agua
L.append(fill("ocean", "ocean", "#a9c9df"))
L.append(fill(
    "water", "water",
    match(klass(), [
        ("lake", "#a9c9df"),
        ("reservoir", "#a9c9df"),
        ("pond", "#a9c9df"),
        ("river", "#a9c9df"),
        ("swimming_pool", "#a9c9df"),
        ("basin", "#a9c9df"),
    ], "#a9c9df"),
))
L.append(line(
    "waterway", "waterway",
    match(klass(), [
        ("river", "#a9c9df"),
        ("canal", "#a9c9df"),
        ("stream", "#a9c9df"),
        ("drain", "#a9c9df"),
        ("ditch", "#a9c9df"),
    ], "#a9c9df"),
    zoom_width([(8, 0.6), (12, 1.2), (14, 2.5)]),
    minzoom=8,
))

# ------------------------------------------------------------------ edificios
L.append(fill("building", "building", "#ddd8d0", 0.9, minzoom=13))

# ------------------------------------------------------------------ carreteras
ROAD_WIDTHS = [
    ("motorway", 4.0),
    ("trunk", 3.0),
    ("primary", 2.2),
    ("secondary", 1.6),
    ("tertiary", 1.1),
    ("minor", 0.7),
    ("service", 0.5),
    ("path", 0.4),
    ("track", 0.4),
    ("rail", 0.8),
    ("ferry", 0.8),
    ("aeroway", 0.6),
]


def width_by_class(pairs, default, stops=((8, 0.5), (12, 1.0), (16, 1.6))):
    """Un solo interpolate por zoom; dentro, un match por clase (no zoom)."""
    out = ["interpolate", ["linear"], ["zoom"]]
    for z, factor in stops:
        out += [z, match(klass(), [(c, round(w * factor, 2)) for c, w in pairs], round(default * factor, 2))]
    return out


road_width = width_by_class(ROAD_WIDTHS, 0.5)

L.append(line(
    "road_casing", "transportation",
    match(klass(), [
        ("motorway", "#c9c2b8"),
        ("trunk", "#c9c2b8"),
        ("primary", "#d3ccc2"),
        ("secondary", "#d3ccc2"),
        ("tertiary", "#d8d2c9"),
    ], "#ded8cf"),
    road_width,
    minzoom=4,
))
L.append(line(
    "road", "transportation",
    match(klass(), [
        ("motorway", "#f7b267"),
        ("trunk", "#f7b267"),
        ("primary", "#ffffff"),
        ("secondary", "#ffffff"),
        ("tertiary", "#ffffff"),
        ("minor", "#ffffff"),
        ("service", "#f2efe9"),
        ("path", "#c8b9a4"),
        ("track", "#c8b9a4"),
        ("rail", "#b5b1ab"),
        ("ferry", "#8fbcd8"),
        ("aeroway", "#d9d4cc"),
    ], "#f2efe9"),
    road_width,
    minzoom=4,
))

# ------------------------------------------------------------------ limites
L.append(line(
    "boundary", "boundary", "#9e9ac8",
    ["interpolate", ["linear"], ["zoom"], 4, 0.6, 10, 1.4],
    minzoom=4,
    dash=[2, 2],
))

# ------------------------------------------------------------------ nombres
L.append(symbol(
    "place_labels", "place",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"]],
        "text-font": FONT,
        "text-size": match(klass(), [
            ("country", 16),
            ("state", 13),
            ("city", 13),
            ("town", 12),
            ("village", 11),
            ("hamlet", 10),
            ("suburb", 11),
            ("neighbourhood", 10),
            ("locality", 10),
            ("island", 10),
        ], 10),
        "text-transform": "none",
        "text-letter-spacing": 0.1,
    },
    {
        "text-color": "#3a3a3a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.4,
    },
))

L.append(symbol(
    "road_labels", "transportation_name",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"], ["get", "ref"]],
        "text-font": FONT,
        "text-size": zoom_size([(10, 8), (14, 11), (16, 12)]),
        "symbol-placement": "line",
        "symbol-spacing": 300,
    },
    {
        "text-color": "#5b564e",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.2,
    },
    minzoom=10,
))

L.append(symbol(
    "water_name", "water_name",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"]],
        "text-font": FONT,
        "text-size": 11,
    },
    {
        "text-color": "#3d6e91",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.2,
    },
    minzoom=11,
))

L.append(symbol(
    "poi_labels", "poi",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"]],
        "text-font": FONT,
        "text-size": 10,
        "text-anchor": "top",
        "text-offset": [0, 0.6],
    },
    {
        "text-color": "#4a4a4a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.2,
    },
    minzoom=13,
))

L.append(symbol(
    "mountain_peak_labels", "mountain_peak",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"]],
        "text-font": FONT,
        "text-size": 10,
        "text-anchor": "top",
        "text-offset": [0, 0.6],
    },
    {
        "text-color": "#6b5333",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.2,
    },
    minzoom=12,
))

L.append(symbol(
    "aerodrome_labels", "aerodrome_label",
    {
        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"], ["get", "iata"]],
        "text-font": FONT,
        "text-size": 10,
        "text-anchor": "top",
        "text-offset": [0, 0.6],
    },
    {
        "text-color": "#5a5a5a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.2,
    },
    minzoom=11,
))

L.append(symbol(
    "housenumber_labels", "housenumber",
    {
        "text-field": ["get", "housenumber"],
        "text-font": FONT,
        "text-size": 8,
    },
    {
        "text-color": "#8a8a8a",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1,
    },
    minzoom=14,
))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(style, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

print("Escrito %s (%d capas)" % (OUT, len(style["layers"])))

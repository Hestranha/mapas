#!/usr/bin/env bash
# Descarga los datos base (Natural Earth) que usa tilemaker para la capa "ocean" (mar)
# y "urban_areas" (manchas urbanas). Se ejecuta dentro de un contenedor ubuntu.
set -euo pipefail
EXT_DIR="${1:-/data/external}"
mkdir -p "$EXT_DIR"

echo "==> Natural Earth: ocean (10m)"
if [ ! -f "$EXT_DIR/ne_10m_ocean.shp" ]; then
  curl -fsSL -o /tmp/ne_10m_ocean.zip "https://naciscdn.org/naturalearth/10m/physical/ne_10m_ocean.zip"
  unzip -o -j -q /tmp/ne_10m_ocean.zip -d "$EXT_DIR"
fi

echo "==> Natural Earth: urban areas (10m)"
if [ ! -f "$EXT_DIR/ne_10m_urban_areas/ne_10m_urban_areas.shp" ]; then
  mkdir -p "$EXT_DIR/ne_10m_urban_areas"
  curl -fsSL -o /tmp/ne_10m_urban_areas.zip "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_urban_areas.zip"
  unzip -o -q /tmp/ne_10m_urban_areas.zip -d "$EXT_DIR/ne_10m_urban_areas"
fi

echo "==> coastline exacta de OSM (opcional, requiere acceso a osmdata.openstreetmap.de)"
if [ ! -f "$EXT_DIR/water_polygons.shp" ] && [ "${WITH_OSM_COASTLINE:-0}" = "1" ]; then
  curl -fsSL -o /tmp/water_polygons.zip "https://osmdata.openstreetmap.de/download/water-polygons-split-4326.zip"
  unzip -o -j -q /tmp/water_polygons.zip -d "$EXT_DIR"
  echo "    -> water_polygons.shp descargado. Para usarlo cambia la capa 'ocean' del config."
fi

ls -la "$EXT_DIR"
echo "OK"

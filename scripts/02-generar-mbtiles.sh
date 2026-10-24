#!/usr/bin/env bash
# Genera los tiles vectoriales (MBTiles) a partir del .osm.pbf de Peru usando tilemaker.
# Uso:  bash scripts/02-generar-mbtiles.sh [ruta.pbf] [bbox]
#   bbox: minlon,minlat,maxlon,maxlat  (por defecto, Peru + mar circundante)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PBF="${1:-$ROOT/peru-261020.osm.pbf}"
BBOX="${2:--83.2,-19.6,-68.0,1.2}"
OUT="$ROOT/data/peru.mbtiles"

mkdir -p "$ROOT/data"

echo "==> PBF   : $PBF"
echo "==> BBOX  : $BBOX"
echo "==> Salida: $OUT"

docker run --rm \
  -v "$ROOT:/data" \
  ghcr.io/systemed/tilemaker:master \
  --input "/data/$(basename "$PBF")" \
  --output /data/data/peru.mbtiles \
  --config /data/tilemaker/config-peru.json \
  --process /data/tilemaker/process-openmaptiles.lua \
  --bbox "$BBOX" \
  --store /data/data/tmp-tilemaker \
  --threads 0 \
  --verbose

ls -lh "$OUT"
echo "OK"

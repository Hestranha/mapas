#!/usr/bin/env bash
# Empaqueta el proyecto para desplegarlo en un VPS (Linux/macOS).
#
#   bash scripts/03-empaquetar-vps.sh
#
# Genera dist/vps/ con:
#   - mapa-imagenes.tar.gz : las 3 imagenes Docker ya construidas
#   - el proyecto (compose, codigo, PBF y MBTiles) listo para descomprimir en el VPS
#   - SHA256SUMS.txt        :sumas para verificar la copia
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$RAIZ/dist/vps"
IMAGENES=(mapas-nominatim:5.3.3 mapas-photon:1.3.0 mapas-tileserver:1.0.0)

cd "$RAIZ"
echo "==> Comprobando imagenes"
for img in "${IMAGENES[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "ERROR: falta la imagen $img. Construyela con:" >&2
    echo "  docker compose build" >&2
    exit 1
  fi
done

echo "==> Preparando $DIST"
rm -rf "$DIST"
mkdir -p "$DIST/proyecto"

echo "==> Exportando imagenes (docker save) -> ~1.8 GB"
docker save -o "$DIST/mapa-imagenes.tar" "${IMAGENES[@]}"
gzip -f "$DIST/mapa-imagenes.tar"

echo "==> Copiando el proyecto"
mkdir -p "$DIST/proyecto/data" "$DIST/proyecto/geocoder" "$DIST/proyecto/tileserver" \
         "$DIST/proyecto/tilemaker" "$DIST/proyecto/scripts" "$DIST/proyecto/deploy/vps"

cp docker-compose.yml docker-compose.vps.yml VPS.md "$DIST/proyecto/"
cp peru-261020.osm.pbf "$DIST/proyecto/"
cp data/peru.mbtiles "$DIST/proyecto/data/"
cp -r geocoder/. "$DIST/proyecto/geocoder/"
cp -r tileserver/. "$DIST/proyecto/tileserver/"
cp -r tilemaker/. "$DIST/proyecto/tilemaker/"
cp scripts/*.sh "$DIST/proyecto/scripts/"
cp -r deploy/vps/. "$DIST/proyecto/deploy/vps/"

echo "==> Calculando sumas"
( cd "$DIST" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

echo
echo "==> Listo:"
du -sh "$DIST"
echo
echo "Siguiente paso (desde tu PC):"
echo "  scp -r dist/vps/* usuario@TU_VPS:/opt/mapas/"
echo
echo "Y en el VPS:"
echo "  cd /opt/mapas/proyecto && bash deploy/vps/iniciar.sh"

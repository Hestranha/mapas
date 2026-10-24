#!/usr/bin/env bash
# Arranque del stack en el VPS.
#   sudo bash deploy/vps/iniciar.sh
#
# - carga las imagenes si estan en un .tar.gz
# - aplica vm.max_map_count (OpenSearch/Photon no arranca sin esto)
# - levanta el stack (la 1a vez importa el PBF en Nominatim y luego en Photon)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

echo "==> Comprobando Docker"
command -v docker >/dev/null || { echo "ERROR: docker no esta instalado" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || {
  echo "ERROR: falta el plugin 'docker compose' (v2). Instala docker-compose-plugin." >&2; exit 1; }

echo "==> Cargando imagenes (si estan empaquetadas)"
cargar_imagenes() {
  local f="$1" tmp t
  tmp="$(mktemp -d)"
  if tar -xzf "$f" -C "$tmp" 2>/dev/null; then
    t="$(find "$tmp" -name '*.tar' | head -1)"
    if [ -n "$t" ]; then docker load -i "$t"; else gunzip -c "$f" | docker load; fi
  else
    gunzip -c "$f" | docker load
  fi
  rm -rf "$tmp"
}
for t in ../mapa-imagenes.tar.gz ../mapa-imagenes.tar; do
  if [ -f "$t" ]; then
    echo "    cargando $t"
    if [[ "$t" == *.gz ]]; then cargar_imagenes "$t"; else docker load -i "$t"; fi
    break
  fi
done
docker images | grep -E 'mapas-(nominatim|photon|tileserver)' || {
  echo "ERROR: no hay imagenes mapas-*. Si no las subiste, construye con: docker compose build" >&2; exit 1; }

echo "==> Ajustando vm.max_map_count (para OpenSearch/Photon)"
if [ "$(cat /proc/sys/vm/max_map_count)" -lt 262144 ]; then
  cp deploy/vps/99-photon.conf /etc/sysctl.d/99-photon.conf
  sysctl -w vm.max_map_count=262144 >/dev/null
  echo "    vm.max_map_count = $(cat /proc/sys/vm/max_map_count)"
else
  echo "    ya estaba en $(cat /proc/sys/vm/max_map_count)"
fi

echo "==> Levantando el stack"
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d

echo
echo "==> Estado"
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
echo
echo "El geocodificador importa en segundo plano (15-25 min la primera vez):"
echo "  docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f nominatim-import"
echo
echo "Mapa:  http://<IP-DEL-VPS>:8080/"
echo "Health: http://<IP-DEL-VPS>:8080/health"

#!/bin/bash
# Photon: importa desde la base de datos de Nominatim o sirve el indice de busqueda.
set -euo pipefail

PHOTON_JAR="${PHOTON_JAR:-/opt/photon.jar}"
PHOTON_HOST="${PHOTON_HOST:-db}"
PHOTON_PORT_DB="${PHOTON_PORT_DB:-5432}"
PHOTON_DB="${PHOTON_DB:-nominatim}"
PHOTON_USER="${PHOTON_USER:-nominatim}"
PHOTON_PASSWORD="${PHOTON_PASSWORD:-nominatim}"
PHOTON_LISTEN_PORT="${PHOTON_LISTEN_PORT:-2322}"
export OPENSEARCH_JAVA_OPTS="${OPENSEARCH_JAVA_OPTS:--Xms1g -Xmx3g}"

cd "${PHOTON_WORKDIR:-/opt/photon}"
mkdir -p photon_data

# OpenSearch no puede arrancar como root: si somos root, preparamos los permisos
# y seguimos como el usuario 'photon'.
as_photon() {
  if [ "$(id -u)" = "0" ]; then
    chown -R photon:photon /opt/photon /opt/photon_data 2>/dev/null || true
    exec su -s /bin/bash photon -c "$*"
  fi
  exec bash -c "$*"
}

case "${1:-serve}" in
  import)
    if [ "${FORCE_IMPORT:-0}" != "1" ] && [ -f photon_data/.import-ok ]; then
      echo "==> El indice de Photon ya existe: se omite el import"
      echo "==> (usa FORCE_IMPORT=1 para reimportar)"
      exit 0
    fi
    echo "==> Importando la base de datos de Nominatim ($PHOTON_HOST/$PHOTON_DB) en Photon"
    for i in $(seq 1 60); do
      if (echo > /dev/tcp/$PHOTON_HOST/$PHOTON_PORT_DB) >/dev/null 2>&1; then break; fi
      echo "    esperando a postgres... ($i)"
      sleep 3
    done
    as_photon "java ${PHOTON_JAVA_OPTS:-} -jar $PHOTON_JAR import \
      -host $PHOTON_HOST -port $PHOTON_PORT_DB \
      -user $PHOTON_USER -password $PHOTON_PASSWORD -database $PHOTON_DB \
      -languages en,es,de,fr -j ${PHOTON_JOBS:-4}"
    touch photon_data/.import-ok
    echo "==> Import de Photon terminado"
    ;;
  serve)
    echo "==> Photon escuchando en 0.0.0.0:$PHOTON_LISTEN_PORT"
    as_photon "java ${PHOTON_JAVA_OPTS:-} -jar $PHOTON_JAR serve \
      -listen-ip 0.0.0.0 -listen-port $PHOTON_LISTEN_PORT -cors-any \
      -data-dir ${PHOTON_DATA_DIR:-/opt/photon}"
    ;;
  *)
    exec "$@"
    ;;
esac

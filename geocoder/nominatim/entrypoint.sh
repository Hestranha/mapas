#!/bin/bash
# Importa el .osm.pbf en la base de datos de Nominatim y deja la BD lista para Photon.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/data-env}"
PBF_FILE="${PBF_FILE:-/data/peru-261020.osm.pbf}"
NOMINATIM_BIN="${NOMINATIM_BIN:-/opt/venv/bin/nominatim}"

export NOMINATIM_DATABASE_DSN="${NOMINATIM_DATABASE_DSN:-postgresql://nominatim:nominatim@db:5432/nominatim}"
export NOMINATIM_IMPORT_STYLE="${NOMINATIM_IMPORT_STYLE:-full}"

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

case "${1:-import}" in
  import)
    if [ ! -f "$PBF_FILE" ]; then
      echo "ERROR: no existe el PBF $PBF_FILE" >&2
      exit 1
    fi
    echo "==> Importando $PBF_FILE en $NOMINATIM_DATABASE_DSN"
    echo "==> estilo de import: $NOMINATIM_IMPORT_STYLE"
    # Espera a que postgres acepte conexiones
    for i in $(seq 1 60); do
      if pg_isready -h "${PGHOST:-db}" -p "${PGPORT:-5432}" -U "${PGUSER:-nominatim}" >/dev/null 2>&1; then
        break
      fi
      echo "    esperando a postgres... ($i)"
      sleep 3
    done
    # Nominatim v5 exige un usuario de solo lectura para la API web
    ADMIN_DSN="postgresql://${PGUSER:-nominatim}:nominatim@${PGHOST:-db}:${PGPORT:-5432}/postgres"
    if ! psql "$ADMIN_DSN" -tAc "SELECT 1 FROM pg_roles WHERE rolname='www-data'" 2>/dev/null | grep -q 1; then
      echo "==> Creando el usuario de solo lectura 'www-data'"
      psql "$ADMIN_DSN" -c "CREATE ROLE \"www-data\" LOGIN PASSWORD 'nominatim'" || true
    fi
    # Estado de la base de datos
    db_exists=$(psql "$ADMIN_DSN" -tAc "SELECT 1 FROM pg_database WHERE datname='nominatim'" 2>/dev/null | tr -d ' ' || true)
    rows=0
    if [ "$db_exists" = "1" ]; then
      rows=$(psql "$NOMINATIM_DATABASE_DSN" -tAc "SELECT count(*) FROM placex" 2>/dev/null | tr -d ' ' || true)
      rows=${rows:-0}
    fi
    # Si la base ya tiene datos importados, no se vuelve a importar
    if [ "${rows:-0}" -gt 0 ] && [ "${FORCE_IMPORT:-0}" != "1" ]; then
      echo "==> La base ya contiene $rows lugares importados: se omite el import"
      echo "==> (usa FORCE_IMPORT=1 para reimportar)"
      exit 0
    fi
    # La base existe pero esta vacia (o se pide forzar): se borra para recrearla
    if [ "$db_exists" = "1" ]; then
      echo "==> Recreando la base de datos 'nominatim'"
      psql "$ADMIN_DSN" -c "DROP DATABASE IF EXISTS nominatim" || true
    fi
    "$NOMINATIM_BIN" import --osm-file "$PBF_FILE" 2>&1 | tee setup.log
    echo "==> Verificando la base de datos"
    "$NOMINATIM_BIN" admin --check-database
    echo "==> Import de Nominatim terminado"
    ;;
  check)
    "$NOMINATIM_BIN" admin --check-database
    ;;
  *)
    exec "$@"
    ;;
esac

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NOMINATIM_VERSION=v5.3.3 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-dev python3-pip \
      osm2pgsql \
      postgresql-client-16 \
      libicu-dev pkg-config build-essential \
      ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*

# Codigo de Nominatim v5 (escrito en Python)
RUN git clone --depth 1 --branch ${NOMINATIM_VERSION} \
      https://github.com/osm-search/Nominatim.git /opt/Nominatim \
 && rm -rf /opt/Nominatim/.git

# Country grid (nombres de pais para el indice de busqueda). El paquete lo
# incluye como "forced include", asi que debe existir antes de instalar.
RUN curl -fsSL -A "Mozilla/5.0 (compatible; NominatimSetup/5.3.3)" \
      -o /opt/Nominatim/data/country_osm_grid.sql.gz \
      https://nominatim.org/data/country_grid.sql.gz

RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir /opt/Nominatim/packaging/nominatim-db

WORKDIR /data-env
VOLUME /data-env

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["import"]

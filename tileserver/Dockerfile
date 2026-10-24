FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py /app/server.py
COPY static /app/static

ENV PORT=8080 \
    MBTILES_PATH=/data/peru.mbtiles \
    STATIC_DIR=/app/static \
    PHOTON_URL=http://photon:2322

EXPOSE 8080
CMD ["python3", "/app/server.py"]

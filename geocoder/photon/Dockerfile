FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PHOTON_VERSION=1.3.0 \
    PHOTON_HOME=/opt/photon \
    PHOTON_PORT=2322

RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-21-jre-headless ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -A "Mozilla/5.0 (compatible; PhotonSetup/1.3.0)" -o /opt/photon.jar \
      "https://github.com/komoot/photon/releases/download/${PHOTON_VERSION}/photon-${PHOTON_VERSION}.jar" \
 && mkdir -p /opt/photon /data/photon_data \
 && useradd -m -u 1001 photon \
 && chown -R photon:photon /opt/photon /data

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /opt/photon

ENV PHOTON_JAVA_OPTS="-Xms512m -Xmx3g"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]

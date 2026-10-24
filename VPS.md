# Despliegue en VPS (Ubuntu 22.04/24.04, Debian 12, Rocky/Alma 9)

Guía para subir el mapa a un servidor con acceso **solo por terminal** y levantarlo con
un `docker compose up -d`.

> Esta guía **no toca** el stack local: el `docker-compose.yml` de siempre sigue igual.
> Lo único nuevo es `docker-compose.vps.yml`, que se usa como *override* (se fusiona con
> el original) y solo en el VPS.

---

## 0. Requisitos del VPS

| | Mínimo | Recomendado |
|---|---|---|
| SO | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB (el import puede morirse) | **8 GB** |
| Disco libre | 20 GB | **30 GB** |
| Docker | Engine 24+ con el plugin `docker compose` v2.24+ | idem |

Instalación de Docker (Ubuntu/Debian):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
docker compose version      # debe ser v2.24 o superior (soporta !override)
```

Si eres root, puedes usar `rootless`/sin sudo; los comandos usan `sudo` por comodidad.

---

## 1. Preparar el paquete en tu PC (Windows o Linux)

```bash
# en la carpeta del proyecto
docker compose build            # (solo si aun no tienes las imagenes)
bash scripts/03-empaquetar-vps.sh          # Linux/macOS
# o en Windows:
powershell -ExecutionPolicy Bypass -File scripts\03-empaquetar-vps.ps1
```

Genera `dist/vps/` con:

```
dist/vps/
├── mapa-imagenes.tar.gz      ~1,8 GB (las 3 imagenes Docker)
├── proyecto/                 docker-compose*.yml, código, PBF, mbtiles
└── SHA256SUMS.txt
```

> Las imágenes ya llevan dentro Java, PostgreSQL/PostGIS, Nominatim, Photon y MapLibre.
> En el VPS **no hay que instalar nada más que Docker**.

---

## 2. Subir al VPS

```bash
scp -r dist/vps/* usuario@TU_VPS:/opt/mapas/
ssh usuario@TU_VPS
cd /opt/mapas && sha256sum -c SHA256SUMS.txt    # verifica la copia
```

Estructura en el VPS:

```
/opt/mapas/
├── mapa-imagenes.tar.gz
├── SHA256SUMS.txt
└── proyecto/            <- aqui vive el stack
```

---

## 3. Arrancar (un solo comando)

```bash
cd /opt/mapas/proyecto
sudo bash deploy/vps/iniciar.sh
```

El script:

1. carga las imágenes (`docker load`),
2. ajusta `vm.max_map_count=262144` (OpenSearch/Photon **no arranca** sin esto),
3. ejecuta `docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d`.

Equivalente manual:

```bash
gunzip -c ../mapa-imagenes.tar.gz | docker load
sudo cp deploy/vps/99-photon.conf /etc/sysctl.d/ && sudo sysctl --system
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d
```
---

## 4. Qué esperar

| Momento | Qué pasa |
|---|---|
| 0-1 min | Postgres arranca, `nominatim-import` empieza a cargar el PBF (250 MB) |
| 5-25 min | Import de Nominatim (osm2pgsql). **El mapa ya sirve tiles** (el override arranca el tileserver sin esperar) |
| +2 min | `photon-import` indexa ~600k documentos en OpenSearch |
| +2 min | `photon` sirve la API; el buscador del mapa empieza a responder |

Ver el progreso:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f nominatim-import
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f photon-import
```

Comprobar:

```bash
curl http://localhost:8080/health
# {"status":"ok", ... "geocoder":"up"}  <- "up" cuando el geocodificador termine
```

---

## 5. Accesos

| Servicio | URL | Nota |
|---|---|---|
| Mapa + buscador | `http://IP_VPS:8080/` | público |
| Health | `http://IP_VPS:8080/health` | público |
| Photon (API cruda) | `127.0.0.1:2322` | **solo local**; desde tu PC: `ssh -L 2322:127.0.0.1:2322 usuario@TU_VPS` |
| PostgreSQL | sin publicar | solo red interna de Docker |

Abre el puerto 8080 en el firewall del proveedor (seguridad de AWS/GCP/Hetzner…):

```bash
sudo ufw allow 8080/tcp && sudo ufw reload     # Ubuntu con ufw
```

---

## 6. HTTPS (recomendado para internet)

El servidor ya trae MapLibre y el proxy `/geocode`; pon Nginx delante:

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/mapas`:

```nginx
server {
    listen 80;
    server_name mapa.tudominio.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/mapas /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d mapa.tudominio.com
```

---

## 7. Operación

```bash
cd /opt/mapas/proyecto
alias mapa='docker compose -f docker-compose.yml -f docker-compose.vps.yml'

mapa ps                     # estado
mapa logs -f tileserver     # logs del mapa
mapa restart photon         # reiniciar solo el geocodificador
mapa down                   # parar (los datos quedan en los volumenes)
mapa up -d                  # volver a levantar (no reimporta)
```

Actualizar los tiles (con un PBF nuevo) sin tocar la BD:

```bash
bash scripts/02-generar-mbtiles.sh
docker compose -f docker-compose.yml -f docker-compose.vps.yml restart tileserver
```

Reimportar la BD y el índice del geocodificador:

```bash
FORCE_IMPORT=1 docker compose -f docker-compose.yml -f docker-compose.vps.yml \
  up --force-recreate nominatim-import photon-import
docker compose -f docker-compose.yml -f docker-compose.vps.yml restart photon
```

---

## 8. Problemas típicos

| Síntoma | Causa | Solución |
|---|---|---|
| Photon muere al arrancar con `max_map_count [65530] is too low` | falta el sysctl | `sudo sysctl -w vm.max_map_count=262144` y persistirlo con `deploy/vps/99-photon.conf` |
| `nominatim-import` muere con OOM | RAM insuficiente | usa un VPS de 8 GB o añade swap (`sudo fallocate -l 8G /swapfile; sudo mkswap /swapfile; sudo swapon /swapfile`) |
| `permission denied` al montar `./data/peru.mbtiles` | SELinux (RHEL/Rocky/Alma) | el override ya añade `:z`; si persiste, `sudo chcon -Rt svirt_sandbox_file_t /opt/mapas/proyecto` |
| El mapa carga pero el buscador da error | el import de Photon sigue en curso | normal los primeros ~30 min; mira `logs -f photon-import` |
| `docker compose config` falla con `!override` | Compose < 2.24 | actualiza el plugin (`sudo apt-get install --only-upgrade docker-compose-plugin`) o edita `docker-compose.yml` a mano |
| Disco lleno | volúmenes + imágenes | `docker system df` y `docker image prune -a` (no borra los volúmenes) |

---

## 9. Qué se publicaron en el VPS (resumen de seguridad)

- `8080` → mapa web (público).
- `2322` → Photon, solo en `127.0.0.1`.
- `5432` → **no** se publica; la BD solo existe en la red interna de Docker.
- El `override` añade `:z` (SELinux) a los bind-mounts.

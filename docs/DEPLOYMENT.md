# AuctionBot — Deployment Guide

> **Última actualización:** 2026-04-05
> **Estado actual del deploy:** ❌ Caído (502 Bad Gateway)

## Infraestructura Actual

```
                     Internet
                        │
                ┌───────┴────────┐
                ▼                ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  Cloudflare Pages │  │  Cloudflare Tunnel│
    │  (dashboard HTML) │  │  (API Flask)      │
    │  ──────────────── │  │  ────────────────  │
    │  CDN global       │  │  auctionbot.       │
    │  Deploy: git push │  │  luisaguilar       │
    │  dashboard/       │  │  aguila.com/api/*  │
    └──────────────────┘  └────────┬─────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  Servidor Origen  │
                          │  Docker Compose   │
                          │  ──────────────── │
                          │  dashboard:8080   │  ← Flask API
                          │  scheduler        │  ← Playwright
                          │  cloudflared      │  ← Tunnel
                          │  data/auctionbot  │  ← SQLite (volumen)
                          └──────────────────┘
```

**Archivos de infraestructura:**
- `Dockerfile` — imagen Flask (sin Playwright)
- `Dockerfile.scraper` — imagen Playwright
- `docker-compose.yml` — orquestación de los 3 servicios
- `.dockerignore` — excluye DB, secrets y venv del build context

## ¿Por qué está caído?

El error 502 significa que Cloudflare puede conectarse al túnel, pero el servidor destino no responde. Causas posibles:
1. El proceso Flask (`ab056_dashboard.py`) no está corriendo
2. El contenedor LXC se reinició y Flask no se auto-inicia
3. La DB se movió o corrompió
4. El puerto 8080 está ocupado o el bind falló

## Plan de Fix: Dockerización

### Estructura propuesta

```
auctionbot/
├── docker-compose.yml          # Orquestación de servicios
├── Dockerfile                  # Imagen para Flask + Scheduler
├── Dockerfile.scraper          # Imagen para Playwright (más pesada)
├── .env                        # Secrets (TUNNEL_TOKEN, etc.)
└── ...
```

### docker-compose.yml propuesto

```yaml
version: "3.9"

services:
  # Dashboard web (Flask)
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8080:8080"
    volumes:
      - ./data:/opt/auctionbot/data
      - ./dashboard:/opt/auctionbot/dashboard
    environment:
      - AUCTIONBOT_DB_PATH=/opt/auctionbot/data/auctionbot.db
    command: python app/ab056_dashboard.py --port 8080

  # Scheduler (corre el scraper cada N minutos)
  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.scraper
    restart: always
    volumes:
      - ./data:/opt/auctionbot/data
    env_file: .env
    environment:
      - AUCTIONBOT_DB_PATH=/opt/auctionbot/data/auctionbot.db
    command: python app/ab054_scheduler.py --interval 30

  # Cloudflare Tunnel
  tunnel:
    image: cloudflare/cloudflared:latest
    restart: always
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
```

### Dockerfile (Flask dashboard)

```dockerfile
FROM python:3.12-slim

WORKDIR /opt/auctionbot

COPY app/ app/
COPY dashboard/ dashboard/
COPY .env.example .env.example

RUN pip install --no-cache-dir flask

EXPOSE 8080

CMD ["python", "app/ab056_dashboard.py", "--port", "8080"]
```

### Dockerfile.scraper (Playwright)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /opt/auctionbot

COPY app/ app/
COPY .env.example .env.example

RUN pip install --no-cache-dir flask playwright
RUN playwright install chromium

CMD ["python", "app/ab054_scheduler.py"]
```

## Deploy Step-by-Step

### 1. En el servidor, clonar o actualizar el repo

```bash
cd /opt
git clone <repo-url> auctionbot  # o git pull si ya existe
cd auctionbot
```

### 2. Configurar `.env`

```bash
cp .env.example .env
nano .env
# Agregar:
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
# TUNNEL_TOKEN=...
# AUCTIONBOT_DB_PATH=/opt/auctionbot/data/auctionbot.db
```

### 3. Construir y levantar

```bash
docker compose up -d --build
docker compose logs -f
```

### 4. Verificar

```bash
# Dashboard local
curl http://localhost:8080/api/stats

# Dashboard público
curl https://auctionbot.luisaguilaraguila.com/api/stats
```

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| 502 Bad Gateway | Flask no corre | `docker compose restart dashboard` |
| Dashboard sin datos | DB vacía o ruta incorrecta | Verificar `AUCTIONBOT_DB_PATH` y que el volumen esté montado |
| Scheduler no envía alertas | Token/ChatID inválido | Verificar `.env` y probar `--dry-run` |
| Tunnel no conecta | Token expirado | Regenerar en Cloudflare Zero Trust Dashboard |
| DB locked | Escrituras concurrentes | WAL mode debería manejarlo; si persiste, reiniciar scheduler |

## Cloudflare Tunnel Setup

Si necesitas recrear el túnel:

1. Ir a [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. Networks → Tunnels → Create Tunnel
3. Nombre: `auctionbot`
4. Copiar el `TUNNEL_TOKEN` al `.env`
5. Public Hostname: `auctionbot.luisaguilaraguila.com` → `http://dashboard:8080`
6. `docker compose up -d tunnel`

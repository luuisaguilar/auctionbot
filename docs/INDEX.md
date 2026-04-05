# AuctionBot — Documentación del Proyecto

> **Última actualización:** 2026-04-05
> **Dominio:** `auctionbot.luisaguilaraguila.com`

## Índice de Documentos

| Documento | Descripción |
|---|---|
| [CURRENT_STATE.md](./CURRENT_STATE.md) | Estado actual del proyecto, arquitectura, stack, y qué está funcional |
| [BACKLOG.md](./BACKLOG.md) | Product backlog completo con sprints e historias priorizadas |
| [ADR/](./adr/) | Architecture Decision Records — decisiones técnicas importantes |
| [HANDOFF.md](./HANDOFF.md) | Guía de handoff para retomar el proyecto sin contexto previo |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Cómo desplegar, infraestructura, Cloudflare Tunnel, troubleshooting |
| [WEB_IMPROVEMENT_PLAN.md](./WEB_IMPROVEMENT_PLAN.md) | Plan de mejora del sitio web (dashboard) — desarrollo y despliegue |

## Quick Start

```bash
# 1. Clonar y configurar
cp .env.example .env
# Editar .env con tus tokens de Telegram

# 2. Instalar dependencias
python -m venv venv
venv\Scripts\activate          # Windows
pip install playwright flask
python -m playwright install chromium

# 3. Inicializar DB
cd app
python ab055_sqlite.py

# 4. Correr scraper (dry-run)
python ab053_v2.py --dry-run

# 5. Correr dashboard
python ab056_dashboard.py --port 8080
```

## Estructura del Proyecto

```
auctionbot/
├── app/                          # Código Python principal
│   ├── ab052_bidgallery_scraper.py  # Scraper standalone (exploración)
│   ├── ab053_telegram_alerts.py     # Alertas Telegram v1 (legacy)
│   ├── ab053_v2.py                  # Alertas Telegram v2 + SQLite ← ACTIVO
│   ├── ab054_scheduler.py           # Scheduler (cron cada N min)
│   ├── ab055_repository.py          # Capa repository (patrón agnóstico)
│   ├── ab055_sqlite.py              # Implementación SQLite
│   ├── ab056_dashboard.py           # Servidor Flask + API REST
│   ├── check_time.py                # Utilidad debug de timezones
│   └── env_loader.py                # Cargador de .env sin dependencias
├── dashboard/
│   └── index.html                   # Frontend SPA (vanilla JS)
├── data/
│   └── auctionbot.db               # SQLite DB (~210 MB, 406k items)
├── artifacts/                       # Outputs del scraper
│   └── ab053/                       # Logs de alertas
├── docs/                            # ← ESTA CARPETA
├── .env                             # Secrets (no versionado)
├── .env.example                     # Template de configuración
└── .gitignore
```

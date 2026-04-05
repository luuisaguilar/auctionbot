# AuctionBot — Handoff Guide

> **Propósito:** Cualquier persona (o agente de IA) que retome este proyecto puede entender el contexto completo leyendo únicamente este documento + los enlaces internos.

## ¿Qué es AuctionBot?

Un bot que scrapea subastas de **Auction Nation** (plataforma de liquidación/subastas en Arizona), detecta items con bid=$0 (oportunidades de compra barata), y envía alertas vía Telegram. Tiene un dashboard web para monitoreo.

## Lectura Obligatoria (en este orden)

1. **[CURRENT_STATE.md](./CURRENT_STATE.md)** — Qué está construido, qué funciona, qué está roto
2. **[BACKLOG.md](./BACKLOG.md)** — Qué falta por hacer, priorizado en sprints
3. **[adr/](./adr/)** — Por qué se tomaron las decisiones técnicas

## Archivos Clave (mapa mental)

```
LO MÁS IMPORTANTE:
  ab053_v2.py      ← El script que corre en producción (scraper + alertas)
  ab054_scheduler.py ← El loop que corre ab053_v2 cada 30 min
  ab055_repository.py ← Interfaz de DB (leer primero para entender el data model)
  ab056_dashboard.py  ← Flask API server
  dashboard/index.html ← Frontend completo (single file)

PARA ENTENDER EL SCRAPING:
  ab052_bidgallery_scraper.py ← Script original de exploración (buena documentación)

INFRA:
  .env              ← Tokens Telegram + ruta de DB
  env_loader.py     ← Lee .env sin python-dotenv

LEGACY (no tocar):
  ab053_telegram_alerts.py ← v1 sin DB, reemplazada por ab053_v2
```

## Convenciones del Proyecto

1. **Naming:** Los archivos siguen un esquema `ab0XX_nombre.py` donde XX es un número incremental de "experimento". El proyecto empezó como una serie de scripts exploratorios.
2. **Imports:** Todos los scripts asumen que el CWD es `app/`. Se ejecutan como `python ab053_v2.py` desde dentro de `app/`.
3. **DB Path:** Configurable via `AUCTIONBOT_DB_PATH` en `.env`. Default: `data/auctionbot.db` (relativo al root del proyecto) en local, `/opt/auctionbot/data/auctionbot.db` en el servidor.
4. **No hay `requirements.txt`:** Las dependencias son: `playwright`, `flask`. Eso es todo.
5. **Timezone:** Auction Nation opera en `America/Phoenix` (Arizona, sin horario de verano). El scraper fuerza esta timezone en el browser context. Los timestamps de `end_time` son Unix epoch UTC.

## Cómo Correr Localmente

```bash
cd auctionbot
python -m venv venv
venv\Scripts\activate  # Windows
pip install playwright flask
python -m playwright install chromium

# Configurar
cp .env.example .env
# Editar .env con tokens reales

# Test rápido
cd app
python ab053_v2.py --dry-run --max-minutes 60

# Dashboard
python ab056_dashboard.py --port 8080
# Abrir http://localhost:8080
```

## Cómo Deployar

Ver [DEPLOYMENT.md](./DEPLOYMENT.md) para la guía completa. Resumen:
1. El proyecto corre en un servidor Linux (probablemente LXC/Proxmox — se inferió de commits "recover from LXC 112")
2. Se usa Cloudflare Tunnel para exponer el dashboard en `auctionbot.luisaguilaraguila.com`
3. **Actualmente caído** — necesita containerización con Docker

## Estado del Deploy (2026-04-05)

| Servicio | Estado | Notas |
|---|---|---|
| Cloudflare Tunnel | ✅ Up (Dallas) | El túnel responde pero el origen no |
| Flask Dashboard | ❌ Down | El servidor no está corriendo |
| Scheduler | ❓ Desconocido | Necesita verificación en el servidor |
| Telegram Bot | ✅ Funcional | Token y Chat ID configurados |

## Riesgos y Deuda Técnica

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Sin backups de la DB | Pérdida de 406k items | Agregar script de backup o migrar a Supabase |
| Código duplicado en parsers | Bugs se arreglan en un archivo pero no en otro | Refactoring a módulo compartido (Sprint 1) |
| Sin auth en dashboard | Cualquiera con la URL puede ver datos | Agregar password o Cloudflare Access |
| Playwright consume RAM | ~200MB por corrida | Aceptable para 1 instancia |
| Sin health checks | No sabemos si el scheduler se murió | Docker restart policy + monitoring |

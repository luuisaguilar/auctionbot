# AuctionBot — Estado Actual del Proyecto

> **Fecha:** 2026-04-05
> **Versión:** v0.5 (MVP funcional con alertas y dashboard)

## Resumen Ejecutivo

AuctionBot es un sistema automatizado que scrapea subastas de **Auction Nation** (Arizona, USA), detecta oportunidades (items con bid = $0) y envía alertas via Telegram. Incluye un dashboard web para monitoreo.

## Qué Funciona Hoy

| Componente | Estado | Descripción |
|---|---|---|
| **Scraper** (`ab053_v2.py`) | ✅ Funcional | Scrapea hasta 10 subastas activas via Playwright + interceptando API `getitems` |
| **Alertas Telegram** | ✅ Funcional | Envía oportunidades urgentes (bid=$0, cierre ≤20min) con deduplicación vía DB |
| **Scheduler** (`ab054`) | ✅ Funcional | Loop cada 30min ejecutando el scraper como subproceso |
| **SQLite DB** (`ab055`) | ✅ Funcional | 3 tablas (runs, items, alerts), 406,911 items históricos, ~210MB |
| **Dashboard API** (`ab056`) | ✅ Funcional | Flask server con 4 endpoints REST (`/api/stats`, `/api/runs`, `/api/opportunities`, `/api/alerts`) |
| **Dashboard Frontend** | ✅ Funcional | SPA vanilla JS con 3 vistas: resumen, oportunidades, corridas |
| **Despliegue web** | ❌ Caído (502) | `auctionbot.luisaguilaraguila.com` — Cloudflare Tunnel activo pero host no responde |

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Auction Nation                        │
│            auctionnation.com (sitio web)                 │
└──────────────────────┬──────────────────────────────────┘
                       │ Playwright headless Chrome
                       │ intercepta XHR "getitems"
                       ▼
┌─────────────────────────────────────────────────────────┐
│              ab053_v2.py (Scraper + Alertas)             │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ Landing page  │→ │ /bidgallery/  │→ │ Parse items  │ │
│  │ detect IDs    │  │ + pagination  │  │ + filter     │ │
│  └──────────────┘  └───────────────┘  └──────┬───────┘ │
└──────────────────────────────────────────────┼─────────┘
                       │                        │
        ┌──────────────┘                        │
        ▼                                       ▼
┌──────────────┐                    ┌──────────────────┐
│   Telegram   │                    │   SQLite DB      │
│   Bot API    │                    │  (ab055_sqlite)  │
│  ──────────  │                    │  ──────────────  │
│  Alertas de  │                    │  runs            │
│  oportunidad │                    │  items (406k)    │
└──────────────┘                    │  alerts          │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  ab056_dashboard  │
                                    │  Flask :8080      │
                                    │  ──────────────── │
                                    │  /api/stats       │
                                    │  /api/runs        │
                                    │  /api/opps        │
                                    │  /api/alerts      │
                                    └────────┬─────────┘
                                             │
                                             ▼
                                    ┌──────────────────┐
                                    │  Cloudflare      │
                                    │  Tunnel          │
                                    │  ──────────────  │
                                    │  auctionbot.     │
                                    │  luisaguilar     │
                                    │  aguila.com      │
                                    └──────────────────┘
```

## Stack Técnico

| Capa | Tecnología |
|---|---|
| Scraping | Python 3.12+ + Playwright (Chromium headless) |
| Alertas | Telegram Bot API (urllib, sin SDK) |
| Base de datos | SQLite con WAL mode |
| Backend web | Flask (Python) |
| Frontend web | Vanilla HTML/JS/CSS (SPA single-file) |
| Tipografía | IBM Plex Sans + IBM Plex Mono |
| Despliegue | Cloudflare Tunnel → origin server |
| Scheduling | `ab054_scheduler.py` (loop asyncio) |
| Env config | `.env` manual (env_loader.py sin dependencias) |

## Base de Datos — Schema Actual

```sql
-- Tabla de corridas del scraper
CREATE TABLE runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    auctions_scraped INTEGER DEFAULT 0,
    items_total      INTEGER DEFAULT 0,
    opportunities    INTEGER DEFAULT 0,
    alerts_sent      INTEGER DEFAULT 0,
    dry_run          INTEGER DEFAULT 0
);

-- Tabla de items scrapeados (406,911 registros)
CREATE TABLE items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER REFERENCES runs(id),
    scraped_at      TEXT NOT NULL,
    auction_id      TEXT NOT NULL,
    auction_title   TEXT,
    item_id         TEXT NOT NULL,
    lot_number      TEXT,
    title           TEXT,
    current_bid     REAL,
    min_bid         REAL,
    retail_price    REAL,
    end_time        INTEGER,
    condition_text  TEXT,
    item_url        TEXT,
    is_opportunity  INTEGER DEFAULT 0
);

-- Tabla de alertas enviadas (dedup)
CREATE TABLE alerts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at           TEXT NOT NULL,
    item_id           TEXT NOT NULL,
    auction_id        TEXT NOT NULL,
    lot_number        TEXT,
    title             TEXT,
    min_bid           REAL,
    retail_price      REAL,
    minutes_remaining INTEGER,
    dry_run           INTEGER DEFAULT 0
);
```

## Estadísticas de la DB (2026-04-05)

- **Total items:** 406,911 registros
- **Títulos únicos:** 5,501
- **DB size:** ~210 MB

## Datos del Dominio (Auction Nation)

- **Fuente:** auctionnation.com (Arizona, USA)
- **Tipos de subasta:** Home Improvement, Kitchen & Bath, Furniture, Tools, Electronics, Coins, Sterling Silver, Outdoor, Miscellaneous, etc.
- **Estructura de API:** El sitio usa SPA (React/JS) que dispara XHR POST a endpoints `getitems` con respuesta JSON paginada (40 items/page)
- **IDs de subastas:** Detectadas via links en DOM + HTML + API auctions/
- **URL pattern:** `online.auctionnation.com//auction/{id}/bidgallery/`
- **No requiere login** para lectura

## Problemas Conocidos

1. **Dashboard caído (502):** El servidor origen no está corriendo. El túnel Cloudflare está activo (Dallas PoP) pero el host responde con error.
2. **Código duplicado:** `ab053.py` y `ab053_v2.py` comparten mucho código de parsing. Necesita refactoring a un módulo compartido.
3. **Sin categorización:** Los 5,501 títulos únicos no están categorizados. No hay forma de filtrar por tipo de producto.
4. **Sin Dockerfile:** El despliegue es manual. No hay containerización.
5. **Rutas hardcodeadas:** `ab056_dashboard.py` tiene paths como `/opt/auctionbot/data/` hardcodeados (asumo la máquina de deploy), no usa `env_loader`.
6. **Sin tests:** No hay tests unitarios ni de integración.
7. **Retail price parcial:** Solo ~X% de los items tienen retail price extraído del título.

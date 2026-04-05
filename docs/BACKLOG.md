# AuctionBot — Product Backlog

> **Última actualización:** 2026-04-05
> **Formato:** Historias priorizadas por sprint con estimaciones relativas

## Priority Legend
- 🔴 **P0** — Blocker / Must-have para el sprint
- 🟠 **P1** — Alta prioridad, debería completarse
- 🟡 **P2** — Nice-to-have, puede diferirse
- ⚪ **P3** — Backlog futuro

---

## Sprint 1 — "Fundación" (Actual)
> **Objetivo:** Categorización de productos + arreglar deploy + documentación completa

### 🔴 P0 — Arreglar deploy (dashboard caído)
- [ ] Diagnosticar por qué el host responde 502
- [ ] Crear `Dockerfile` para el dashboard Flask
- [ ] Crear `docker-compose.yml` con servicios: dashboard, cloudflared, scheduler (opcional)
- [ ] Configurar variables de entorno en `.env` productivo
- [ ] Verificar que `auctionbot.luisaguilaraguila.com` carga correctamente
- **Notas:** El Cloudflare Tunnel está activo (Dallas PoP). El problema es que Flask no corre en el servidor origen. Necesitamos containerizarlo y asegurar que arranque solo.

### 🔴 P0 — Categorización de productos (ab057)
- [ ] Crear módulo `ab057_categorizer.py` con sistema de keywords
- [ ] Agregar columna `category TEXT` a tabla `items` en SQLite
- [ ] Modificar `insert_items_bulk()` para incluir categoría
- [ ] Backfill: categorizar los 406k items existentes
- [ ] Exponer en `ab055_repository.py`
- [ ] Agregar endpoint `GET /api/categories` en dashboard API
- [ ] Agregar filtro por categoría en `GET /api/opportunities?category=X`
- [ ] Nueva sección "Categorías" en el frontend del dashboard

### 🟠 P1 — Refactoring del código duplicado
- [ ] Extraer parsing compartido (`parse_price`, `extract_items_from_page`, etc.) a un módulo `ab_parsers.py`
- [ ] Que `ab052`, `ab053`, `ab053_v2` importen de `ab_parsers`
- [ ] Eliminar duplicación de ~100 líneas

### 🟡 P2 — Dashboard: usar env_loader
- [ ] Que `ab056_dashboard.py` use `env_loader` para `DB_PATH` y `STATIC_DIR`
- [ ] Eliminar rutas hardcodeadas a `/opt/auctionbot/`

---

## Sprint 2 — "Rastreo Inteligente"
> **Objetivo:** Poder rastrear categorías específicas y recibir alertas personalizadas

### 🟠 P1 — Watchlist por categoría
- [ ] Tabla `watchlist` en SQLite: categorías que el usuario quiere rastrear
- [ ] API endpoints para CRUD de watchlist
- [ ] UI en dashboard para activar/desactivar rastreo por categoría
- [ ] Alertas Telegram filtradas por watchlist (solo alertar categorías rastreadas)

### 🟠 P1 — Dashboard mejorado: columna de categoría
- [ ] Badge de categoría en tabla de oportunidades
- [ ] Filtro dropdown por categoría
- [ ] Gráfica de distribución de categorías (pie chart o bar chart)

### 🟡 P2 — Historial de precios por item
- [ ] Vista de detalle de item en el dashboard
- [ ] Gráfica de evolución del bid a lo largo de corridas
- [ ] Endpoint `/api/item/<id>/history`

### 🟡 P2 — Mejorar categorización
- [ ] Feedback loop: UI para re-categorizar items mal clasificados
- [ ] Usar auction_title como señal secundaria
- [ ] Logging de items categorizados como "Otro" para refinar reglas

---

## Sprint 3 — "Experiencia Web Completa"
> **Objetivo:** Dashboard profesional con auth y UX pulida

### 🟠 P1 — Autenticación básica
- [ ] Login simple (variable de entorno `DASHBOARD_PASSWORD`)
- [ ] Middleware Flask para proteger la API
- [ ] Cloudflare Access como alternativa (SSO email)

### 🟠 P1 — Dashboard responsive y mobile-first
- [ ] Rediseño mobile (la sidebar actual se oculta en <700px)
- [ ] PWA manifest para "instalar" como app
- [ ] Push notifications alternativas a Telegram

### 🟡 P2 — Búsqueda full-text
- [ ] SQLite FTS5 sobre títulos de items
- [ ] Barra de búsqueda en el dashboard
- [ ] Autocompletar con sugerencias en tiempo real

### 🟡 P2 — Notificaciones configurables
- [ ] Settings page: elegir categorías, umbral de minutos, max alertas
- [ ] Guardar en DB (tabla `settings`)
- [ ] Telegram commands: `/watch electronics`, `/unwatch coins`

---

## Backlog Futuro (No planificado)

### ⚪ P3 — Multi-site support
- [ ] Abstraer scraper para soportar otros sitios de subastas
- [ ] Plugin system: cada sitio tiene su propio parser
- [ ] Shared DB schema para comparar entre sitios

### ⚪ P3 — Analytics avanzados
- [ ] Predicción de precio final usando historial
- [ ] Score de "calidad de oportunidad" (ratio retail/min_bid + tiempo + categoría)
- [ ] Reporte semanal automático vía Telegram

### ⚪ P3 — Migración a Supabase
- [ ] Implementar `ab055_supabase.py` (ya diseñado en el patrón repository)
- [ ] Real-time updates en dashboard via websockets
- [ ] Auth con Supabase Auth
- [ ] Deployment en Edge (Supabase + Vercel/Cloudflare Pages)

### ⚪ P3 — Bidding automático
- [ ] Research de ToS de Auction Nation
- [ ] API de bidding (si existe)
- [ ] Reglas de auto-bid por categoría y budget máximo
- [ ] Safeguards y confirmaciones

### ⚪ P3 — CI/CD
- [ ] GitHub Actions para lint + tests
- [ ] Auto-deploy a servidor via SSH/Docker on push to main
- [ ] Health checks y alertas de sistema caído

### ⚪ P3 — Imágenes de productos
- [ ] Scrapear thumbnails de los items
- [ ] Mostrar en el dashboard
- [ ] Enviar imagen en alertas Telegram

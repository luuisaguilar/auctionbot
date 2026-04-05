# AuctionBot — Plan de Mejora del Sitio Web

> **Objetivo:** Transformar el dashboard actual (MVP funcional) en un sitio web profesional, útil y bonito.

## Estado Actual del Dashboard

El dashboard actual es un archivo `index.html` de 442 líneas con:
- ✅ 3 vistas: Resumen, Oportunidades, Corridas
- ✅ Dark/light mode
- ✅ Diseño aceptable con IBM Plex Sans/Mono
- ✅ Badges de ratio y condición
- ❌ Sin categorización de productos
- ❌ Sin filtros avanzados
- ❌ Sin búsqueda
- ❌ Sin autenticación
- ❌ Sin responsive real (sidebar se oculta en mobile, pero no hay nav alternativa)
- ❌ Sin gráficas ni visualización de datos

## Cómo se Desarrollaría

### Approach: Evolución incremental del SPA vanilla

Dado que el dashboard actual funciona y es simple, **no migraremos a un framework** (ver ADR-004). En su lugar:

1. **Sprint 1:** Agregar sección de categorías + arreglar deploy
2. **Sprint 2:** Filtros avanzados, watchlist, gráficas básicas
3. **Sprint 3:** Auth, responsive mobile, PWA
4. **Evaluación:** Si en Sprint 3 el `index.html` sobrepasa ~1,500 líneas, migrar a Vite + vanilla TS con módulos ES

### Técnicamente:

- **CSS:** Seguir con CSS custom (variables root). Agregar componentes: cards de categoría, dropdowns de filtro, modals.
- **JS:** Extraer funciones a módulos si crece demasiado. De momento, todo en `<script>` inline está bien.
- **API:** Flask sigue sirviendo los endpoints. Agregar nuevos endpoints según features.
- **Charts:** Usar [Chart.js](https://www.chartjs.org/) via CDN para gráficas (ligero, sin build step).

## Cómo se Desplegaría

```
[Git push to main]
      │
      ▼
[SSH al servidor / Docker rebuild]
      │
      ▼
[docker compose up -d --build]
      │
      ▼
[Cloudflare Tunnel → público]
```

**Workflow simplificado actual (sin CI/CD):**
1. Editar archivos localmente
2. `git push`
3. En el servidor: `git pull && docker compose up -d --build`

**Workflow futuro (con CI/CD):**
1. `git push` a main
2. GitHub Action hace `ssh deploy` automáticamente
3. Sin intervención manual

## Features por Sprint

### Sprint 1 — Fundación (Actual)

| Feature | Componente | Dificultad |
|---|---|---|
| Categorización de items | Backend + Frontend | Media |
| Grid de categorías con íconos | Frontend | Baja |
| Filtro de oportunidades por categoría | API + Frontend | Baja |
| Badge de categoría en tabla | Frontend | Baja |
| Fix deploy (Dockerización) | Infra | Media |

**UI Mockup Sprint 1 — Sección Categorías:**
```
┌──────────────────────────────────────────────────┐
│  categorías                          ↺ actualizar │
│  resumen por tipo de producto                     │
├──────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│ │ 🔧 Herram.│ │ 💡 Ilumin.│ │ 🍳 Cocina │       │
│ │   1,204   │ │    892    │ │    756    │       │
│ │  23 opps  │ │  15 opps  │ │  31 opps  │       │
│ └───────────┘ └───────────┘ └───────────┘       │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│ │ 🛋 Muebles│ │ 💎 Joyería│ │ 🪙 Monedas│       │
│ │    543    │ │    421    │ │    389    │       │
│ │   8 opps  │ │  12 opps  │ │   5 opps  │       │
│ └───────────┘ └───────────┘ └───────────┘       │
├──────────────────────────────────────────────────┤
│  oportunidades en [Herramientas ▼]               │
│ ┌─────────────────────────────────────────────┐  │
│ │ Lot | Título        | Bid | Retail | Ratio  │  │
│ │ 423 | DEWALT 20V.. | $0  | $399   | 79.8x  │  │
│ │ 891 | Milwaukee..  | $0  | $249   | 49.8x  │  │
│ └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Sprint 2 — Rastreo Inteligente

| Feature | Componente | Dificultad |
|---|---|---|
| Watchlist UI (toggle por categoría) | Full stack | Media |
| Gráfica de distribución de categorías | Frontend (Chart.js) | Baja |
| Historial de precio por item | API + Frontend | Media |
| Filtro combinado: categoría + tiempo + ratio | Frontend | Baja |
| Notificación de "nueva subasta detectada" | Backend + Telegram | Baja |

### Sprint 3 — Experiencia Pro

| Feature | Componente | Dificultad |
|---|---|---|
| Auth con password (o Cloudflare Access) | Backend/Infra | Baja-Media |
| Mobile bottom nav (reemplazar sidebar) | Frontend | Media |
| Búsqueda full-text (FTS5) | Backend + Frontend | Media |
| PWA manifest + service worker | Frontend | Baja |
| Tema de colores por categoría | Frontend | Baja |

## Features para Futuras Iteraciones

| Feature | Sprint | Nota |
|---|---|---|
| Multi-sitio (otras casas de subastas) | 4+ | Plugin system para parsers |
| Imágenes de productos | 4+ | Scrapear thumbnails |
| Telegram bot interactivo | 4+ | `/watch electronics`, `/stats` |
| Score de calidad de oportunidad | 4+ | ML-lite: ratio + categoría + historial |
| Export a CSV/Excel | 3-4 | Quick win para análisis offline |
| Email alerts (además de/en vez de Telegram) | 4+ | SendGrid o similar |
| Supabase migration | 5+ | Real-time, multi-user, cloud DB |
| Auto-bid | 6+ | Requiere research legal + API del sitio |

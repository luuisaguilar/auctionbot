# ADR-004: Vanilla HTML/JS/CSS para el Dashboard (sin framework)

- **Fecha:** 2026-03-30
- **Estado:** Aceptada
- **Contexto:** El dashboard es una herramienta interna de monitoreo. Opciones: React/Next.js, Vue, vanilla HTML.
- **Decisión:** SPA en un solo archivo `index.html` con vanilla JavaScript y CSS custom.
- **Razones:**
  - Cero tooling (no hay build step, no hay npm, no hay bundler)
  - Servido directamente por Flask como static file
  - Lo suficientemente simple para 3-4 vistas
  - Fácil de deployar — solo copiar el archivo
- **Consecuencias:**
  - Sin component system — el código JS crece linealmente con cada feature
  - Sin state management — todo se re-fetcha del API
  - Para >5 vistas complejas, considerar migrar a un framework ligero (Preact, Alpine.js, o Vite+vanilla)
- **Nota de futuro:** Si el dashboard crece a >10 vistas o necesita auth, considerar migrar a un mini-framework. Ver Sprint 3 en BACKLOG.md.

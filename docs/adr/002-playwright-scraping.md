# ADR-002: Playwright para Scraping (en vez de requests/API directa)

- **Fecha:** 2026-03-22
- **Estado:** Aceptada
- **Contexto:** Auction Nation es una SPA pesada en JavaScript. Los datos de items se cargan dinámicamente via XHR POST a un endpoint `getitems`. Opciones: requests + reverse-engineer API, Selenium, Playwright.
- **Decisión:** Playwright (Python) con Chromium headless + interceptación de network responses.
- **Razones:**
  - La SPA construye los parámetros del POST dinámicamente (cookies, tokens de sesión internos)
  - Playwright permite `page.on("response")` para interceptar las responses de `getitems` sin tener que replicar la lógica de autenticación
  - Más robusto ante cambios del frontend — no dependemos de reverse-engineer del API
  - La paginación se activa por scroll/click en "Next" — Playwright maneja esto nativamente
- **Consecuencias:**
  - Cada corrida abre un browser real (~200MB RAM)
  - Más lento que requests directos (~30s por subasta vs ~2s)
  - Necesita `playwright install chromium` en cada deploy
  - En Docker, requiere imagen base con dependencias de Chromium

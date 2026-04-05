# ADR-001: SQLite como Base de Datos Principal

- **Fecha:** 2026-03-22
- **Estado:** Aceptada
- **Contexto:** Necesitamos persistir datos de items scrapeados, historial de corridas y alertas enviadas. Opciones: SQLite, PostgreSQL, Supabase, archivos JSON.
- **Decisión:** SQLite con WAL mode.
- **Razones:**
  - Cero dependencias externas — un solo archivo `.db`
  - Perfecto para volúmenes actuales (~400k rows, ~210MB)
  - WAL mode permite lecturas concurrentes (dashboard + scraper)
  - Si necesitamos migrar, el patrón Repository (`ab055_repository.py`) abstrae la implementación
- **Consecuencias:**
  - Sin concurrencia de escrituras pesada (solo 1 scraper escribe a la vez)
  - La DB vive en el filesystem del servidor — sin backups automáticos
  - Para escalar a >1M rows o multi-usuario, migrar a Supabase/PostgreSQL

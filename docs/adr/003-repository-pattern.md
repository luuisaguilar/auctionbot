# ADR-003: Repository Pattern para Abstracción de DB

- **Fecha:** 2026-03-30
- **Estado:** Aceptada
- **Contexto:** Queremos poder migrar de SQLite a Supabase (o cualquier otra DB) sin tocar los scripts principales.
- **Decisión:** `ab055_repository.py` expone una clase `AuctionBotDB` que delega a `ab055_sqlite.py`. Para migrar, solo se cambia el import.
- **Razones:**
  - Separación limpia entre lógica de negocio (scraper, alertas) e implementación de persistencia
  - Los scripts `ab053_v2`, `ab054` solo importan `AuctionBotDB` — no saben si la DB es SQLite o un API remoto
  - Facilita testing con mocks
- **Consecuencias:**
  - Doble capa de indirección: `ab053_v2 → repository → sqlite`
  - Cualquier nueva query debe agregarse en ambos archivos
  - La interfaz crece con el tiempo — mantenerla sincronizada requiere disciplina

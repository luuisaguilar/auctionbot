# ADR-005: Categorización por Keywords (en vez de IA/ML)

- **Fecha:** 2026-04-05
- **Estado:** Propuesta (pendiente de implementación)
- **Contexto:** Queremos categorizar ~5,500 títulos únicos de productos. Opciones: (A) Keywords/regex, (B) LLM API (Gemini/OpenAI), (C) Modelo ML local.
- **Decisión:** Opción A — Keywords/regex con fallback a "Otro".
- **Razones:**
  - Los productos de Auction Nation tienen patrones muy consistentes (marcas conocidas, tipos de producto en inglés claro)
  - Los nombres de subasta (`auction_title`) ya contienen categorías explícitas ("Tools", "Kitchen and Bath", "Furniture", etc.)
  - Cero costo operativo — sin API calls
  - Latencia insignificante — regex pura sobre strings
  - Fácil de depurar y ajustar
- **Consecuencias:**
  - Algunos productos pueden caer en "Otro" si no matchean ningún patrón
  - Necesita mantenimiento manual: agregar keywords cuando aparezcan nuevas categorías
  - Para >50k títulos únicos o productos más ambiguos, reconsiderar LLM batch classification
- **Categorías propuestas:** Electrónica, Herramientas, Iluminación, Cocina y Baño, Muebles, Hogar y Decoración, Puertas y Pisos, Materiales de Construcción, Jardín y Exterior, Joyería, Monedas y Coleccionables, Plomería, Otro

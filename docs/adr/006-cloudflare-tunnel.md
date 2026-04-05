# ADR-006: Cloudflare Tunnel para Deploy Público

- **Fecha:** 2026-03-25
- **Estado:** Aceptada (implementada, actualmente caída)
- **Contexto:** Queremos exponer el dashboard en internet sin abrir puertos ni configurar NAT/firewall.
- **Decisión:** Cloudflare Tunnel (cloudflared) conectando el servidor origen con `auctionbot.luisaguilaraguila.com`.
- **Razones:**
  - No requiere IP pública fija ni port forwarding
  - HTTPS automático via Cloudflare
  - Integración con Zero Trust Access (futuro: proteger con email login)
  - El dominio `luisaguilaraguila.com` ya está en Cloudflare
- **Consecuencias:**
  - Dependencia de infraestructura Cloudflare
  - Si el origen está caído, Cloudflare muestra 502 (situación actual)
  - El tunnel agent (`cloudflared`) debe correr como servicio/contenedor en el servidor
  - Para alta disponibilidad, considerar Docker + `restart: always`

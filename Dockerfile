# ── AuctionBot Dashboard — Dockerfile ────────────────────────────────────────
# Imagen ligera para el servidor Flask (ab056_dashboard.py)
# Playwright NO está aquí — el scheduler tiene su propia imagen.

FROM python:3.12-slim

# Metadatos
LABEL org.opencontainers.image.title="AuctionBot Dashboard"
LABEL org.opencontainers.image.description="Flask API server for AuctionBot"

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/auctionbot

# Copiar sólo lo necesario para el dashboard
COPY app/env_loader.py        app/
COPY app/ab055_sqlite.py      app/
COPY app/ab055_repository.py  app/
COPY app/ab057_categorizer.py app/
COPY app/ab056_dashboard.py   app/

# Sin Playwright — sólo Flask
RUN pip install --no-cache-dir flask==3.1.0

# El volumen de datos se monta externamente (ver docker-compose.yml)
# La DB no se incluye en la imagen

EXPOSE 8080

# Healthcheck: verifica que Flask responde
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/stats')" || exit 1

# Correr desde la raíz del proyecto para que las rutas relativas funcionen
WORKDIR /opt/auctionbot
CMD ["python", "app/ab056_dashboard.py", "--port", "8080"]

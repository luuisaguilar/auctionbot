---
description: Deploy completo - Docker en servidor + Cloudflare Pages para el frontend
---

# Deploy AuctionBot

## Prerequisitos
- Acceso SSH al servidor
- Docker y Docker Compose instalados en el servidor
- Repo en GitHub
- Dominio en Cloudflare con el Tunnel activo

---

## Paso 1: Verificar/Instalar Docker en el servidor

```bash
ssh usuario@servidor

# Verificar si está instalado
docker --version
docker compose version

# Si no está instalado (Ubuntu/Debian):
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

---

## Paso 2: Clonar/Actualizar el repo en el servidor

```bash
# Primera vez
cd /opt
sudo git clone <repo-url> auctionbot
sudo chown -R $USER:$USER /opt/auctionbot
cd /opt/auctionbot

# Actualizar (siguiente veces)
git pull
```

---

## Paso 3: Configurar .env en el servidor

```bash
cp .env.example .env
nano .env
```

Llenar con los valores reales:
```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
TUNNEL_TOKEN=xxx          # desde Cloudflare Zero Trust → Tunnels
AUCTIONBOT_DB_PATH=/opt/auctionbot/data/auctionbot.db
```

---

## Paso 4: Asegurarse de que la DB existe

```bash
mkdir -p data
# Si la DB ya existía en el servidor, solo verificar que está en data/
ls -lh data/auctionbot.db
```

---

## Paso 5: Levantar con Docker Compose

```bash
# Primera vez (build + start)
docker compose up -d --build

# Ver logs en vivo
docker compose logs -f

# Verificar que los 3 servicios están healthy
docker compose ps
```

Salida esperada:
```
NAME                    STATUS          PORTS
auctionbot-dashboard    healthy         127.0.0.1:8080->8080/tcp
auctionbot-scheduler    running
auctionbot-tunnel       running
```

---

## Paso 6: Configurar Cloudflare Pages (solo primera vez)

1. Ir a [Cloudflare Pages](https://pages.cloudflare.com/)
2. **Create project** → Connect to Git → Seleccionar el repo de AuctionBot
3. Configurar build:
   - **Framework preset**: None
   - **Build command**: *(dejar vacío)*
   - **Build output directory**: `dashboard`
4. Deploy → Cloudflare asigna URL tipo `auctionbot-xxx.pages.dev`
5. **Custom domain**: Agregar `auctionbot.luisaguilaraguila.com`
   - Esto reemplazará/compartirá el dominio con el Tunnel
   - Opción A: Usar subdominio diferente para el frontend, ej: `app.luisaguilaraguila.com`
   - Opción B: En Cloudflare, el Tunnel maneja `/api/*` y Pages sirve `/`

---

## Paso 7: Verificar

```bash
# API desde el servidor
curl http://localhost:8080/api/stats

# API pública
curl https://auctionbot.luisaguilaraguila.com/api/stats

# Frontend (en browser)
# Abrir https://auctionbot.luisaguilaraguila.com o el URL de Cloudflare Pages
```

---

## Comandos útiles del día a día

```bash
# Ver estado
docker compose ps

# Reiniciar solo el dashboard (sin rebuild)
docker compose restart dashboard

# Actualizar código y redeploy
git pull
docker compose up -d --build dashboard

# Ver logs del scheduler (scraper)
docker compose logs -f scheduler

# Detener todo
docker compose down

# Detener y eliminar imágenes (rebuild total)
docker compose down --rmi all
docker compose up -d --build
```

---

// turbo
## Paso [AUTO] Verificar puertos en uso
```bash
ss -tlnp | grep 8080
```

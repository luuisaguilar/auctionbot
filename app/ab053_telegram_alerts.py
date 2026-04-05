"""
AB-053 — Telegram Alerts: Auction Nation
=========================================
Integra el scraper de bidgallery con alertas de Telegram.

Flujo:
  1. Carga subastas activas desde la landing
  2. Scrape completo con paginación
  3. Filtra oportunidades: current_bid == 0 + tiempo restante <= umbral
  4. Deduplica contra alertas ya enviadas en esta sesión
  5. Envía alerta Telegram por cada oportunidad nueva
  6. Guarda registro de alertas enviadas

Uso:
    python ab053_telegram_alerts.py

    # Modo prueba (no envía Telegram, solo muestra qué enviaría):
    python ab053_telegram_alerts.py --dry-run

    # Cambiar umbral de tiempo:
    python ab053_telegram_alerts.py --max-minutes 45
"""

import argparse
import asyncio
import json
import os
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Response


# ──────────────────────────────────────────────
# CONFIG — edita estos valores
# ──────────────────────────────────────────────

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LANDING_URL     = "https://www.auctionnation.com/#all-auctions"
ARTIFACTS_DIR   = Path("artifacts/ab053")
ALERTS_LOG      = ARTIFACTS_DIR / "alerts_sent.json"

# Filtros por defecto (sobreescribibles por CLI)
MAX_MINUTES_DEFAULT = 60    # alertar si cierra en <= N minutos
MAX_AUCTIONS        = 10    # subastas a revisar por corrida
DELAY_PAGE_MS       = 6000
DELAY_SCROLL_MS     = 1500
GETITEMS_TIMEOUT    = 20000

BROWSER_HEADERS = {
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
}


# ──────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────

def send_telegram(message: str, dry_run: bool = False) -> bool:
    """Envía un mensaje de Telegram. Retorna True si fue exitoso."""
    if dry_run:
        print(f"\n  [DRY-RUN] Mensaje que se enviaría:\n{message}\n")
        return True

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ✗ TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados")
        return False

    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ✗ Telegram HTTP error {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")
        return False


def format_alert(item: dict) -> str:
    """Formatea un item como mensaje Telegram."""
    mins  = item["time_remaining_seconds"] // 60
    secs  = item["time_remaining_seconds"] % 60
    tiempo = f"{mins}m {secs}s"

    condition = item.get("condition", "").strip()
    condition_line = f"\n🔍 <b>Condición:</b> {condition}" if condition else ""

    return (
        f"🎯 <b>OPORTUNIDAD — BID $0.00</b>\n"
        f"\n"
        f"📦 <b>Lot {item['lot_number']}:</b> {item['title']}\n"
        f"\n"
        f"💰 <b>Min bid:</b> ${item['min_bid']:.2f}\n"
        f"⏰ <b>Cierra en:</b> {tiempo} ({item['end_time_display']})\n"
        f"🏷 <b>Subasta:</b> {item.get('auction_title', item['auction_id'])}"
        f"{condition_line}\n"
        f"\n"
        f"🔗 <a href=\"{item['url']}\">Ver item</a>"
    )


def format_summary(sent: int, total_opps: int, total_items: int,
                   auctions: int, max_minutes: int) -> str:
    """Mensaje de resumen al final de la corrida."""
    return (
        f"📊 <b>Resumen de corrida</b>\n"
        f"\n"
        f"🏪 Subastas revisadas: {auctions}\n"
        f"📋 Items escaneados: {total_items}\n"
        f"🎯 Oportunidades bid=$0: {total_opps}\n"
        f"📬 Alertas enviadas: {sent} (filtro: ≤{max_minutes}min)\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


# ──────────────────────────────────────────────
# DEDUPLICACIÓN
# ──────────────────────────────────────────────

def load_alerts_log() -> dict:
    """Carga el registro de alertas enviadas."""
    if ALERTS_LOG.exists():
        try:
            return json.loads(ALERTS_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sent": {}}


def save_alerts_log(log: dict):
    ALERTS_LOG.write_text(
        json.dumps(log, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def make_dedup_key(item: dict) -> str:
    """Clave única por item. Mismo lot en misma subasta = mismo key."""
    return f"{item['auction_id']}:{item['lot_number']}"


def already_sent(item: dict, log: dict, max_minutes: int) -> bool:
    """
    Retorna True si ya se envió alerta para este item recientemente.
    No re-alerta si fue enviado hace menos de max_minutes * 2.
    """
    key = make_dedup_key(item)
    if key not in log["sent"]:
        return False
    last_sent_ts = log["sent"][key]["timestamp"]
    last_sent = datetime.fromisoformat(last_sent_ts)
    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - last_sent).total_seconds() / 60
    # no re-alertar si fue enviado hace menos de 2x el umbral de tiempo
    return elapsed_minutes < (max_minutes * 2)


def mark_sent(item: dict, log: dict):
    key = make_dedup_key(item)
    log["sent"][key] = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "title":      item["title"][:60],
        "auction_id": item["auction_id"],
        "lot_number": item["lot_number"],
    }


# ──────────────────────────────────────────────
# PARSERS (mismo código que ab052)
# ──────────────────────────────────────────────

def parse_price(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_condition_from_extra_info(extra_info: str) -> str:
    if not extra_info:
        return ""
    text = re.sub(r"<[^>]+>", " ", extra_info)
    return re.sub(r"\s+", " ", text).strip()


def extract_items_from_page(page_data: dict, auction_id: str) -> list[dict]:
    now = datetime.now(timezone.utc).timestamp()
    items = []
    for raw in page_data.get("items", []):
        if not isinstance(raw, dict):
            continue
        end_time_raw = raw.get("end_time") or raw.get("ends")
        try:
            end_unix = float(end_time_raw) if end_time_raw else None
            time_remaining_seconds = max(0, int(end_unix - now)) if end_unix else -1
        except (ValueError, TypeError):
            time_remaining_seconds = -1

        current_bid = parse_price(raw.get("current_bid", 0))
        min_bid     = parse_price(raw.get("minimum_bid") or raw.get("starting_bid") or 0)

        item_url = raw.get("item_url", "")
        if item_url and not item_url.startswith("http"):
            item_url = f"https://online.auctionnation.com{item_url}"

        items.append({
            "auction_id":             auction_id,
            "item_id":                str(raw.get("id", "")),
            "lot_number":             str(raw.get("lot_number", "")),
            "title":                  str(raw.get("title", "")).strip(),
            "current_bid":            current_bid,
            "min_bid":                min_bid,
            "bid_count":              int(raw.get("bid_count") or 0),
            "high_bidder":            raw.get("high_bidder"),
            "end_time_unix":          end_unix if end_time_raw else None,
            "end_time_display":       str(raw.get("display_end_time", "")),
            "time_remaining_seconds": time_remaining_seconds,
            "condition":              parse_condition_from_extra_info(raw.get("extra_info", "")),
            "url":                    item_url,
            "auction_title":          str(raw.get("auction_title", "")),
            "is_opportunity":         current_bid == 0.0,
        })
    return items


def extract_items_from_response(data, auction_id: str) -> tuple[list, dict]:
    if isinstance(data, dict) and "data" in data:
        page_data = data["data"]
    elif isinstance(data, dict) and "items" in data:
        page_data = data
    else:
        return [], {}

    pagination = {
        "total":       int(page_data.get("total", 0)),
        "perpage":     int(page_data.get("perpage", 40)),
        "page":        int(page_data.get("page", 1)),
        "total_pages": int(page_data.get("total_pages", 1)),
    }
    return extract_items_from_page(page_data, auction_id), pagination


# ──────────────────────────────────────────────
# SCRAPER
# ──────────────────────────────────────────────

async def scrape_auction(context, auction_id: str) -> list[dict]:
    """Retorna lista completa de items de una subasta."""
    bidgallery_url = f"https://online.auctionnation.com//auction/{auction_id}/bidgallery/"

    all_getitems   = []
    getitems_ready = asyncio.get_event_loop().create_future()
    page           = await context.new_page()

    async def on_response(response: Response):
        if "getitems" in response.url:
            try:
                data = json.loads(await response.body())
                all_getitems.append({"url": response.url, "status": response.status, "data": data})
                if not getitems_ready.done():
                    getitems_ready.set_result(True)
            except Exception as e:
                if not getitems_ready.done():
                    getitems_ready.set_exception(e)

    page.on("response", on_response)

    try:
        await page.goto(bidgallery_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        await asyncio.wait_for(asyncio.shield(getitems_ready), timeout=GETITEMS_TIMEOUT / 1000)

        p1 = all_getitems[0]
        items_p1, pagination = extract_items_from_response(p1["data"], auction_id)
        total_pages = pagination.get("total_pages", 1)
        all_items   = list(items_p1)
        pages_got   = 1

        if total_pages > 1:
            prev = 1
            attempts = 0
            while pages_got < total_pages and attempts < total_pages * 4:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                try:
                    btn = await page.query_selector(
                        "a.next, button.next, [aria-label='Next'], .pagination-next, li.next a"
                    )
                    if btn:
                        await btn.click()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass

                if len(all_getitems) > prev:
                    for resp in all_getitems[prev:]:
                        items_pn, _ = extract_items_from_response(resp["data"], auction_id)
                        if items_pn:
                            all_items += items_pn
                            pages_got += 1
                    prev = len(all_getitems)
                else:
                    await page.wait_for_timeout(1500)
                attempts += 1

        return all_items

    except asyncio.TimeoutError:
        print(f"    ✗ getitems timeout en subasta {auction_id}")
        return []
    except Exception as e:
        print(f"    ✗ Error en subasta {auction_id}: {e}")
        return []
    finally:
        await page.close()


# ──────────────────────────────────────────────
# RUNNER PRINCIPAL
# ──────────────────────────────────────────────

async def run(max_minutes: int, dry_run: bool):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"AB-053 — AuctionBot Telegram Alerts")
    print(f"{'='*60}")
    print(f"Filtro tiempo:  <= {max_minutes} minutos")
    print(f"Max subastas:   {MAX_AUCTIONS}")
    print(f"Dry-run:        {'SÍ — no se envían mensajes' if dry_run else 'NO — enviando real'}")
    if not TELEGRAM_CHAT_ID and not dry_run:
        print(f"\n  ⚠️  TELEGRAM_CHAT_ID está vacío. Configúralo en las variables de entorno.")
        if TELEGRAM_TOKEN:
            print(f"     Puedes obtenerlo en:")
            print(f"     https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates")
            print(f"     (envíale un mensaje al bot primero)\n")
        else:
            print("     También necesitas definir TELEGRAM_BOT_TOKEN.\n")
        return

    alerts_log = load_alerts_log()
    print(f"Alertas previas en log: {len(alerts_log['sent'])}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/Phoenix",
            extra_http_headers=BROWSER_HEADERS,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )

        # ── LANDING ──────────────────────────────────────────────
        print(f"\n[1/3] Detectando subastas activas...")
        page = await context.new_page()

        try:
            await page.goto(LANDING_URL, wait_until="networkidle", timeout=40000)
        except Exception:
            await page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=30000)

        await page.wait_for_timeout(DELAY_PAGE_MS)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(DELAY_SCROLL_MS)

        landing_html    = await page.content()
        auction_pattern = re.compile(r"online\.auctionnation\.com/+auction/(\d+)", re.IGNORECASE)
        seen            = set()
        auction_ids     = []

        links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        for link in links:
            m = auction_pattern.search(link)
            if m:
                aid = m.group(1)
                if aid not in seen:
                    seen.add(aid)
                    auction_ids.append(aid)

        if not auction_ids:
            for m in auction_pattern.finditer(landing_html):
                aid = m.group(1)
                if aid not in seen:
                    seen.add(aid)
                    auction_ids.append(aid)

        await page.close()
        print(f"  ✓ {len(auction_ids)} subastas detectadas")

        if not auction_ids:
            print("  ✗ No hay subastas. Abortando.")
            await browser.close()
            return

        # ── SCRAPING ─────────────────────────────────────────────
        targets    = auction_ids[:MAX_AUCTIONS]
        all_items  = []
        max_secs   = max_minutes * 60

        print(f"\n[2/3] Scrapeando {len(targets)} subasta(s)...")

        for aid in targets:
            print(f"  → {aid}", end=" ", flush=True)
            items = await scrape_auction(context, aid)
            opps  = [i for i in items if i["is_opportunity"]]
            urgent = [i for i in opps
                      if 0 <= i["time_remaining_seconds"] <= max_secs]
            all_items += items
            print(f"— {len(items)} items | {len(opps)} opp | {len(urgent)} urgentes")
            await asyncio.sleep(4)

        await browser.close()

    # ── ALERTAS ──────────────────────────────────────────────────
    print(f"\n[3/3] Enviando alertas...")

    opportunities = [i for i in all_items if i["is_opportunity"]]
    urgent_opps   = [
        i for i in opportunities
        if 0 <= i["time_remaining_seconds"] <= max_secs
    ]
    # ordenar por tiempo restante ascendente (más urgentes primero)
    urgent_opps.sort(key=lambda x: x["time_remaining_seconds"])

    print(f"  Items totales:       {len(all_items)}")
    print(f"  Oportunidades bid=0: {len(opportunities)}")
    print(f"  Urgentes (<={max_minutes}min): {len(urgent_opps)}")

    sent_count    = 0
    skipped_dedup = 0

    for item in urgent_opps:
        if already_sent(item, alerts_log, max_minutes):
            skipped_dedup += 1
            continue

        message = format_alert(item)
        ok      = send_telegram(message, dry_run=dry_run)

        if ok:
            mark_sent(item, alerts_log)
            sent_count += 1
            mins = item["time_remaining_seconds"] // 60
            print(f"  ✓ Enviada: Lot {item['lot_number']} — {item['title'][:45]} ({mins}min)")
        else:
            print(f"  ✗ Falló:   Lot {item['lot_number']} — {item['title'][:45]}")

        await asyncio.sleep(0.3)  # rate limit Telegram: ~30 msg/seg

    # guardar log de alertas
    save_alerts_log(alerts_log)

    # resumen final
    if sent_count > 0 or dry_run:
        summary_msg = format_summary(
            sent=sent_count,
            total_opps=len(opportunities),
            total_items=len(all_items),
            auctions=len(targets),
            max_minutes=max_minutes,
        )
        send_telegram(summary_msg, dry_run=dry_run)

    print(f"\n{'='*60}")
    print(f"  Enviadas:     {sent_count}")
    print(f"  Deduplicadas: {skipped_dedup}")
    print(f"  Log guardado: {ALERTS_LOG}")
    print(f"{'='*60}\n")


# ──────────────────────────────────────────────
# ENTRYPOINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuctionBot Telegram Alerts")
    parser.add_argument(
        "--max-minutes", type=int, default=MAX_MINUTES_DEFAULT,
        help=f"Alertar items que cierran en <= N minutos (default: {MAX_MINUTES_DEFAULT})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No enviar Telegram, solo mostrar qué se enviaría"
    )
    args = parser.parse_args()
    asyncio.run(run(max_minutes=args.max_minutes, dry_run=args.dry_run))

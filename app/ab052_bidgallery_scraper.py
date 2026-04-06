"""
AB-052 — BidGallery Scraper: Auction Nation
============================================
Hallazgo de AB-051:
  - La URL correcta del detalle es /auction/{id}/bidgallery/
  - La request que devuelve los items es 'getitems' (XHR ~295 kB)
  - No requiere login ni tokens especiales
  - El {"status":"invalid"} en AB-050 era por navegar a /auction/{id} sin el sufijo

Objetivo de este script:
  1. Abrir la landing y detectar subastas activas
  2. Por cada subasta, navegar a /auction/{id}/bidgallery/
  3. Interceptar la response de 'getitems'
  4. Parsear los items: title, current_bid, min_bid, time_remaining, url
  5. Filtrar oportunidades: current_bid == 0
  6. Guardar resultados en artifacts/ab052/

Uso:
    python -m playwright install chromium   (solo la primera vez)
    python ab052_bidgallery_scraper.py

Salida:
    artifacts/ab052/
    ├── summary.json          ← resumen de la corrida
    ├── raw_getitems_{id}.json ← response cruda de getitems por subasta
    ├── items_{id}.json        ← items parseados por subasta
    ├── opportunities.json     ← items con current_bid == 0
    ├── detail_{id}.png        ← screenshot de cada subasta
    └── detail_{id}.html       ← HTML de cada subasta (para debug)
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Route, Response


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

LANDING_URL        = "https://www.auctionnation.com/#all-auctions"
ARTIFACTS_DIR      = Path("artifacts/ab052")
MAX_AUCTIONS       = 3      # cuántas subastas procesar por corrida
DELAY_PAGE_MS      = 6000   # espera tras cargar página (más tiempo para JS)
DELAY_SCROLL_MS    = 1500   # espera entre scrolls
GETITEMS_TIMEOUT   = 20000  # ms máximos esperando la response de getitems

BROWSER_HEADERS = {
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Upgrade-Insecure-Requests": "1",
}


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_price(value) -> float:
    """Convierte cualquier representación de precio a float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_seconds(value) -> int:
    """
    Convierte tiempo restante a segundos.
    Acepta: número (segundos), string '6H 19M 29S', o timestamp Unix.
    """
    if value is None:
        return -1
    if isinstance(value, (int, float)):
        # si es un número grande, probablemente es timestamp Unix
        if value > 86400 * 365:
            delta = value - datetime.now(timezone.utc).timestamp()
            return max(0, int(delta))
        return int(value)
    # formato '6H 19M 29S' o '6h 19m 29s'
    s = str(value).upper()
    total = 0
    for match in re.finditer(r"(\d+)\s*([DHMS])", s):
        n, unit = int(match.group(1)), match.group(2)
        total += n * {"D": 86400, "H": 3600, "M": 60, "S": 1}[unit]
    return total if total > 0 else -1


def parse_condition_from_extra_info(extra_info: str) -> str:
    """Extrae texto de condición del HTML de extra_info."""
    if not extra_info:
        return ""
    # eliminar tags HTML y dejar solo el texto
    text = re.sub(r"<[^>]+>", " ", extra_info)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_items_from_page(page_data: dict, auction_id: str) -> list[dict]:
    """
    Extrae items de una página del JSON de getitems.
    Estructura confirmada de Auction Nation:
      response.data.items[] con campos:
        id, lot_number, title, current_bid, minimum_bid, starting_bid,
        end_time (Unix timestamp), item_url, increment, extra_info, high_bidder
    """
    now = datetime.now(timezone.utc).timestamp()
    raw_items = page_data.get("items", [])
    items = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        # tiempo restante: end_time es Unix timestamp
        end_time_raw = raw.get("end_time") or raw.get("ends")
        try:
            end_unix = float(end_time_raw) if end_time_raw else None
            time_remaining_seconds = max(0, int(end_unix - now)) if end_unix else -1
        except (ValueError, TypeError):
            time_remaining_seconds = -1

        current_bid  = parse_price(raw.get("current_bid", 0))
        min_bid      = parse_price(raw.get("minimum_bid") or raw.get("starting_bid") or 0)
        bid_increment_raw = raw.get("increment", 0)

        # increment es un ID numérico que referencia increments_array, no el valor directo
        # guardamos el raw para referencia pero no lo usamos como precio
        bid_increment = parse_price(bid_increment_raw) if str(bid_increment_raw).replace(".", "").isdigit() else 0

        item_url = raw.get("item_url", "")
        if item_url and not item_url.startswith("http"):
            item_url = f"https://online.auctionnation.com{item_url}"

        condition = parse_condition_from_extra_info(raw.get("extra_info", ""))

        items.append({
            "auction_id":             auction_id,
            "item_id":                str(raw.get("id", "")),
            "lot_number":             str(raw.get("lot_number", "")),
            "title":                  str(raw.get("title", "")).strip(),
            "current_bid":            current_bid,
            "min_bid":                min_bid,
            "bid_increment_id":       str(bid_increment_raw),
            "bid_count":              int(raw.get("bid_count") or 0),
            "high_bidder":            raw.get("high_bidder"),
            "end_time_unix":          end_unix if end_time_raw else None,
            "end_time_display":       str(raw.get("display_end_time", "")),
            "time_remaining_seconds": time_remaining_seconds,
            "condition":              condition,
            "url":                    item_url,
            "auction_title":          str(raw.get("auction_title", "")),
            "state":                  str(raw.get("state", "")),
            "is_opportunity":         current_bid == 0.0,
        })

    return items


def extract_items_from_response(data: dict | list, auction_id: str) -> tuple[list[dict], dict]:
    """
    Extrae items y metadatos de paginación del response de getitems.
    Retorna (items, pagination_info).
    """
    # el response viene envuelto: {"url":..., "status":..., "data":{...}}
    if isinstance(data, dict) and "data" in data:
        page_data = data["data"]
    elif isinstance(data, dict) and "items" in data:
        page_data = data
    elif isinstance(data, list):
        return [extract_items_from_page({"items": data}, auction_id)], {}
    else:
        return [], {}

    pagination = {
        "total":       int(page_data.get("total", 0)),
        "perpage":     int(page_data.get("perpage", 40)),
        "page":        int(page_data.get("page", 1)),
        "total_pages": int(page_data.get("total_pages", 1)),
    }

    items = extract_items_from_page(page_data, auction_id)
    return items, pagination


# ──────────────────────────────────────────────
# SCRAPER PRINCIPAL
# ──────────────────────────────────────────────

async def scrape_auction(context, auction_id: str, auction_url: str) -> dict:
    """
    Navega a /auction/{id}/bidgallery/, intercepta getitems, parsea y retorna items.
    """
    bidgallery_url = f"https://online.auctionnation.com//auction/{auction_id}/bidgallery/"
    print(f"\n  → Subasta {auction_id}")
    print(f"    URL: {bidgallery_url}")

    result = {
        "auction_id":    auction_id,
        "auction_url":   auction_url,
        "bidgallery_url": bidgallery_url,
        "timestamp":     ts(),
        "status":        "pending",
        "getitems_captured": False,
        "items_count":   0,
        "opportunities_count": 0,
        "items":         [],
        "error":         None,
    }

    page = await context.new_page()

    # colector de TODOS los getitems que se disparen (p1, p2, p3...)
    all_getitems_responses = []
    getitems_future = asyncio.get_event_loop().create_future()

    async def handle_response(response: Response):
        if "getitems" in response.url:
            try:
                body = await response.body()
                data = json.loads(body)
                all_getitems_responses.append({
                    "url":    response.url,
                    "status": response.status,
                    "data":   data,
                })
                # resolver el future de p1 con la primera respuesta
                if not getitems_future.done():
                    getitems_future.set_result(all_getitems_responses[0])
            except Exception as e:
                if not getitems_future.done():
                    getitems_future.set_exception(e)

    page.on("response", handle_response)

    try:
        await page.goto(bidgallery_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # esperar que se dispare getitems p1
        try:
            await asyncio.wait_for(
                asyncio.shield(getitems_future),
                timeout=GETITEMS_TIMEOUT / 1000
            )
        except asyncio.TimeoutError:
            result["status"] = "getitems_timeout"
            print(f"    ✗ getitems p1 no se disparó en {GETITEMS_TIMEOUT}ms")
            await page.close()
            return result

        result["getitems_captured"] = True
        p1 = all_getitems_responses[0]
        print(f"    ✓ getitems p1 capturado (HTTP {p1['status']})")

        # guardar raw p1
        (ARTIFACTS_DIR / f"raw_getitems_{auction_id}_p1.json").write_text(
            json.dumps(p1, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        if not isinstance(p1["data"], (dict, list)):
            result["status"] = "getitems_not_json"
            print(f"    ✗ getitems no devolvió JSON parseable")
            await page.close()
            return result

        items_p1, pagination = extract_items_from_response(p1["data"], auction_id)
        total_pages  = pagination.get("total_pages", 1)
        total_server = pagination.get("total", len(items_p1))
        print(f"      Página 1/{total_pages} — {len(items_p1)} items "
              f"(total servidor: {total_server})")

        # ── PAGINACIÓN: scroll progresivo para disparar p2..N ────
        # El sitio usa infinite scroll o botones de página — al hacer scroll
        # hasta el fondo el browser dispara getitems automáticamente con
        # los parámetros correctos (POST form data con cookies de sesión)
        all_items = list(items_p1)
        pages_collected = 1

        if total_pages > 1:
            # scroll agresivo hasta el fondo para activar todas las páginas
            prev_count = len(all_getitems_responses)
            scroll_attempts = 0
            max_scroll_attempts = total_pages * 4  # intentos máximos

            while pages_collected < total_pages and scroll_attempts < max_scroll_attempts:
                # scroll al fondo de la página
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                # también intentar hacer click en botón "next page" si existe
                try:
                    next_btn = await page.query_selector(
                        "a.next, button.next, [aria-label='Next'], "
                        ".pagination-next, a[rel='next'], "
                        "li.next a, .next-page"
                    )
                    if next_btn:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass

                # ver si llegaron nuevas respuestas de getitems
                new_count = len(all_getitems_responses)
                if new_count > prev_count:
                    for resp in all_getitems_responses[prev_count:new_count]:
                        page_num = pages_collected + 1
                        items_pn, _ = extract_items_from_response(resp["data"], auction_id)
                        if items_pn:
                            all_items += items_pn
                            pages_collected += 1
                            print(f"      Página {pages_collected}/{total_pages} "
                                  f"— {len(items_pn)} items")
                            (ARTIFACTS_DIR / f"raw_getitems_{auction_id}_p{pages_collected}.json").write_text(
                                json.dumps(resp, indent=2, ensure_ascii=False),
                                encoding="utf-8"
                            )
                    prev_count = new_count
                else:
                    # no llegó nada nuevo — esperar un poco más
                    await page.wait_for_timeout(1500)

                scroll_attempts += 1

            if pages_collected < total_pages:
                print(f"      ℹ Solo se obtuvieron {pages_collected}/{total_pages} páginas "
                      f"({len(all_items)}/{total_server} items)")

        result["items"]               = all_items
        result["items_count"]         = len(all_items)
        result["pagination"]          = pagination
        result["opportunities_count"] = sum(1 for i in all_items if i["is_opportunity"])
        result["status"]              = "success"

        (ARTIFACTS_DIR / f"items_{auction_id}.json").write_text(
            json.dumps(all_items, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(f"    ✓ Total items: {len(all_items)} de {total_server}")
        print(f"    ✓ Oportunidades (bid=0): {result['opportunities_count']}")

        opps = [i for i in all_items if i["is_opportunity"]]
        for opp in opps[:3]:
            mins  = opp["time_remaining_seconds"] // 60
            secs  = opp["time_remaining_seconds"] % 60
            tiempo = f"{mins}m {secs}s" if opp["time_remaining_seconds"] >= 0 else "N/A"
            print(f"      🎯 Lot {opp['lot_number']}: {opp['title'][:55]}")
            print(f"         Min bid: ${opp['min_bid']} | "
                  f"Cierre: {opp['end_time_display']} | Restante: {tiempo}")

        # screenshot para debug
        await page.screenshot(
            path=str(ARTIFACTS_DIR / f"detail_{auction_id}.png"),
            full_page=False
        )
        html = await page.content()
        (ARTIFACTS_DIR / f"detail_{auction_id}.html").write_text(html, encoding="utf-8")

    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
        print(f"    ✗ Error: {e}")

    finally:
        await page.close()

    return result


# ──────────────────────────────────────────────
# RUNNER PRINCIPAL
# ──────────────────────────────────────────────

async def run():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = f"ab052-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"\n{'='*60}")
    print(f"AB-052 — BidGallery Scraper")
    print(f"{'='*60}")
    print(f"Run ID:  {run_id}")
    print(f"Inicio:  {ts()}")
    print(f"Max subastas: {MAX_AUCTIONS}")

    summary = {
        "run_id":            run_id,
        "timestamp":         ts(),
        "landing_url":       LANDING_URL,
        "max_auctions":      MAX_AUCTIONS,
        "auctions_found":    [],
        "auctions_scraped":  [],
        "total_items":       0,
        "total_opportunities": 0,
        "opportunities":     [],
        "verdict":           "",
    }

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

        # ── PASO 1: LANDING ──────────────────────────────────────
        print(f"\n[1/3] Cargando landing...")
        page = await context.new_page()

        # capturar la response de auctions/ en la landing
        auctions_future = asyncio.get_event_loop().create_future()

        async def capture_auctions_api(response: Response):
            if "auctions/" in response.url and not auctions_future.done():
                try:
                    body = await response.body()
                    data = json.loads(body)
                    auctions_future.set_result(data)
                except Exception:
                    pass

        page.on("response", capture_auctions_api)

        # esperar JS completo con networkidle
        try:
            await page.goto(LANDING_URL, wait_until="networkidle", timeout=40000)
        except Exception:
            await page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=30000)

        await page.wait_for_timeout(DELAY_PAGE_MS)

        # scroll progresivo para activar lazy load
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(DELAY_SCROLL_MS)

        # guardar landing para diagnóstico
        landing_html = await page.content()
        (ARTIFACTS_DIR / "landing.html").write_text(landing_html, encoding="utf-8")
        await page.screenshot(path=str(ARTIFACTS_DIR / "landing.png"), full_page=False)
        print(f"  landing guardada ({len(landing_html):,} bytes)")

        # El sitio usa doble slash: online.auctionnation.com//auction/{id}
        auction_pattern = re.compile(
            r"online\.auctionnation\.com/+auction/(\d+)", re.IGNORECASE
        )
        seen  = set()
        auction_entries = []

        # Estrategia 1: links del DOM
        links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        for link in links:
            m = auction_pattern.search(link)
            if m:
                aid = m.group(1)
                if aid not in seen:
                    seen.add(aid)
                    auction_entries.append({"id": aid, "url": link, "source": "dom_link"})
        print(f"  Estrategia 1 (links DOM): {len(auction_entries)} encontradas")

        # Estrategia 2: buscar IDs en el HTML completo
        if len(auction_entries) < 3:
            for m in auction_pattern.finditer(landing_html):
                aid = m.group(1)
                if aid not in seen:
                    seen.add(aid)
                    url = f"https://online.auctionnation.com//auction/{aid}"
                    auction_entries.append({"id": aid, "url": url, "source": "html_text"})
            print(f"  Estrategia 2 (texto HTML): {len(auction_entries)} acumuladas")

        # Estrategia 3: capturar de la API auctions/ si se disparó
        if len(auction_entries) < 3:
            try:
                api_data = await asyncio.wait_for(asyncio.shield(auctions_future), timeout=2)
                api_text = json.dumps(api_data)
                for m in re.finditer(r'"(?:auction_id|id|auctionId)"\s*:\s*"?(\d{4,})"?', api_text):
                    aid = m.group(1)
                    if aid not in seen:
                        seen.add(aid)
                        url = f"https://online.auctionnation.com//auction/{aid}"
                        auction_entries.append({"id": aid, "url": url, "source": "api_response"})
                print(f"  Estrategia 3 (API auctions/): {len(auction_entries)} acumuladas")
            except Exception:
                print(f"  Estrategia 3 (API auctions/): no disponible")

        await page.close()

        summary["auctions_found"] = auction_entries[:10]
        print(f"  ✓ {len(auction_entries)} subastas detectadas en total")
        for a in auction_entries[:5]:
            print(f"    · ID {a['id']} ({a['source']}) — {a['url']}")

        if not auction_entries:
            print("\n  ✗ No se detectaron subastas.")
            print("  Revisa artifacts/ab052/landing.html para ver que cargo el browser.")
            summary["verdict"] = "NO_AUCTIONS_FOUND - revisar landing.html"
            await browser.close()
            _save_summary(summary)
            return

        # ── PASO 2: SCRAPING DE SUBASTAS ─────────────────────────
        targets = auction_entries[:MAX_AUCTIONS]
        print(f"\n[2/3] Scrapeando {len(targets)} subasta(s)...")

        all_items = []
        all_opportunities = []

        for auction in targets:
            result = await scrape_auction(context, auction["id"], auction["url"])
            summary["auctions_scraped"].append({
                "auction_id":            result["auction_id"],
                "status":                result["status"],
                "getitems_captured":     result["getitems_captured"],
                "items_count":           result["items_count"],
                "opportunities_count":   result["opportunities_count"],
                "error":                 result["error"],
            })
            all_items        += result["items"]
            all_opportunities += [i for i in result["items"] if i["is_opportunity"]]

            # delay entre subastas
            await asyncio.sleep(4)

        summary["total_items"]        = len(all_items)
        summary["total_opportunities"] = len(all_opportunities)
        summary["opportunities"]       = all_opportunities

        # ── PASO 3: GUARDAR OPORTUNIDADES ────────────────────────
        print(f"\n[3/3] Guardando resultados...")
        opps_path = ARTIFACTS_DIR / "opportunities.json"
        opps_path.write_text(
            json.dumps(all_opportunities, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"  ✓ {len(all_opportunities)} oportunidades guardadas")

        await browser.close()

    # ── VEREDICTO ────────────────────────────────────────────────
    scraped       = summary["auctions_scraped"]
    success_count = sum(1 for a in scraped if a["status"] == "success")
    getitems_ok   = sum(1 for a in scraped if a["getitems_captured"])

    if success_count == len(targets):
        verdict = "SUCCESS: scraping funciona con /bidgallery/ — AB-050 puede cerrarse como resuelto"
    elif getitems_ok > 0:
        verdict = "PARTIAL: getitems capturado en algunas subastas — revisar parsing"
    elif success_count == 0 and getitems_ok == 0:
        verdict = "FAIL: getitems no se capturó — revisar URL o estructura de la subasta"
    else:
        verdict = "MIXED: resultados inconsistentes — revisar por subasta"

    summary["verdict"] = verdict

    print(f"\n{'='*60}")
    print("RESULTADO")
    print(f"{'='*60}")
    print(f"  Subastas procesadas:  {len(scraped)}")
    print(f"  Exitosas:             {success_count}")
    print(f"  getitems capturado:   {getitems_ok}")
    print(f"  Total items:          {summary['total_items']}")
    print(f"  Oportunidades (bid=0): {summary['total_opportunities']}")
    print(f"\n  Veredicto:")
    print(f"  → {verdict}")

    _save_summary(summary)

    print(f"\n{'='*60}")
    print("ARCHIVOS GENERADOS")
    print(f"{'='*60}")
    for f in sorted(ARTIFACTS_DIR.iterdir()):
        print(f"  {f.name:<40} {f.stat().st_size:>8,} bytes")

    print(f"\nFin: {ts()}")


def _save_summary(summary: dict):
    path = ARTIFACTS_DIR / "summary.json"
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\n  summary.json guardado en {ARTIFACTS_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(run())
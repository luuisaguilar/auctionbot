"""
AB-056 — AuctionBot Dashboard Server
======================================
Servidor Flask que expone la DB SQLite via API REST
y sirve el dashboard HTML en http://0.0.0.0:8080

Uso:
    python ab056_dashboard.py
    python ab056_dashboard.py --port 8080
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from env_loader import load_local_env

load_local_env()

# Rutas configurables via .env (ya no hardcodeadas)
_base_dir = Path(__file__).resolve().parents[1]
DB_PATH    = os.environ.get("AUCTIONBOT_DB_PATH", str(_base_dir / "data" / "auctionbot.db"))
STATIC_DIR = Path(os.environ.get("AUCTIONBOT_STATIC_DIR", str(_base_dir / "dashboard")))
PORT_DEFAULT = 8080

# Origen de Cloudflare Pages — actualiza si cambia el dominio del frontend
ALLOWED_ORIGINS = {
    "https://auctionbot.luisaguilaraguila.com",   # dominio principal
    "http://localhost:8080",                        # dev local
    "http://localhost:8085",                        # dev local alternativo
}

app = Flask(__name__, static_folder=str(STATIC_DIR))


@app.after_request
def add_cors(response):
    """Agrega headers CORS para permitir que Cloudflare Pages llame a la API."""
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"]  = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


@app.route("/", methods=["OPTIONS"])
@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path=""):
    """Responde preflight CORS requests."""
    return "", 204


# ── DB helper ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── API endpoints ────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    conn = get_db()
    stats = {}
    stats["total_runs"]    = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    stats["total_items"]   = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    stats["total_alerts"]  = conn.execute("SELECT COUNT(*) FROM alerts WHERE dry_run=0").fetchone()[0]
    stats["opportunities"] = conn.execute("SELECT COUNT(*) FROM items WHERE is_opportunity=1").fetchone()[0]
    stats["with_retail"]   = conn.execute("SELECT COUNT(*) FROM items WHERE retail_price IS NOT NULL").fetchone()[0]
    stats["categorized"]   = conn.execute("SELECT COUNT(*) FROM items WHERE category IS NOT NULL").fetchone()[0]
    conn.close()
    return jsonify(stats)


@app.route("/api/runs")
def api_runs():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, started_at, finished_at, auctions_scraped,
               items_total, opportunities, alerts_sent, dry_run
        FROM runs
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/opportunities")
def api_opportunities():
    conn = get_db()
    now_unix = datetime.now(timezone.utc).timestamp()

    # Filtro opcional por categoría
    category = request.args.get("category")

    base_query = """
        SELECT
            i.item_id,
            i.lot_number,
            i.title,
            i.auction_id,
            i.auction_title,
            i.min_bid,
            i.retail_price,
            ROUND(i.retail_price / NULLIF(i.min_bid, 0), 1) AS ratio,
            i.end_time,
            i.condition_text,
            i.item_url,
            i.category,
            MAX(i.scraped_at) AS last_seen
        FROM items i
        WHERE i.is_opportunity = 1
          AND i.retail_price IS NOT NULL
          AND i.retail_price / NULLIF(i.min_bid, 0) >= 3.0
          AND i.end_time > ?
    """
    params = [now_unix]

    if category:
        base_query += " AND i.category = ?"
        params.append(category)

    base_query += """
        GROUP BY i.item_id, i.auction_id
        ORDER BY ratio DESC
        LIMIT 50
    """

    rows = conn.execute(base_query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if d["end_time"]:
            secs = max(0, int(d["end_time"] - now_unix))
            d["minutes_remaining"] = secs // 60
        else:
            d["minutes_remaining"] = None
        result.append(d)
    return jsonify(result)


@app.route("/api/alerts")
def api_alerts():
    conn = get_db()
    rows = conn.execute("""
        SELECT item_id, auction_id, lot_number, title,
               min_bid, retail_price, minutes_remaining, sent_at, dry_run
        FROM alerts
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/categories")
def api_categories():
    """Retorna conteo de items y oportunidades por categoría."""
    conn = get_db()
    now_unix = datetime.now(timezone.utc).timestamp()
    rows = conn.execute("""
        SELECT
            COALESCE(category, 'Otro') as category,
            COUNT(*) as total_items,
            SUM(CASE WHEN is_opportunity = 1 THEN 1 ELSE 0 END) as total_opps,
            SUM(CASE WHEN is_opportunity = 1 AND end_time > ? THEN 1 ELSE 0 END) as active_opps
        FROM items
        GROUP BY category
        ORDER BY total_items DESC
    """, (now_unix,)).fetchall()
    conn.close()

    # Agregar íconos
    icon_map = {
        "Electrónica": "⚡", "Herramientas": "🔧", "Iluminación": "💡",
        "Cocina y Baño": "🍳", "Muebles": "🛋", "Hogar y Decoración": "🏠",
        "Puertas y Pisos": "🚪", "Materiales de Construcción": "🧱",
        "Jardín y Exterior": "🌿", "Joyería": "💎",
        "Monedas y Coleccionables": "🪙", "Plomería": "🔩", "Otro": "📦",
    }

    result = []
    for r in rows:
        d = dict(r)
        d["icon"] = icon_map.get(d["category"], "📦")
        result.append(d)
    return jsonify(result)


# ── Serve dashboard HTML ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuctionBot Dashboard")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    args = parser.parse_args()

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ AuctionBot Dashboard → http://0.0.0.0:{args.port}")
    print(f"  DB: {DB_PATH}")
    print(f"  Static: {STATIC_DIR}")
    app.run(host="0.0.0.0", port=args.port, debug=False)

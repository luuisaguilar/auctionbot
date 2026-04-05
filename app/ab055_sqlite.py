"""
AB-055 — SQLite Implementation
Implementación concreta de la base de datos usando SQLite.
No llamar directamente desde los scripts — usar ab055_repository.py
"""

import sqlite3
import os
import re
from datetime import datetime
from typing import Optional

DB_PATH = os.environ.get("AUCTIONBOT_DB_PATH", "/opt/auctionbot/data/auctionbot.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Escrituras concurrentes seguras
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crea las tablas si no existen. Idempotente — seguro correr múltiples veces."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at       TEXT NOT NULL,
                finished_at      TEXT,
                auctions_scraped INTEGER DEFAULT 0,
                items_total      INTEGER DEFAULT 0,
                opportunities    INTEGER DEFAULT 0,
                alerts_sent      INTEGER DEFAULT 0,
                dry_run          INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id          INTEGER REFERENCES runs(id),
                scraped_at      TEXT NOT NULL,
                auction_id      TEXT NOT NULL,
                auction_title   TEXT,
                item_id         TEXT NOT NULL,
                lot_number      TEXT,
                title           TEXT,
                current_bid     REAL,
                min_bid         REAL,
                retail_price    REAL,
                end_time        INTEGER,
                condition_text  TEXT,
                item_url        TEXT,
                is_opportunity  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at           TEXT NOT NULL,
                item_id           TEXT NOT NULL,
                auction_id        TEXT NOT NULL,
                lot_number        TEXT,
                title             TEXT,
                min_bid           REAL,
                retail_price      REAL,
                minutes_remaining INTEGER,
                dry_run           INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_items_item_id     ON items(item_id);
            CREATE INDEX IF NOT EXISTS idx_items_auction_id  ON items(auction_id);
            CREATE INDEX IF NOT EXISTS idx_items_scraped_at  ON items(scraped_at);
            CREATE INDEX IF NOT EXISTS idx_alerts_item_id    ON alerts(item_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_sent_at    ON alerts(sent_at);
        """)
    conn.close()
    print(f"✓ DB inicializada: {DB_PATH}")


# ─── RUNS ────────────────────────────────────────────────────────────────────

def insert_run(started_at: str, dry_run: bool = False) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, dry_run) VALUES (?, ?)",
            (started_at, int(dry_run))
        )
        run_id = cur.lastrowid
    conn.close()
    return run_id


def update_run(run_id: int, finished_at: str, auctions_scraped: int,
               items_total: int, opportunities: int, alerts_sent: int):
    conn = get_connection()
    with conn:
        conn.execute("""
            UPDATE runs SET
                finished_at      = ?,
                auctions_scraped = ?,
                items_total      = ?,
                opportunities    = ?,
                alerts_sent      = ?
            WHERE id = ?
        """, (finished_at, auctions_scraped, items_total, opportunities, alerts_sent, run_id))
    conn.close()


# ─── ITEMS ───────────────────────────────────────────────────────────────────

def _extract_retail_price(title: str) -> Optional[float]:
    """Extrae el precio retail del título si dice (Retail $X) o (Retail $X,XXX)."""
    if not title:
        return None
    match = re.search(r'\(Retail\s+\$([0-9,]+(?:\.\d{1,2})?)\)', title, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(',', ''))
    return None


def insert_items_bulk(run_id: int, items: list[dict]):
    """
    Inserta múltiples items de una corrida.
    Cada dict debe tener las claves del API getitems + auction_title.
    """
    if not items:
        return

    scraped_at = datetime.now().isoformat()
    rows = []

    for item in items:
        retail = _extract_retail_price(item.get('title', ''))
        current_bid_raw = item.get('current_bid', '0')
        min_bid_raw     = item.get('minimum_bid') or item.get('starting_bid', '0')

        try:
            current_bid = float(current_bid_raw)
        except (ValueError, TypeError):
            current_bid = 0.0

        try:
            min_bid = float(min_bid_raw)
        except (ValueError, TypeError):
            min_bid = 0.0

        rows.append((
            run_id,
            scraped_at,
            str(item.get('auction_id', '')),
            item.get('auction_title', ''),
            str(item.get('id', '')),
            str(item.get('lot_number', '')),
            item.get('title', ''),
            current_bid,
            min_bid,
            retail,
            item.get('end_time'),
            item.get('condition_text', ''),
            item.get('item_url', ''),
            1 if current_bid == 0.0 else 0
        ))

    conn = get_connection()
    with conn:
        conn.executemany("""
            INSERT INTO items (
                run_id, scraped_at, auction_id, auction_title,
                item_id, lot_number, title, current_bid, min_bid,
                retail_price, end_time, condition_text, item_url, is_opportunity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.close()


# ─── ALERTS ──────────────────────────────────────────────────────────────────

def insert_alert(item_id: str, auction_id: str, lot_number: str, title: str,
                 min_bid: float, minutes_remaining: int, dry_run: bool = False,
                 retail_price: Optional[float] = None):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO alerts (
                sent_at, item_id, auction_id, lot_number,
                title, min_bid, retail_price, minutes_remaining, dry_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            item_id, auction_id, lot_number,
            title, min_bid, retail_price,
            minutes_remaining, int(dry_run)
        ))
    conn.close()


def was_alert_sent_recently(item_id: str, auction_id: str, within_minutes: int) -> bool:
    """
    Devuelve True si ya se envió alerta para este item en los últimos within_minutes.
    Reemplaza la deduplicación basada en JSON.
    """
    conn = get_connection()
    cur = conn.execute("""
        SELECT COUNT(*) as cnt FROM alerts
        WHERE item_id = ?
          AND auction_id = ?
          AND dry_run = 0  -- solo alertas reales
          AND sent_at >= datetime('now', ?, 'localtime')
    """, (item_id, auction_id, f'-{within_minutes} minutes'))
    row = cur.fetchone()
    conn.close()
    return row['cnt'] > 0


# ─── QUERIES / REPORTES ──────────────────────────────────────────────────────

def get_last_runs(limit: int = 10) -> list:
    conn = get_connection()
    cur = conn.execute("""
        SELECT * FROM runs ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_item_price_history(item_id: str) -> list:
    """Historial de precios de un item específico a lo largo de las corridas."""
    conn = get_connection()
    cur = conn.execute("""
        SELECT scraped_at, current_bid, min_bid, is_opportunity
        FROM items
        WHERE item_id = ?
        ORDER BY scraped_at ASC
    """, (item_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_opportunities_with_retail(min_ratio: float = 5.0) -> list:
    """
    Items con bid=$0 donde retail_price / min_bid >= min_ratio.
    Útil para scoring de reventa.
    """
    conn = get_connection()
    cur = conn.execute("""
        SELECT
            item_id, auction_id, lot_number, title,
            min_bid, retail_price,
            ROUND(retail_price / NULLIF(min_bid, 0), 1) as ratio,
            end_time, item_url
        FROM items
        WHERE is_opportunity = 1
          AND retail_price IS NOT NULL
          AND retail_price / NULLIF(min_bid, 0) >= ?
        ORDER BY ratio DESC
        LIMIT 50
    """, (min_ratio,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_db_stats() -> dict:
    conn = get_connection()
    stats = {}
    stats['total_runs']   = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    stats['total_items']  = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    stats['total_alerts'] = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    stats['opportunities']= conn.execute("SELECT COUNT(*) FROM items WHERE is_opportunity=1").fetchone()[0]
    stats['with_retail']  = conn.execute("SELECT COUNT(*) FROM items WHERE retail_price IS NOT NULL").fetchone()[0]
    conn.close()
    return stats


# ─── CLI rápido para verificar ───────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    stats = get_db_stats()
    print("\n📊 DB Stats:")
    for k, v in stats.items():
        print(f"   {k}: {v}")
    runs = get_last_runs(5)
    if runs:
        print("\n🕐 Últimas corridas:")
        for r in runs:
            print(f"   Run {r['id']} | {r['started_at']} | items={r['items_total']} | alerts={r['alerts_sent']}")

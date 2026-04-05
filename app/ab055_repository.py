"""
AB-055 — Repository (interfaz agnóstica de DB)
Los scripts ab053, ab054 solo importan este módulo.
Para migrar a Supabase: cambiar la línea de import abajo. Nada más.
"""

# ─── SWAP AQUÍ PARA MIGRAR ───────────────────────────────────────────────────
# Hoy:
from ab055_sqlite import (
    init_db,
    insert_run,
    update_run,
    insert_items_bulk,
    insert_alert,
    was_alert_sent_recently,
    get_last_runs,
    get_item_price_history,
    get_opportunities_with_retail,
    get_db_stats,
    get_category_stats,
    get_opportunities_by_category,
    backfill_categories,
)
# Cuando migres a Supabase, reemplaza por:
# from ab055_supabase import (
#     init_db, insert_run, update_run, insert_items_bulk,
#     insert_alert, was_alert_sent_recently, get_last_runs,
#     get_item_price_history, get_opportunities_with_retail, get_db_stats,
# )
# ─────────────────────────────────────────────────────────────────────────────


class AuctionBotDB:
    """
    Interfaz principal que usan ab053 y ab054.
    Métodos documentados — la implementación vive en ab055_sqlite.py
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.current_run_id = None
        init_db()

    # ── Lifecycle de corrida ─────────────────────────────────────────────────

    def start_run(self) -> int:
        """Registra el inicio de una corrida. Retorna el run_id."""
        from datetime import datetime
        self.current_run_id = insert_run(
            started_at=datetime.now().isoformat(),
            dry_run=self.dry_run
        )
        return self.current_run_id

    def finish_run(self, auctions_scraped: int, items_total: int,
                   opportunities: int, alerts_sent: int):
        """Actualiza la corrida con los resultados finales."""
        if not self.current_run_id:
            return
        from datetime import datetime
        update_run(
            run_id=self.current_run_id,
            finished_at=datetime.now().isoformat(),
            auctions_scraped=auctions_scraped,
            items_total=items_total,
            opportunities=opportunities,
            alerts_sent=alerts_sent
        )

    # ── Items ────────────────────────────────────────────────────────────────

    def save_items(self, items: list[dict]):
        """
        Guarda todos los items scrapeados de una corrida.
        items: lista de dicts con campos del API getitems + auction_title + auction_id
        """
        if not self.current_run_id:
            raise RuntimeError("Llama start_run() antes de save_items()")
        insert_items_bulk(self.current_run_id, items)

    # ── Alertas ──────────────────────────────────────────────────────────────

    def should_alert(self, item_id: str, auction_id: str, dedup_minutes: int) -> bool:
        """
        True si hay que enviar alerta (no fue enviada recientemente).
        Reemplaza la lógica del alerts_sent.json actual.
        """
        if self.dry_run:
            # En dry-run siempre mostrar, nunca bloquear por dedup
            return True
        return not was_alert_sent_recently(item_id, auction_id, dedup_minutes)

    def record_alert(self, item_id: str, auction_id: str, lot_number: str,
                     title: str, min_bid: float, minutes_remaining: int,
                     retail_price=None):
        """Registra que se envió (o se habría enviado en dry-run) una alerta."""
        insert_alert(
            item_id=item_id,
            auction_id=auction_id,
            lot_number=lot_number,
            title=title,
            min_bid=min_bid,
            minutes_remaining=minutes_remaining,
            dry_run=self.dry_run,
            retail_price=retail_price
        )

    # ── Reportes ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return get_db_stats()

    def get_recent_runs(self, limit: int = 10) -> list:
        return get_last_runs(limit)

    def get_price_history(self, item_id: str) -> list:
        return get_item_price_history(item_id)

    def get_top_opportunities(self, min_ratio: float = 5.0) -> list:
        """Items con mejor ratio retail_price / min_bid."""
        return get_opportunities_with_retail(min_ratio)

    def get_categories(self) -> list:
        """Conteo de items y oportunidades por categoría."""
        return get_category_stats()

    def get_category_opportunities(self, category: str) -> list:
        """Oportunidades activas filtradas por categoría."""
        return get_opportunities_by_category(category)

    def backfill_item_categories(self, categorize_fn) -> int:
        """Categoriza items existentes sin categoría."""
        return backfill_categories(categorize_fn)


# ─── CLI de diagnóstico ──────────────────────────────────────────────────────

if __name__ == "__main__":
    db = AuctionBotDB()
    stats = db.get_stats()
    print("\n📊 AuctionBot DB Stats:")
    print(f"   Corridas totales : {stats['total_runs']}")
    print(f"   Items registrados: {stats['total_items']}")
    print(f"   Alertas enviadas : {stats['total_alerts']}")
    print(f"   Oportunidades    : {stats['opportunities']}")
    print(f"   Con retail price : {stats['with_retail']}")

    runs = db.get_recent_runs(5)
    if runs:
        print("\n🕐 Últimas 5 corridas:")
        for r in runs:
            status = "DRY" if r['dry_run'] else "REAL"
            print(f"   [{status}] Run {r['id']} | {r['started_at'][:19]} | "
                  f"items={r['items_total']} | opps={r['opportunities']} | alerts={r['alerts_sent']}")

    top = db.get_top_opportunities(min_ratio=3.0)
    if top:
        print(f"\n🎯 Top oportunidades (ratio retail/min >= 3x):")
        for t in top[:5]:
            print(f"   {t['ratio']}x | ${t['min_bid']} → ${t['retail_price']} | {t['title'][:60]}")

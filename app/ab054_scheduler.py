"""
AB-054 — Scheduler: AuctionBot
================================
Corre el bot de alertas cada N minutos de forma continua.

Uso:
    python ab054_scheduler.py                    # corre cada 30 min
    python ab054_scheduler.py --interval 15      # corre cada 15 min
    python ab054_scheduler.py --max-minutes 45   # alertar items <= 45 min
    python ab054_scheduler.py --once             # corre una sola vez y sale

Detener: Ctrl+C
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

INTERVAL_MINUTES_DEFAULT = 30
MAX_ALERT_MINUTES_DEFAULT = 60
SCRAPER_SCRIPT = Path("ab053_v2.py")
LOG_FILE       = Path("artifacts/ab054/scheduler.log")


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ts_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, also_print: bool = True):
    """Escribe al log y opcionalmente imprime."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{ts_local()}] {msg}"
    if also_print:
        print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def format_duration(seconds: float) -> str:
    """Convierte segundos a string legible."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


# ──────────────────────────────────────────────
# RUNNER DE CORRIDA
# ──────────────────────────────────────────────

def run_scraper(max_minutes: int) -> dict:
    """
    Ejecuta ab053_v2.py como subproceso.
    Retorna dict con resultado de la corrida.
    """
    if not SCRAPER_SCRIPT.exists():
        return {"status": "error", "error": f"{SCRAPER_SCRIPT} no encontrado"}

    cmd = [
        sys.executable,
        str(SCRAPER_SCRIPT),
        "--max-alerts", "15", "--max-minutes", str(max_minutes),
    ]

    start = datetime.now(timezone.utc).timestamp()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos máximo por corrida
            encoding="utf-8",
            errors="replace",
        )
        duration = datetime.now(timezone.utc).timestamp() - start

        # extraer métricas del output
        output = result.stdout
        metrics = parse_metrics(output)

        return {
            "status":       "success" if result.returncode == 0 else "error",
            "returncode":   result.returncode,
            "duration_s":   round(duration, 1),
            "metrics":      metrics,
            "stdout_tail":  output[-800:] if output else "",
            "stderr_tail":  result.stderr[-400:] if result.stderr else "",
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "duration_s": 600, "metrics": {}}
    except Exception as e:
        return {"status": "error", "error": str(e), "metrics": {}}


def parse_metrics(output: str) -> dict:
    """Extrae métricas del stdout del scraper."""
    import re
    metrics = {}

    patterns = {
        "subastas":     r"(\d+) subastas detectadas",
        "items":        r"Items totales:\s+(\d+)",
        "oportunidades": r"Oportunidades bid=\$0:\s+(\d+)",
        "urgentes":     r"Urgentes \([^)]+\):\s+(\d+)",
        "enviadas":     r"Enviadas:\s+(\d+)",
        "deduplicadas": r"Deduplicadas:\s+(\d+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, output)
        if m:
            metrics[key] = int(m.group(1))

    return metrics


# ──────────────────────────────────────────────
# LOOP PRINCIPAL
# ──────────────────────────────────────────────

async def run_loop(interval_minutes: int, max_minutes: int, run_once: bool):
    interval_secs = interval_minutes * 60
    run_number    = 0

    print(f"\n{'='*60}")
    print(f"AB-054 — AuctionBot Scheduler")
    print(f"{'='*60}")
    print(f"Intervalo:      cada {interval_minutes} minutos")
    print(f"Filtro alertas: <= {max_minutes} minutos")
    print(f"Script:         {SCRAPER_SCRIPT}")
    print(f"Log:            {LOG_FILE}")
    print(f"Iniciado:       {ts_local()}")
    if not run_once:
        print(f"\nPresiona Ctrl+C para detener.\n")
    print(f"{'='*60}\n")

    log(f"Scheduler iniciado — intervalo={interval_minutes}min, max_minutes={max_minutes}")

    while True:
        run_number += 1
        log(f"--- Corrida #{run_number} iniciando ---")

        result = run_scraper(max_minutes)

        m = result.get("metrics", {})
        status_icon = "✓" if result["status"] == "success" else "✗"

        summary = (
            f"{status_icon} Corrida #{run_number} "
            f"[{format_duration(result.get('duration_s', 0))}] — "
            f"items={m.get('items', '?')} | "
            f"opp={m.get('oportunidades', '?')} | "
            f"enviadas={m.get('enviadas', '?')} | "
            f"dedup={m.get('deduplicadas', '?')}"
        )
        log(summary)

        if result["status"] == "error":
            log(f"  ERROR: {result.get('error', 'ver stderr')}")
            if result.get("stderr_tail"):
                log(f"  STDERR: {result['stderr_tail'][:300]}")

        if run_once:
            log("Modo --once: saliendo después de la primera corrida.")
            break

        # calcular próxima corrida
        next_run = datetime.now()
        from datetime import timedelta
        next_run_time = next_run + timedelta(seconds=interval_secs)

        log(f"Próxima corrida: {next_run_time.strftime('%H:%M:%S')} "
            f"(en {interval_minutes} minutos)")

        print(f"\n  Esperando {interval_minutes} minutos...")
        print(f"  Próxima corrida: {next_run_time.strftime('%H:%M:%S')}")
        print(f"  Presiona Ctrl+C para detener.\n")

        # esperar con posibilidad de Ctrl+C limpio
        try:
            await asyncio.sleep(interval_secs)
        except asyncio.CancelledError:
            break


# ──────────────────────────────────────────────
# ENTRYPOINT
# ──────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AuctionBot Scheduler")
    parser.add_argument(
        "--interval", type=int, default=INTERVAL_MINUTES_DEFAULT,
        help=f"Intervalo entre corridas en minutos (default: {INTERVAL_MINUTES_DEFAULT})"
    )
    parser.add_argument(
        "--max-minutes", type=int, default=MAX_ALERT_MINUTES_DEFAULT,
        help=f"Alertar items que cierran en <= N minutos (default: {MAX_ALERT_MINUTES_DEFAULT})"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Correr una sola vez y salir"
    )
    args = parser.parse_args()

    try:
        await run_loop(
            interval_minutes=args.interval,
            max_minutes=args.max_minutes,
            run_once=args.once,
        )
    except KeyboardInterrupt:
        log("\nScheduler detenido por el usuario (Ctrl+C).")
        print("\n\nScheduler detenido. Hasta luego.")


if __name__ == "__main__":
    asyncio.run(main())

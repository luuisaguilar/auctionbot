"""
AB-057 — Categorizador de Productos
=====================================
Categoriza items de Auction Nation basándose en keywords del título
y del nombre de la subasta.

Uso standalone:
    python ab057_categorizer.py              # muestra distribución de la DB
    python ab057_categorizer.py --backfill   # categoriza items sin categoría

Uso como módulo:
    from ab057_categorizer import categorize_item
    cat = categorize_item("DEWALT 20V Max Drill", "Hardware And Tools Auction")
    # → "Herramientas"
"""

import re
from typing import Optional


# ──────────────────────────────────────────────
# CATEGORÍAS Y PATRONES
# ──────────────────────────────────────────────
# Orden importa: las categorías más específicas van primero.
# Cada categoría tiene:
#   - title_patterns: regex compilados para matchear contra el título del item
#   - auction_patterns: regex para matchear contra el nombre de la subasta
# El primer match gana.

CATEGORIES = [
    {
        "name": "Monedas y Coleccionables",
        "icon": "🪙",
        "title_patterns": [
            r"\b(?:coin|dollar|eagle|proof|morgan|mint|bullion|quarter|dime|nickel"
            r"|penny|cent\b|numismatic|graded|NGC|PCGS|uncirculated|silver\s+dollar"
            r"|gold\s+coin|silver\s+coin|currency|banknote)\b",
        ],
        "auction_patterns": [
            r"(?:coin|bullion|currency|collectible\s+coin)",
        ],
    },
    {
        "name": "Joyería",
        "icon": "💎",
        "title_patterns": [
            r"\b(?:sterling\s+silver|(?:925|14k|10k|18k)\s+(?:gold|silver|ring|pendant|necklace|bracelet)"
            r"|necklace|bracelet|earring|ring\b.*(?:size|grams|silver|gold|zirconia|diamond)"
            r"|pendant\b.*(?:chain|necklace|stone|silver|gold)"
            r"|carat|karat|gemstone|topaz|amethyst|sapphire|ruby|onyx|turquoise"
            r"|dooney\s*&?\s*bourke|coach\s+(?:bag|purse)|jewelry|jewel)\b",
        ],
        "auction_patterns": [
            r"(?:sterling\s+silver|ring\s+auction|jewelry|watch\s+auction)",
        ],
    },
    {
        "name": "Herramientas",
        "icon": "🔧",
        "title_patterns": [
            r"\b(?:RYOBI|DEWALT|Milwaukee|Makita|Bosch|Ridgid|Craftsman|Kobalt"
            r"|drill|saw\b|wrench|plier|socket|ratchet|grinder|sander"
            r"|impact\s+driver|rotary\s+tool|jigsaw|miter|circular\s+saw"
            r"|tool\s+(?:box|bag|set|kit|only|chest)|multi-?tool"
            r"|compressor|nailer|stapler|clamp|vise|level\b"
            r"|tape\s+measure|stud\s+finder|cordless\s+(?!vacuum|stick))\b",
        ],
        "auction_patterns": [
            r"(?:hardware\s+and\s+tools|tools?\s+supply|tools?\s+auction)",
        ],
    },
    {
        "name": "Electrónica",
        "icon": "⚡",
        "title_patterns": [
            r"\b(?:smart\s+(?:home|device|plug|switch|speaker|display|thermostat)"
            r"|wifi|wi-fi|bluetooth|wireless\s+(?!doorbell)(?:charger|speaker|earbuds)"
            r"|camera\b|webcam|security\s+cam|wyze|ring\s+(?:doorbell|camera|alarm)"
            r"|EcoFlow|power\s+station|solar\s+(?:panel|generator)|inverter"
            r"|battery\s+(?:charger|pack|backup)|UPS\b|surge\s+protector"
            r"|ipad|tablet|laptop|monitor|TV\b|television|roku|firestick"
            r"|echo\b|alexa|google\s+(?:home|nest)|sonos)\b",
        ],
        "auction_patterns": [
            r"(?:smart\s+device|electronic)",
        ],
    },
    {
        "name": "Iluminación",
        "icon": "💡",
        "title_patterns": [
            r"\b(?:pendant\b(?!.*(?:necklace|chain|silver|gold|stone))"
            r"|chandelier|flush\s+mount|ceiling\s+(?:fan|light)"
            r"|sconce|wall\s+(?:light|lantern)|vanity\s+light"
            r"|recessed\s+(?:light|can|trim|kit)|track\s+light"
            r"|under\s+cabinet\s+light|led\s+(?:panel|strip|bulb|light|lamp)"
            r"|flood\s+light|spot\s+light|work\s+light|landscape\s+light"
            r"|lumen|watt\b.*(?:light|lamp|fixture)|light\s+fixture"
            r"|lamp\b(?!.*(?:table|desk|floor)\b.*(?:wood|metal|chair))"
            r"|dimmable|dimmer)\b",
        ],
        "auction_patterns": [],
    },
    {
        "name": "Cocina y Baño",
        "icon": "🍳",
        "title_patterns": [
            r"\b(?:kitchen\s+cabinet|kitchen\s+(?:sink|faucet|cart|island)"
            r"|bathroom\s+(?:sink|vanity|mirror|cabinet)"
            r"|shower\s+(?:head|door|drain|stall|system|curtain|valve)"
            r"|toilet\s+(?:seat|bowl|tank)|toilet\b"
            r"|bathtub|tub\b|medicine\s+cabinet"
            r"|towel\s+(?:bar|rack|ring|hook)"
            r"|faucet|showerhead|soap\s+dispens"
            r"|base\s+kitchen\s+cabinet|wall\s+cabinet)\b",
        ],
        "auction_patterns": [
            r"(?:kitchen\s+(?:and|&)\s+bath|kitchen\s+cabinet|luxury\s+kitchen)",
        ],
    },
    {
        "name": "Muebles",
        "icon": "🛋",
        "title_patterns": [
            r"\b(?:sofa|couch|loveseat|recliner|futon"
            r"|table\b(?!.*(?:saw|tile|lamp|mount|top\s+(?:vanity|sink)))"
            r"|(?:dining|coffee|end|console|accent|side)\s+table"
            r"|desk\b|bookcase|bookshelf|shelf\b(?!.*(?:shower|wire\s+rack))"
            r"|nightstand|bed\s*(?:frame|side)|headboard|dresser"
            r"|chair\b(?!.*(?:toilet|shower))|bench\b(?!.*(?:grinder|vise|work))"
            r"|ottoman|stool\b(?!.*(?:step|bar\s+stool)))\b",
        ],
        "auction_patterns": [
            r"(?:furniture|home\s+decor)",
        ],
    },
    {
        "name": "Puertas y Pisos",
        "icon": "🚪",
        "title_patterns": [
            r"\b(?:door\b(?!.*(?:bell|knob|stop|mat|lock\b))"
            r"|(?:interior|exterior|entry|patio|sliding|french|barn)\s+door"
            r"|flooring|(?:vinyl|laminate|hardwood|porcelain|ceramic)\s+(?:tile|plank|floor)"
            r"|tile\b(?!.*(?:shower\s+drain|backer))"
            r"|sq\.\s*ft\.\s*(?:/|per)\s*case"
            r"|(?:floor|wall)\s+tile)\b",
        ],
        "auction_patterns": [
            r"(?:doors?\b|flooring|building\s+materials)",
        ],
    },
    {
        "name": "Jardín y Exterior",
        "icon": "🌿",
        "title_patterns": [
            r"\b(?:patio|outdoor\s+(?!wall\b|light\b|lantern\b|sconce\b)"
            r"|garden\b|lawn\b|mower|trimmer|blower|chainsaw"
            r"|sprinkler|irrigation|hose\b|nozzle"
            r"|fire\s+pit|grill\b|bbq|barbecue"
            r"|planter|pot\b.*(?:plant|flower)|raised\s+bed"
            r"|fence\b|gate\b(?!.*(?:baby|pet|safety))|deck\b(?!.*(?:screw|mate))"
            r"|pergola|gazebo|umbrella\b.*(?:patio|outdoor)"
            r"|snow\s+blower|snow\s+shovel|leaf\s+(?:blower|bag)"
            r"|weed\s*(?:er|ing)|edger|hedge\s+trim"
            r"|pressure\s+washer|power\s+washer)\b",
        ],
        "auction_patterns": [
            r"(?:outdoor|patio|garden)",
        ],
    },
    {
        "name": "Materiales de Construcción",
        "icon": "🧱",
        "title_patterns": [
            r"\b(?:plywood|drywall|sheetrock|lumber|stud\b(?!.*finder)"
            r"|cement|concrete|mortar|grout"
            r"|backer\s+board|insulation|roofing|shingle"
            r"|(?:wood|metal|deck)\s+screw|nail\b.*(?:lb|piece|pack|bag)"
            r"|anchor|bolt\b.*(?:pack|piece)|washer\b.*(?:pack|piece)"
            r"|caulk|sealant|adhesive|construction\s+adhesive"
            r"|flashing|vapor\s+barrier|wire\s+mesh"
            r"|tape\b.*(?:drywall|joint|duct))\b",
        ],
        "auction_patterns": [
            r"(?:building\s+materials|parts?\s+pallet)",
        ],
    },
    {
        "name": "Plomería",
        "icon": "🔩",
        "title_patterns": [
            r"\b(?:pipe\b(?!.*(?:clamp\b|wrench\b))|pvc\b|copper\s+(?:pipe|fitting)"
            r"|drain\b(?!.*(?:shower|linear))|valve\b(?!.*(?:shower))"
            r"|garbage\s+disposal|water\s+heater"
            r"|sump\s+pump|well\s+pump|utility\s+pump"
            r"|p-trap|coupling|elbow\b.*(?:pvc|pipe)"
            r"|water\s+(?:filter|softener|line)"
            r"|plumb|laundry\s+(?:sink|tub))\b",
        ],
        "auction_patterns": [],
    },
    {
        "name": "Hogar y Decoración",
        "icon": "🏠",
        "title_patterns": [
            r"\b(?:decor|curtain|drape|blind\b|shade\b(?!.*(?:lamp|glass))"
            r"|pillow|cushion|throw\b|blanket|comforter|duvet"
            r"|rug\b|mat\b(?!.*(?:battery|welding))|carpet"
            r"|mirror\b(?!.*(?:medicine|cabinet))"
            r"|frame\b(?!.*(?:bed|door|window))|wall\s+art|canvas"
            r"|organizer|storage\s+(?:bin|box|tote|container|tub)"
            r"|closet\s+(?:organizer|shelf|system|kit)"
            r"|hook\b|hanger|basket|hamper"
            r"|doorbell|door\s+(?:knob|handle|lock|mat)"
            r"|mailbox|house\s+number|address\s+(?:number|plaque)"
            r"|clock\b|vase|candle)\b",
        ],
        "auction_patterns": [
            r"(?:home\s+goods|general\s+(?:goods|merchandise)|miscellaneous|assorted)",
        ],
    },
]

# Categoría por defecto
DEFAULT_CATEGORY = "Otro"
DEFAULT_ICON = "📦"


# ──────────────────────────────────────────────
# COMPILAR PATRONES (una sola vez)
# ──────────────────────────────────────────────

_compiled = []
for cat in CATEGORIES:
    _compiled.append({
        "name": cat["name"],
        "icon": cat["icon"],
        "title_re": [re.compile(p, re.IGNORECASE) for p in cat["title_patterns"]],
        "auction_re": [re.compile(p, re.IGNORECASE) for p in cat["auction_patterns"]],
    })


# ──────────────────────────────────────────────
# API PRINCIPAL
# ──────────────────────────────────────────────

def categorize_item(title: str, auction_title: str = "") -> str:
    """
    Categoriza un item basándose en su título y el nombre de la subasta.
    Retorna el nombre de la categoría (string).
    """
    title = (title or "").strip()
    auction_title = (auction_title or "").strip()

    # Paso 1: Matchear por título (más específico)
    for cat in _compiled:
        for pattern in cat["title_re"]:
            if pattern.search(title):
                return cat["name"]

    # Paso 2: Matchear por nombre de subasta (fallback)
    for cat in _compiled:
        for pattern in cat["auction_re"]:
            if pattern.search(auction_title):
                return cat["name"]

    return DEFAULT_CATEGORY


def get_category_icon(category_name: str) -> str:
    """Retorna el ícono emoji de una categoría."""
    for cat in CATEGORIES:
        if cat["name"] == category_name:
            return cat["icon"]
    return DEFAULT_ICON


def get_all_categories() -> list[dict]:
    """Retorna la lista de categorías con nombre e ícono."""
    cats = [{"name": c["name"], "icon": c["icon"]} for c in CATEGORIES]
    cats.append({"name": DEFAULT_CATEGORY, "icon": DEFAULT_ICON})
    return cats


# ──────────────────────────────────────────────
# CLI: DIAGNÓSTICO Y BACKFILL
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sqlite3
    import os
    from env_loader import load_local_env

    load_local_env()

    parser = argparse.ArgumentParser(description="AB-057 Categorizador de Productos")
    parser.add_argument("--backfill", action="store_true",
                        help="Categorizar items existentes sin categoría")
    parser.add_argument("--stats", action="store_true", default=True,
                        help="Mostrar distribución de categorías (default)")
    parser.add_argument("--sample", type=int, default=0,
                        help="Mostrar N items de muestra con su categoría asignada")
    args = parser.parse_args()

    DB_PATH = os.environ.get("AUCTIONBOT_DB_PATH", "data/auctionbot.db")

    # Resolver ruta relativa desde el directorio padre
    if not os.path.isabs(DB_PATH):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DB_PATH = os.path.join(base, DB_PATH)

    if not os.path.exists(DB_PATH):
        print(f"✗ DB no encontrada: {DB_PATH}")
        exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Verificar si la columna category existe
    cols = [c[1] for c in conn.execute("PRAGMA table_info(items)").fetchall()]
    has_category = "category" in cols

    if args.backfill:
        if not has_category:
            print("Agregando columna 'category' a tabla items...")
            conn.execute("ALTER TABLE items ADD COLUMN category TEXT")
            conn.commit()
            has_category = True

        print("\nCategorizando items sin categoría...")
        rows = conn.execute(
            "SELECT DISTINCT title, auction_title FROM items WHERE category IS NULL"
        ).fetchall()
        print(f"  {len(rows)} combinaciones título/subasta únicas por categorizar")

        batch = []
        for row in rows:
            cat = categorize_item(row["title"], row["auction_title"])
            batch.append((cat, row["title"], row["auction_title"]))

        # Update en batch por combinación título+subasta
        with conn:
            for cat, title, auction_title in batch:
                conn.execute(
                    "UPDATE items SET category = ? WHERE title = ? AND auction_title = ?",
                    (cat, title, auction_title)
                )
        print(f"  ✓ Backfill completo")

    # Mostrar distribución
    print(f"\n{'='*60}")
    print("DISTRIBUCIÓN DE CATEGORÍAS")
    print(f"{'='*60}")

    if has_category:
        rows = conn.execute("""
            SELECT COALESCE(category, '(sin categoría)') as cat,
                   COUNT(*) as total,
                   SUM(CASE WHEN is_opportunity = 1 THEN 1 ELSE 0 END) as opps
            FROM items
            GROUP BY category
            ORDER BY total DESC
        """).fetchall()
        for r in rows:
            icon = get_category_icon(r["cat"]) if r["cat"] != "(sin categoría)" else "❓"
            print(f"  {icon} {r['cat']:<30} {r['total']:>8,} items  |  {r['opps']:>6,} opps")
    else:
        # Simular distribución sin columna (solo lectura)
        print("  (Simulación — la columna 'category' aún no existe)")
        print("  Leyendo títulos únicos...")
        rows = conn.execute(
            "SELECT DISTINCT title, auction_title FROM items WHERE title IS NOT NULL"
        ).fetchall()
        counts = {}
        for row in rows:
            cat = categorize_item(row["title"], row["auction_title"])
            counts[cat] = counts.get(cat, 0) + 1
        for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
            icon = get_category_icon(cat)
            print(f"  {icon} {cat:<30} {count:>6,} títulos únicos")
        print(f"\n  Total títulos únicos: {sum(counts.values()):,}")

    if args.sample > 0:
        print(f"\n{'='*60}")
        print(f"MUESTRA DE {args.sample} ITEMS")
        print(f"{'='*60}")
        rows = conn.execute(
            "SELECT title, auction_title FROM items ORDER BY RANDOM() LIMIT ?",
            (args.sample,)
        ).fetchall()
        for r in rows:
            cat = categorize_item(r["title"], r["auction_title"])
            icon = get_category_icon(cat)
            title_short = (r["title"] or "")[:70]
            print(f"  {icon} [{cat:<20}] {title_short}")

    conn.close()

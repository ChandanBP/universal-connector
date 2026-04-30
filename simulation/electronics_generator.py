"""
UNIVERSAL CONNECTOR — Electronics Domain Simulation Generator
Generates products, trust edges, interactions, and source trust for electronics.

Outputs:
  simulation/data/products.json
  simulation/data/electronics_trust_edges.json
  simulation/data/electronics_interactions.json
  simulation/data/electronics_source_trust.json

Run:
  python -m simulation.electronics_generator          # generate JSON only
  python -m simulation.electronics_generator --seed   # generate + seed to DB
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent / "data"

random.seed(42)


# ── HELPERS ───────────────────────────────────────────────────────────────────

def rand_uuid() -> str:
    return str(uuid.uuid4())

def rand_date(start_days_ago: int = 300, end_days_ago: int = 0) -> str:
    delta = random.randint(end_days_ago, start_days_ago)
    return (datetime.now() - timedelta(days=delta)).isoformat()

def load_users() -> list[dict]:
    with open(DATA_DIR / "users.json") as f:
        return json.load(f)


# ── PRODUCT CATALOGUE ─────────────────────────────────────────────────────────

PRODUCTS = [
    # Phones
    {
        "name": "Apple iPhone 15 Pro",
        "brand": ["Apple"],
        "category": "phone",
        "use_case": ["professional", "content-creation", "casual-use"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "5G", "USB-C"],
        "battery_life": "good",
        "portability": "highly-portable",
        "tags": ["apple", "premium", "5g", "camera", "flagship"],
    },
    {
        "name": "Samsung Galaxy S24",
        "brand": ["Samsung"],
        "category": "phone",
        "use_case": ["professional", "gaming", "casual-use"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "5G", "USB-C"],
        "battery_life": "good",
        "portability": "highly-portable",
        "tags": ["samsung", "android", "5g", "amoled", "flagship"],
    },
    {
        "name": "OnePlus 12R",
        "brand": ["OnePlus"],
        "category": "phone",
        "use_case": ["gaming", "casual-use", "student"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "5G"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["oneplus", "gaming", "fast-charging", "5g", "mid-range"],
    },
    {
        "name": "Google Pixel 8a",
        "brand": ["Google"],
        "category": "phone",
        "use_case": ["casual-use", "professional", "travel"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "5G"],
        "battery_life": "good",
        "portability": "highly-portable",
        "tags": ["google", "pure-android", "camera", "ai", "mid-range"],
    },
    # Laptops
    {
        "name": "Apple MacBook Air M3",
        "brand": ["Apple"],
        "category": "laptop",
        "use_case": ["work", "content-creation", "student", "home-office"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "Thunderbolt", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["apple", "m3", "lightweight", "battery", "silent"],
    },
    {
        "name": "Dell XPS 15",
        "brand": ["Dell"],
        "category": "laptop",
        "use_case": ["work", "content-creation", "professional"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "Thunderbolt", "USB-A"],
        "battery_life": "good",
        "portability": "portable",
        "tags": ["dell", "oled", "professional", "video-editing", "4k"],
    },
    {
        "name": "Lenovo ThinkPad E14",
        "brand": ["Lenovo"],
        "category": "laptop",
        "use_case": ["work", "home-office", "student"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "USB-C", "USB-A", "HDMI"],
        "battery_life": "good",
        "portability": "portable",
        "tags": ["lenovo", "thinkpad", "business", "keyboard", "durable"],
    },
    {
        "name": "Asus ROG Zephyrus G14",
        "brand": ["Asus"],
        "category": "laptop",
        "use_case": ["gaming", "content-creation"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "USB-C", "USB-A", "HDMI"],
        "battery_life": "good",
        "portability": "portable",
        "tags": ["asus", "rog", "gaming", "ryzen", "amd", "144hz"],
    },
    {
        "name": "HP Pavilion 15",
        "brand": ["HP"],
        "category": "laptop",
        "use_case": ["student", "casual-use", "home-office"],
        "price_range": "budget",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "USB-C", "USB-A", "HDMI"],
        "battery_life": "average",
        "portability": "portable",
        "tags": ["hp", "budget", "student", "everyday", "affordable"],
    },
    # Headphones
    {
        "name": "Sony WH-1000XM5",
        "brand": ["Sony"],
        "category": "headphones",
        "use_case": ["travel", "work", "casual-use"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C", "3.5mm"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["sony", "anc", "noise-cancelling", "wireless", "premium"],
    },
    {
        "name": "Bose QuietComfort 45",
        "brand": ["Bose"],
        "category": "headphones",
        "use_case": ["travel", "work", "casual-use"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C", "3.5mm"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["bose", "anc", "comfortable", "premium", "wireless"],
    },
    {
        "name": "Jabra Evolve2 65",
        "brand": ["Jabra"],
        "category": "headphones",
        "use_case": ["work", "home-office", "professional"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-A"],
        "battery_life": "excellent",
        "portability": "portable",
        "tags": ["jabra", "work", "calls", "professional", "wireless"],
    },
    {
        "name": "Sennheiser HD 560S",
        "brand": ["Sennheiser"],
        "category": "headphones",
        "use_case": ["content-creation", "casual-use", "professional"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["3.5mm", "6.35mm"],
        "battery_life": "na",
        "portability": "portable",
        "tags": ["sennheiser", "audiophile", "open-back", "studio", "wired"],
    },
    {
        "name": "JBL Tune 770NC",
        "brand": ["JBL"],
        "category": "headphones",
        "use_case": ["casual-use", "fitness", "travel"],
        "price_range": "budget",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["jbl", "budget", "anc", "wireless", "affordable"],
    },
    # Tablets
    {
        "name": "Apple iPad Air M2",
        "brand": ["Apple"],
        "category": "tablet",
        "use_case": ["casual-use", "content-creation", "student"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["apple", "ipad", "creative", "display", "apple-pencil"],
    },
    {
        "name": "Samsung Galaxy Tab S9",
        "brand": ["Samsung"],
        "category": "tablet",
        "use_case": ["casual-use", "content-creation", "student"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["WiFi", "Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["samsung", "amoled", "android", "s-pen", "tablet"],
    },
    # Smartwatches
    {
        "name": "Apple Watch Series 9",
        "brand": ["Apple"],
        "category": "smartwatch",
        "use_case": ["fitness", "casual-use", "professional"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["Bluetooth", "WiFi", "GPS"],
        "battery_life": "good",
        "portability": "highly-portable",
        "tags": ["apple", "health", "fitness", "ios", "waterproof"],
    },
    {
        "name": "Samsung Galaxy Watch 6",
        "brand": ["Samsung"],
        "category": "smartwatch",
        "use_case": ["fitness", "casual-use"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["Bluetooth", "WiFi", "GPS"],
        "battery_life": "good",
        "portability": "highly-portable",
        "tags": ["samsung", "android", "health", "fitness", "wear-os"],
    },
    # Speakers
    {
        "name": "Bose SoundLink Flex",
        "brand": ["Bose"],
        "category": "speaker",
        "use_case": ["travel", "casual-use", "fitness"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["bose", "waterproof", "portable", "outdoor", "rugged"],
    },
    {
        "name": "Sony SRS-XB33",
        "brand": ["Sony"],
        "category": "speaker",
        "use_case": ["casual-use", "fitness", "travel"],
        "price_range": "budget",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C", "3.5mm"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["sony", "bass", "waterproof", "portable", "party"],
    },
    {
        "name": "JBL Charge 5",
        "brand": ["JBL"],
        "category": "speaker",
        "use_case": ["casual-use", "travel", "fitness"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "highly-portable",
        "tags": ["jbl", "charge", "powerbank", "waterproof", "portable"],
    },
    # Monitors
    {
        "name": "LG UltraFine 27UK850",
        "brand": ["LG"],
        "category": "monitor",
        "use_case": ["work", "content-creation", "home-office"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["USB-C", "HDMI", "DisplayPort"],
        "battery_life": "na",
        "portability": "desktop",
        "tags": ["lg", "4k", "usb-c", "color-accurate", "ips"],
    },
    {
        "name": "Dell UltraSharp 27",
        "brand": ["Dell"],
        "category": "monitor",
        "use_case": ["work", "professional", "home-office"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["USB-C", "HDMI", "DisplayPort", "USB-A"],
        "battery_life": "na",
        "portability": "desktop",
        "tags": ["dell", "ips", "4k", "professional", "color-accurate"],
    },
    {
        "name": "Asus TUF Gaming VG279QM",
        "brand": ["Asus"],
        "category": "monitor",
        "use_case": ["gaming"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["HDMI", "DisplayPort"],
        "battery_life": "na",
        "portability": "desktop",
        "tags": ["asus", "280hz", "gaming", "fast", "ips"],
    },
    # Keyboards
    {
        "name": "Logitech MX Keys",
        "brand": ["Logitech"],
        "category": "keyboard",
        "use_case": ["work", "home-office", "professional"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-A"],
        "battery_life": "excellent",
        "portability": "portable",
        "tags": ["logitech", "wireless", "backlit", "typing", "multi-device"],
    },
    {
        "name": "Apple Magic Keyboard",
        "brand": ["Apple"],
        "category": "keyboard",
        "use_case": ["work", "home-office", "casual-use"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["Bluetooth", "USB-C"],
        "battery_life": "excellent",
        "portability": "portable",
        "tags": ["apple", "wireless", "slim", "mac", "minimalist"],
    },
    # TVs
    {
        "name": "LG C3 OLED 65\"",
        "brand": ["LG"],
        "category": "tv",
        "use_case": ["casual-use", "gaming", "home-office"],
        "price_range": "premium",
        "condition": "new",
        "connectivity": ["HDMI", "WiFi", "Bluetooth", "USB"],
        "battery_life": "na",
        "portability": "desktop",
        "tags": ["lg", "oled", "4k", "dolby", "gaming", "premium"],
    },
    {
        "name": "Samsung Neo QLED 55\"",
        "brand": ["Samsung"],
        "category": "tv",
        "use_case": ["casual-use", "gaming"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["HDMI", "WiFi", "Bluetooth", "USB"],
        "battery_life": "na",
        "portability": "desktop",
        "tags": ["samsung", "qled", "4k", "hdr", "smart-tv"],
    },
    # Cameras
    {
        "name": "Sony Alpha ZV-E10",
        "brand": ["Sony"],
        "category": "camera",
        "use_case": ["content-creation", "casual-use", "professional"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["USB-C", "WiFi", "Bluetooth"],
        "battery_life": "average",
        "portability": "portable",
        "tags": ["sony", "mirrorless", "vlog", "content-creator", "aps-c"],
    },
    {
        "name": "Canon EOS R50",
        "brand": ["Canon"],
        "category": "camera",
        "use_case": ["casual-use", "content-creation", "travel"],
        "price_range": "mid",
        "condition": "new",
        "connectivity": ["USB-C", "WiFi", "Bluetooth"],
        "battery_life": "good",
        "portability": "portable",
        "tags": ["canon", "mirrorless", "beginner", "video", "aps-c"],
    },
]


# ── TRUST GRAPH DESIGN ────────────────────────────────────────────────────────
# Tech-savvy groups trust each other for electronics:
#   college_friends <-> young_professionals (highest overlap)
#   work_colleagues <-> young_professionals
#   foodies trust college_friends (gadget-adjacent)

ELECTRONICS_TRUST_PAIRS = [
    # (group_a, group_b, base_weight_range)
    ("college_friends",     "college_friends",     (0.70, 0.92)),
    ("young_professionals", "young_professionals", (0.72, 0.90)),
    ("work_colleagues",     "work_colleagues",     (0.65, 0.85)),
    ("college_friends",     "young_professionals", (0.55, 0.78)),
    ("young_professionals", "work_colleagues",     (0.50, 0.72)),
    ("foodies",             "college_friends",     (0.40, 0.65)),
]


def generate_products() -> list[dict]:
    now = datetime.now()
    out = []
    for p in PRODUCTS:
        created = now - timedelta(days=random.randint(30, 400))
        out.append({
            "id":               rand_uuid(),
            "name":             p["name"],
            "brand":            p["brand"],
            "category":         p["category"],
            "use_case":         p["use_case"],
            "price_range":      p["price_range"],
            "condition":        p["condition"],
            "connectivity":     p["connectivity"],
            "battery_life":     p["battery_life"],
            "portability":      p["portability"],
            "tags":             p["tags"],
            "avg_outcome_score": round(random.uniform(0.55, 0.90), 2),
            "total_visits":     random.randint(3, 40),
            "trust_citations":  random.randint(5, 60),
            "active":           True,
            "created_at":       created.isoformat(),
            "updated_at":       (now - timedelta(days=random.randint(0, 30))).isoformat(),
        })
    return out


def generate_trust_edges(users: list[dict]) -> list[dict]:
    """Generate electronics trust edges between tech-savvy user groups."""
    group_map: dict[str, list[dict]] = {}
    for u in users:
        g = u.get("friend_group", "none")
        group_map.setdefault(g, []).append(u)

    edges = []
    seen  = set()  # (from_id, to_id) — one edge per direction pair

    for group_a, group_b, (w_low, w_high) in ELECTRONICS_TRUST_PAIRS:
        members_a = group_map.get(group_a, [])
        members_b = group_map.get(group_b, [])

        for ua in members_a:
            # Each user trusts 2-4 people in the target group
            targets = random.sample(members_b, min(len(members_b), random.randint(2, 4)))
            for ub in targets:
                if ua["id"] == ub["id"]:
                    continue
                if (ua["id"], ub["id"]) in seen:
                    continue
                seen.add((ua["id"], ub["id"]))

                weight = round(random.uniform(w_low, w_high), 2)
                last_r = rand_date(180, 7)
                edges.append({
                    "id":                   rand_uuid(),
                    "from_user_id":         ua["id"],
                    "to_user_id":           ub["id"],
                    "domain":               "electronics",
                    "weight":               weight,
                    "basis":                "explicit",
                    "explicit_count":       random.randint(1, 6),
                    "implicit_count":       random.randint(2, 15),
                    "explicit_decay_clock": last_r,
                    "implicit_decay_clock": last_r,
                    "last_reinforced_at":   last_r,
                    "decay_rate":           round(random.uniform(0.005, 0.012), 4),
                    "status":               "active",
                    "created_at":           rand_date(400, 200),
                    "updated_at":           last_r,
                })

    return edges


ELECTRONICS_QUERIES = [
    ("I need a laptop for work from home, good battery life",
     {"category": {"value": "laptop", "constraint": "hard"},
      "use_case": {"value": ["work", "home-office"], "constraint": "soft"},
      "battery_life": {"value": "excellent", "constraint": "soft"}}),

    ("Looking for premium noise-cancelling headphones for travel",
     {"category": {"value": "headphones", "constraint": "hard"},
      "price_range": {"value": "premium", "constraint": "soft"},
      "use_case": {"value": ["travel"], "constraint": "soft"}}),

    ("Budget phone with great battery, 5G",
     {"category": {"value": "phone", "constraint": "hard"},
      "price_range": {"value": "budget", "constraint": "soft"},
      "battery_life": {"value": "excellent", "constraint": "soft"}}),

    ("Gaming laptop under mid-range budget",
     {"category": {"value": "laptop", "constraint": "hard"},
      "use_case": {"value": ["gaming"], "constraint": "soft"},
      "price_range": {"value": "mid", "constraint": "soft"}}),

    ("Sony or Apple earphones for gym use",
     {"category": {"value": "headphones", "constraint": "hard"},
      "brand": {"value": ["Sony", "Apple"], "constraint": "soft"},
      "use_case": {"value": ["fitness"], "constraint": "soft"}}),

    ("Best MacBook for a CS student",
     {"category": {"value": "laptop", "constraint": "hard"},
      "brand": {"value": ["Apple"], "constraint": "soft"},
      "use_case": {"value": ["student", "work"], "constraint": "soft"}}),

    ("4K monitor for video editing",
     {"category": {"value": "monitor", "constraint": "hard"},
      "use_case": {"value": ["content-creation"], "constraint": "soft"}}),

    ("Portable Bluetooth speaker for outdoor trips",
     {"category": {"value": "speaker", "constraint": "hard"},
      "use_case": {"value": ["travel", "fitness"], "constraint": "soft"},
      "portability": {"value": "highly-portable", "constraint": "soft"}}),

    ("Samsung flagship phone",
     {"category": {"value": "phone", "constraint": "hard"},
      "brand": {"value": ["Samsung"], "constraint": "soft"},
      "price_range": {"value": "premium", "constraint": "soft"}}),

    ("Smartwatch for fitness tracking",
     {"category": {"value": "smartwatch", "constraint": "hard"},
      "use_case": {"value": ["fitness"], "constraint": "soft"}}),
]


def generate_interactions(users: list[dict], products: list[dict]) -> list[dict]:
    """Generate ~80-100 electronics interactions across users and products."""
    interactions = []
    now = datetime.now()

    # Build a product index by category for realistic query→product pairing
    cat_products: dict[str, list[dict]] = {}
    for p in products:
        cat_products.setdefault(p["category"], []).append(p)

    # Active electronics users: college_friends + young_professionals + work_colleagues
    active_groups = {"college_friends", "young_professionals", "work_colleagues", "foodies"}
    active_users  = [u for u in users if u.get("friend_group") in active_groups]

    outcomes = ["positive", "positive", "positive", "neutral", "negative"]

    for _ in range(90):
        user   = random.choice(active_users)
        query, intent_fields = random.choice(ELECTRONICS_QUERIES)

        # Extract category from intent to pick a matching product
        cat   = intent_fields.get("category", {}).get("value", "phone")
        pool  = cat_products.get(cat, products)
        prod  = random.choice(pool)

        outcome        = random.choice(outcomes)
        outcome_scores = {"positive": 0.8, "neutral": 0.1, "negative": -0.6}
        visited_dt     = now - timedelta(days=random.randint(1, 200))

        interactions.append({
            "id":                  rand_uuid(),
            "user_id":             user["id"],
            "restaurant_id":       None,
            "product_id":          prod["id"],
            "recommended_by":      None,
            "trust_path_weight":   None,
            "trust_hops":          0,
            "intent_query":        query,
            "intent_parsed":       json.dumps({
                k: v["value"] for k, v in intent_fields.items()
            }),
            "outcome":             outcome,
            "outcome_score":       round(outcome_scores[outcome] + random.uniform(-0.1, 0.1), 2),
            "outcome_notes":       None,
            "outcome_recorded_at": (visited_dt + timedelta(days=1)).isoformat(),
            "visited_at":          visited_dt.isoformat(),
            "created_at":          visited_dt.isoformat(),
        })

    return interactions


def generate_source_trust(users: list[dict], products: list[dict],
                           interactions: list[dict]) -> list[dict]:
    """Derive source_trust from the interactions we generated."""
    from collections import defaultdict
    agg: dict[tuple, dict] = defaultdict(lambda: {
        "pos": 0, "neg": 0, "visits": 0, "weight": 0.3
    })

    prod_id_map = {p["id"]: p for p in products}

    for ix in interactions:
        if not ix.get("product_id"):
            continue
        key = (ix["user_id"], ix["product_id"])
        a   = agg[key]
        a["visits"] += 1
        if ix["outcome"] == "positive":
            a["pos"]    += 1
            a["weight"]  = min(1.0, a["weight"] + 0.05)
        elif ix["outcome"] in ("negative", "regret"):
            a["neg"]    += 1
            a["weight"]  = max(0.0, a["weight"] - 0.03)

    now = datetime.now()
    rows = []
    for (user_id, prod_id), data in agg.items():
        rows.append({
            "id":                    rand_uuid(),
            "user_id":               user_id,
            "restaurant_id":         None,
            "product_id":            prod_id,
            "domain":                "electronics",
            "weight":                round(data["weight"], 3),
            "visit_count":           data["visits"],
            "positive_outcome_count": data["pos"],
            "negative_outcome_count": data["neg"],
            "last_visited_at":       now.isoformat(),
            "status":                "active",
            "created_at":            now.isoformat(),
            "updated_at":            now.isoformat(),
        })
    return rows


# ── SEEDER ────────────────────────────────────────────────────────────────────

def seed_to_db(products, trust_edges, interactions, source_trust):
    import psycopg2
    from psycopg2.extras import execute_values, Json

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(url)
    cur  = conn.cursor()

    # Products
    print(f"  Seeding {len(products)} products...")
    execute_values(cur, """
        INSERT INTO products
          (id, name, brand, category, use_case, price_range, condition,
           connectivity, battery_life, portability, tags,
           avg_outcome_score, total_visits, trust_citations, active, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        p["id"], p["name"], p["brand"], p["category"], p["use_case"],
        p["price_range"], p["condition"], p["connectivity"],
        p["battery_life"], p["portability"], p["tags"],
        p["avg_outcome_score"], p["total_visits"], p["trust_citations"],
        p["active"], p["created_at"], p["updated_at"],
    ) for p in products])

    # Trust edges
    print(f"  Seeding {len(trust_edges)} electronics trust edges...")
    execute_values(cur, """
        INSERT INTO trust_edges
          (id, from_user_id, to_user_id, domain, weight, basis,
           explicit_count, implicit_count, explicit_decay_clock, implicit_decay_clock,
           last_reinforced_at, decay_rate, status, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        e["id"], e["from_user_id"], e["to_user_id"], e["domain"], e["weight"],
        e["basis"], e["explicit_count"], e["implicit_count"],
        e["explicit_decay_clock"], e["implicit_decay_clock"],
        e["last_reinforced_at"], e["decay_rate"], e["status"],
        e["created_at"], e["updated_at"],
    ) for e in trust_edges])

    # Interactions
    print(f"  Seeding {len(interactions)} electronics interactions...")
    execute_values(cur, """
        INSERT INTO interactions
          (id, user_id, restaurant_id, product_id, recommended_by,
           trust_path_weight, trust_hops, intent_query, intent_parsed,
           outcome, outcome_score, outcome_notes, outcome_recorded_at,
           visited_at, created_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        i["id"], i["user_id"], i["restaurant_id"], i["product_id"],
        i["recommended_by"], i["trust_path_weight"], i["trust_hops"],
        i["intent_query"], Json(json.loads(i["intent_parsed"])),
        i["outcome"], i["outcome_score"], i["outcome_notes"],
        i["outcome_recorded_at"], i["visited_at"], i["created_at"],
    ) for i in interactions])

    # Source trust
    print(f"  Seeding {len(source_trust)} electronics source_trust rows...")
    execute_values(cur, """
        INSERT INTO source_trust
          (id, user_id, restaurant_id, product_id, domain, weight,
           visit_count, positive_outcome_count, negative_outcome_count,
           last_visited_at, status, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, [(
        st["id"], st["user_id"], st["restaurant_id"], st["product_id"],
        st["domain"], st["weight"], st["visit_count"],
        st["positive_outcome_count"], st["negative_outcome_count"],
        st["last_visited_at"], st["status"], st["created_at"], st["updated_at"],
    ) for st in source_trust])

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Electronics data seeded.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate electronics simulation data")
    parser.add_argument("--seed", action="store_true", help="Seed generated data to DB")
    args = parser.parse_args()

    users = load_users()
    print(f"Loaded {len(users)} users")

    print("Generating products...")
    products = generate_products()

    print("Generating electronics trust edges...")
    trust_edges = generate_trust_edges(users)

    print("Generating electronics interactions...")
    interactions = generate_interactions(users, products)

    print("Generating source trust...")
    source_trust = generate_source_trust(users, products, interactions)

    # Save JSON files
    (DATA_DIR / "products.json").write_text(json.dumps(products, indent=2))
    print(f"  Saved products.json ({len(products)} items)")

    (DATA_DIR / "electronics_trust_edges.json").write_text(json.dumps(trust_edges, indent=2))
    print(f"  Saved electronics_trust_edges.json ({len(trust_edges)} items)")

    (DATA_DIR / "electronics_interactions.json").write_text(json.dumps(interactions, indent=2))
    print(f"  Saved electronics_interactions.json ({len(interactions)} items)")

    (DATA_DIR / "electronics_source_trust.json").write_text(json.dumps(source_trust, indent=2))
    print(f"  Saved electronics_source_trust.json ({len(source_trust)} items)")

    if args.seed:
        print("\nSeeding to database...")
        seed_to_db(products, trust_edges, interactions, source_trust)
    else:
        print("\nRun with --seed to push data to the database.")


if __name__ == "__main__":
    main()

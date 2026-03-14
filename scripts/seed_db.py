"""
UNIVERSAL CONNECTOR — Database Seeder
Phase 1: Restaurants Domain

Seeds all simulation data into Postgres.
Works with both local Postgres and Supabase.

Usage:
  python scripts/seed_db.py

Requires:
  pip install psycopg2-binary python-dotenv
  .env file with DATABASE_URL set
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import execute_values, Json
except ImportError:
    print("❌ Missing dependency. Run: pip install psycopg2-binary python-dotenv")
    sys.exit(1)

# ── SETUP ─────────────────────────────────────────────────────────────────────
load_dotenv()
DATA_DIR = Path(__file__).parent.parent / "simulation" / "data"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not set in .env file")
    print("   Create a .env file with:")
    print("   DATABASE_URL=postgresql://user:password@host:port/dbname")
    sys.exit(1)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def load(filename):
    with open(DATA_DIR / filename) as f:
        return json.load(f)

def connect():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Connected to database")
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

# ── SEEDERS ───────────────────────────────────────────────────────────────────
def seed_restaurants(cur, data):
    print(f"  Seeding {len(data)} restaurants...")
    rows = [(
        r["id"], r["name"], r["area"], r["city"],
        r["cuisine"], r["vibe"], r["occasion"],
        r["price_range"], r["noise_level"],
        r["seating_type"], r["parking"], r["tags"],
        r["avg_outcome_score"], r["total_visits"],
        r["trust_citations"], r["verified"], r["active"],
        r["created_at"], r["updated_at"]
    ) for r in data]

    execute_values(cur, """
        INSERT INTO restaurants (
            id, name, area, city,
            cuisine, vibe, occasion,
            price_range, noise_level,
            seating_type, parking, tags,
            avg_outcome_score, total_visits,
            trust_citations, verified, active,
            created_at, updated_at
        ) VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, rows)
    print(f"  ✅ Restaurants seeded")

def seed_users(cur, data):
    print(f"  Seeding {len(data)} users...")
    rows = [(
        u["id"], u["name"], u["email"],
        u["age_range"], u["area"], u["city"], u["friend_group"],
        u["trust_received_overall"], u["trust_received_restaurants"],
        u["trust_given_overall"], u["trust_given_restaurants"],
        u["last_active_restaurants"], u["cold_start_flag"],
        u["is_simulated"], u["created_at"], u["updated_at"]
    ) for u in data]

    execute_values(cur, """
        INSERT INTO users (
            id, name, email,
            age_range, area, city, friend_group,
            trust_received_overall, trust_received_restaurants,
            trust_given_overall, trust_given_restaurants,
            last_active_restaurants, cold_start_flag,
            is_simulated, created_at, updated_at
        ) VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, rows)
    print(f"  ✅ Users seeded")

def seed_trust_edges(cur, data):
    print(f"  Seeding {len(data)} trust edges...")
    # Strip internal flags before inserting
    rows = [(
        e["id"], e["from_user_id"], e["to_user_id"], e["domain"],
        e["weight"], e["basis"],
        e["explicit_count"], e["implicit_count"],
        e["explicit_decay_clock"], e["implicit_decay_clock"],
        e["last_reinforced_at"], e["decay_rate"], e["status"],
        e["created_at"], e["updated_at"]
    ) for e in data]

    execute_values(cur, """
        INSERT INTO trust_edges (
            id, from_user_id, to_user_id, domain,
            weight, basis,
            explicit_count, implicit_count,
            explicit_decay_clock, implicit_decay_clock,
            last_reinforced_at, decay_rate, status,
            created_at, updated_at
        ) VALUES %s
        ON CONFLICT (from_user_id, to_user_id, domain) DO NOTHING
    """, rows)
    print(f"  ✅ Trust edges seeded")

def seed_interactions(cur, data):
    print(f"  Seeding {len(data)} interactions...")
    rows = [(
        i["id"], i["user_id"], i["restaurant_id"],
        i["recommended_by"], i["trust_path_weight"], i["trust_hops"],
        i["intent_query"],
        Json(json.loads(i["intent_parsed"])) if i["intent_parsed"] else None,
        i["outcome"], i["outcome_score"], i["outcome_notes"],
        i["outcome_recorded_at"], i["visited_at"], i["created_at"]
    ) for i in data]

    execute_values(cur, """
        INSERT INTO interactions (
            id, user_id, restaurant_id,
            recommended_by, trust_path_weight, trust_hops,
            intent_query, intent_parsed,
            outcome, outcome_score, outcome_notes,
            outcome_recorded_at, visited_at, created_at
        ) VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, rows)
    print(f"  ✅ Interactions seeded")

def seed_source_trust(cur, data):
    print(f"  Seeding {len(data)} source trust records...")
    rows = [(
        s["id"], s["user_id"], s["restaurant_id"], s["domain"],
        s["weight"], s["visit_count"],
        s["positive_outcome_count"], s["negative_outcome_count"],
        s["last_visited_at"], s["status"],
        s["created_at"], s["updated_at"]
    ) for s in data]

    execute_values(cur, """
        INSERT INTO source_trust (
            id, user_id, restaurant_id, domain,
            weight, visit_count,
            positive_outcome_count, negative_outcome_count,
            last_visited_at, status,
            created_at, updated_at
        ) VALUES %s
        ON CONFLICT (user_id, restaurant_id) DO NOTHING
    """, rows)
    print(f"  ✅ Source trust seeded")

# ── VERIFICATION ──────────────────────────────────────────────────────────────
def verify(cur):
    print("\n🔍 Verifying seeded data...")
    checks = [
        ("restaurants",  "SELECT COUNT(*) FROM restaurants"),
        ("users",        "SELECT COUNT(*) FROM users"),
        ("trust_edges",  "SELECT COUNT(*) FROM trust_edges"),
        ("interactions", "SELECT COUNT(*) FROM interactions"),
        ("source_trust", "SELECT COUNT(*) FROM source_trust"),
    ]
    for name, query in checks:
        cur.execute(query)
        count = cur.fetchone()[0]
        print(f"  {name:15}: {count:>5} records")

    # Quick sanity checks
    cur.execute("SELECT COUNT(*) FROM trust_edges WHERE status = 'decaying'")
    decaying = cur.fetchone()[0]
    print(f"\n  Decaying edges : {decaying}")

    cur.execute("SELECT COUNT(*) FROM users WHERE cold_start_flag = true")
    cold = cur.fetchone()[0]
    print(f"  Cold start users: {cold}")

    cur.execute("""
        SELECT COUNT(*) FROM interactions
        WHERE outcome = 'positive'
        AND trust_hops = 1
    """)
    trust_positive = cur.fetchone()[0]
    print(f"  Trust-pathed positive outcomes: {trust_positive}")

    cur.execute("""
        SELECT COUNT(*) FROM interactions
        WHERE outcome IN ('negative', 'regret')
        AND trust_hops = 1
        AND trust_path_weight > 0.6
    """)
    conflict = cur.fetchone()[0]
    print(f"  Conflict scenarios (high trust, bad outcome): {conflict}")

    print("\n✅ Verification complete")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🚀 Universal Connector — Database Seeder")
    print("=" * 50)

    # Check data files exist
    required = ["restaurants.json", "users.json", "trust_edges.json",
                "interactions.json", "source_trust.json"]
    for f in required:
        if not (DATA_DIR / f).exists():
            print(f"❌ Missing: simulation/data/{f}")
            print("   Run: python simulation/generator.py first")
            sys.exit(1)

    print("\n📂 Loading simulation data...")
    restaurants  = load("restaurants.json")
    users        = load("users.json")
    trust_edges  = load("trust_edges.json")
    interactions = load("interactions.json")
    source_trust = load("source_trust.json")
    print("✅ All data files loaded")

    conn = connect()
    cur  = conn.cursor()

    print("\n📥 Seeding data...")
    try:
        seed_restaurants(cur, restaurants)
        seed_users(cur, users)
        seed_trust_edges(cur, trust_edges)
        seed_interactions(cur, interactions)
        seed_source_trust(cur, source_trust)
        conn.commit()
        print("\n✅ All data committed to database")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Seeding failed: {e}")
        raise
    finally:
        cur.close()

    # Verify
    cur = conn.cursor()
    verify(cur)
    cur.close()
    conn.close()

    print("\n✅ Database ready for Phase 1 build")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    main()

"""
UNIVERSAL CONNECTOR — Community + Ghost Source Seed Data Generator
Phase MVP: Steps 3 & 4 — the core vision

Generates:
  - user_community.json   — community memberships (village/profession/neighborhood)
  - ghost_sources.json    — offline sources entered by reference

Run: python simulation/community_ghost_generator.py
Reads: simulation/data/users.json (must exist — run generator.py first)

The community data is what makes community_trust layer fire.
The ghost data is what makes ghost_matches appear in search results.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(99)

DATA_DIR   = Path(__file__).parent / "data"
OUTPUT_DIR = DATA_DIR

def new_id():
    return str(uuid.uuid4())

def random_date(days_back_min=1, days_back_max=180):
    days_back = random.randint(days_back_min, days_back_max)
    return (datetime.now() - timedelta(days=days_back)).isoformat()

def save(filename, data):
    path = OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✅ {filename}: {len(data)} records")


# ══════════════════════════════════════════════════════════════════════════════
# 1. USER COMMUNITY MEMBERSHIPS
# ══════════════════════════════════════════════════════════════════════════════
# Map users to real-world community contexts.
# Users in the same context will discover each other via community_trust layer.

# Village clusters — users from the same native place
VILLAGE_CLUSTERS = [
    ("Mandya", 5),       # 5 users from Mandya
    ("Mysore", 4),
    ("Tumkur", 3),
    ("Hassan", 4),
    ("Dharwad", 3),
]

# Profession clusters
PROFESSION_CLUSTERS = [
    ("Software Engineer", 8),
    ("Doctor", 4),
    ("Lawyer", 3),
    ("Teacher", 4),
    ("Entrepreneur", 5),
]

# Neighborhood clusters (current residence in Bangalore)
NEIGHBORHOOD_CLUSTERS = [
    ("Koramangala", 6),
    ("Indiranagar", 5),
    ("HSR Layout",  5),
    ("Whitefield",  4),
]


def generate_user_community(users: list) -> list:
    """
    Assign community memberships to users.
    Each user gets 1-3 community memberships across different context types.
    """
    user_ids = [u["id"] for u in users if not u.get("cold_start_flag")]
    random.shuffle(user_ids)

    memberships = []
    used = set()   # (user_id, context_type, context_value) — no duplicates

    def assign(pool_ids, context_type, context_value):
        for uid in pool_ids:
            key = (uid, context_type, context_value)
            if key not in used:
                used.add(key)
                memberships.append({
                    "id":            new_id(),
                    "user_id":       uid,
                    "context_type":  context_type,
                    "context_value": context_value,
                    "created_at":    random_date(30, 365),
                })

    # Assign village memberships
    idx = 0
    for village, count in VILLAGE_CLUSTERS:
        batch = user_ids[idx : idx + count]
        assign(batch, "village", village)
        idx += count

    # Assign profession memberships (overlap OK — same user can have profession + village)
    idx = 0
    shuffled = user_ids[:]
    random.shuffle(shuffled)
    for profession, count in PROFESSION_CLUSTERS:
        batch = shuffled[idx : idx + count]
        assign(batch, "profession", profession)
        idx += count

    # Assign neighborhood memberships
    idx = 0
    random.shuffle(shuffled)
    for neighborhood, count in NEIGHBORHOOD_CLUSTERS:
        batch = shuffled[idx : idx + count]
        assign(batch, "neighborhood", neighborhood)
        idx += count

    return memberships


# ══════════════════════════════════════════════════════════════════════════════
# 2. GHOST SOURCES
# ══════════════════════════════════════════════════════════════════════════════
# Offline restaurants + food sellers entered by reference.
# These are the "connection that already exists" — just not yet on the platform.

GHOST_RESTAURANT_TEMPLATES = [
    {
        "name":         "Ravi's Udupi Kitchen",
        "description":  "Family-run udupi spot near Mandya bus stand, only locals know about it",
        "attributes": {
            "cuisine":     ["South Indian"],
            "vibe":        ["casual", "authentic"],
            "occasion":    ["casual dining"],
            "price_range": "budget",
            "noise_level": "moderate",
            "area":        "Mandya",
        },
        "contact_hint":  "Ask for Ravi anna near the Mandya bus stand, open 7am-2pm",
        "location_hint": "100m from Mandya old bus stand, no board outside",
        "community_tags": ["village:Mandya", "south-indian-authentic"],
    },
    {
        "name":         "Ammaji's Home Food",
        "description":  "Home-cooked Karnataka meals, only for referrals, WhatsApp order",
        "attributes": {
            "cuisine":     ["South Indian", "North Karnataka"],
            "vibe":        ["homely", "authentic"],
            "occasion":    ["lunch", "casual dining"],
            "price_range": "budget",
            "noise_level": "quiet",
            "area":        "HSR Layout",
        },
        "contact_hint":  "WhatsApp +91-98XXXXXX — mention you were referred",
        "location_hint": "HSR Layout Sector 2, apartment complex, no walk-ins",
        "community_tags": ["home-food", "referral-only"],
    },
    {
        "name":         "Shivanna's Dhaba",
        "description":  "Truck driver dhaba on Tumkur highway, legendary mutton curry",
        "attributes": {
            "cuisine":     ["North Karnataka", "Non-Veg"],
            "vibe":        ["rustic", "casual"],
            "occasion":    ["casual dining"],
            "price_range": "budget",
            "noise_level": "loud",
            "area":        "Tumkur Road",
        },
        "contact_hint":  "60km on Tumkur NH48, look for green board",
        "location_hint": "Near Nelamangala toll, on the left side going towards Tumkur",
        "community_tags": ["village:Tumkur", "highway-dhaba"],
    },
    {
        "name":         "Dr. Patel's Dabba Service",
        "description":  "Gujarati food tiffin, only for doctors at Manipal hospital",
        "attributes": {
            "cuisine":     ["Gujarati"],
            "vibe":        ["homely"],
            "occasion":    ["lunch", "tiffin"],
            "price_range": "mid",
            "noise_level": "quiet",
            "area":        "Malleswaram",
        },
        "contact_hint":  "Call only — reference from hospital colleagues required",
        "location_hint": "Delivered to Manipal hospital area, no pickup",
        "community_tags": ["profession:Doctor", "hospital-community"],
    },
    {
        "name":         "Koramangala Rooftop Mess",
        "description":  "Unmarked mess on 4th floor, beloved by startup founders in Koramangala",
        "attributes": {
            "cuisine":     ["South Indian", "North Indian"],
            "vibe":        ["casual", "quirky"],
            "occasion":    ["lunch", "casual dining"],
            "price_range": "budget",
            "noise_level": "moderate",
            "area":        "Koramangala",
        },
        "contact_hint":  "Building 5B, 5th Cross, no elevator — just walk up",
        "location_hint": "Behind the HDFC bank, 4th floor, no sign",
        "community_tags": ["neighborhood:Koramangala", "startup-crowd"],
    },
]


def generate_ghost_sources(users: list) -> list:
    """
    Create ghost sources entered by real users in the simulation.
    The `entered_by` user becomes the trust signal for anyone who finds it.
    Prioritize users who have community memberships (village/neighborhood).
    """
    eligible_users = [u for u in users if not u.get("cold_start_flag")]
    ghost_sources  = []

    for i, template in enumerate(GHOST_RESTAURANT_TEMPLATES):
        entered_by = eligible_users[i % len(eligible_users)]
        ghost_sources.append({
            "id":              new_id(),
            "domain":          "restaurants",
            "name":            template["name"],
            "description":     template["description"],
            "attributes":      template["attributes"],
            "entered_by":      entered_by["id"],
            "contact_hint":    template["contact_hint"],
            "location_hint":   template["location_hint"],
            "community_tags":  template["community_tags"],
            "is_materialized": False,
            "materialized_to": None,
            "active":          True,
            "created_at":      random_date(7, 90),
            "updated_at":      random_date(1, 7),
        })

    return ghost_sources


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n🌐 Universal Connector — Community + Ghost Seed Generator")
    print("=" * 55)

    # Load existing users
    users_path = DATA_DIR / "users.json"
    if not users_path.exists():
        print("❌ simulation/data/users.json not found.")
        print("   Run: python simulation/generator.py first")
        return

    with open(users_path) as f:
        users = json.load(f)
    print(f"\n  Loaded {len(users)} users from users.json")

    print("\n🏘️  Generating community memberships...")
    community = generate_user_community(users)
    save("user_community.json", community)

    print("\n👻 Generating ghost sources...")
    ghosts = generate_ghost_sources(users)
    save("ghost_sources.json", ghosts)

    print("\n" + "=" * 55)
    print("✅ COMPLETE — Summary")
    print("=" * 55)

    by_type = {}
    for m in community:
        by_type[m["context_type"]] = by_type.get(m["context_type"], 0) + 1
    for k, v in sorted(by_type.items()):
        print(f"  Community [{k}]  : {v} memberships")
    print(f"  Ghost sources   : {len(ghosts)}")

    print("\n  Key demo scenario:")
    print("    User A + User B both have village:Mandya membership")
    print("    User B visited a restaurant → community_trust layer fires for User A")
    print("    Ghost sources appear in ghost_matches tier for network members")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()

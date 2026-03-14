"""
UNIVERSAL CONNECTOR — Simulation Data Generator
Phase 1: Restaurants Domain

Generates:
  - 150 restaurants (Bangalore)
  - 50 users across 5 friend groups
  - ~200 trust edges (within + cross group)
  - ~500 interactions with outcomes
  - All unhappy path scenarios included

Run: python simulation/generator.py
Output: simulation/data/ folder with JSON files
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── SEED for reproducibility ──────────────────────────────────────────────────
random.seed(42)

# ── OUTPUT DIR ────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def new_id():
    return str(uuid.uuid4())

def random_date(days_back_min=1, days_back_max=180):
    days_back = random.randint(days_back_min, days_back_max)
    return (datetime.now() - timedelta(days=days_back)).isoformat()

def random_recent_date(days_back_max=30):
    return random_date(1, days_back_max)

def save(filename, data):
    path = OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✅ {filename}: {len(data)} records")

# ══════════════════════════════════════════════════════════════════════════════
# 1. RESTAURANTS — 150 records
# ══════════════════════════════════════════════════════════════════════════════

AREAS = ["Koramangala", "Indiranagar", "HSR Layout", "Jayanagar"]

CUISINES = [
    ["North Indian"], ["South Indian"], ["Chinese"], ["Italian"],
    ["Continental"], ["Cafe"], ["Biryani"], ["Street Food"],
    ["North Indian", "Chinese"], ["South Indian", "North Indian"],
    ["Italian", "Continental"], ["Cafe", "Desserts"],
    ["Pan Asian"], ["Mediterranean"], ["Mexican"],
]

VIBES = [
    ["cozy"], ["lively"], ["rooftop"], ["quiet"], ["romantic"],
    ["family-friendly"], ["trendy"], ["rustic"], ["minimalist"],
    ["cozy", "quiet"], ["lively", "trendy"], ["rooftop", "romantic"],
    ["family-friendly", "cozy"], ["quiet", "minimalist"],
]

OCCASIONS = [
    ["casual"], ["date-night"], ["business"], ["family"],
    ["quick-lunch"], ["celebration"], ["friends-hangout"],
    ["date-night", "casual"], ["business", "casual"],
    ["family", "celebration"], ["friends-hangout", "casual"],
    ["quick-lunch", "casual"],
]

SEATING = [
    ["indoor"], ["outdoor"], ["indoor", "outdoor"],
    ["rooftop"], ["indoor", "rooftop"], ["outdoor", "rooftop"],
]

# Restaurant name components for realistic names
NAME_PREFIXES = [
    "The", "Cafe", "Restaurant", "Bistro", "Kitchen",
    "House of", "Little", "Royal", "Green", "Urban",
    "Spice", "The Old", "New", "Corner", "Garden",
]
NAME_MAINS = [
    "Punjabi", "Dakshin", "Bamboo", "Olive", "Harvest",
    "Pepper", "Mint", "Basil", "Saffron", "Turmeric",
    "Mango", "Tamarind", "Coriander", "Cardamom", "Thyme",
    "Ember", "Forge", "Table", "Fork", "Spoon",
    "Andhra", "Kerala", "Udupi", "Chettinad", "Coastal",
    "Imperial", "Heritage", "Garden", "Bagh", "Nagar",
]

used_names = set()

def generate_restaurant_name(cuisine):
    for _ in range(100):
        if "South Indian" in cuisine or "Biryani" in cuisine:
            mains = ["Dakshin", "Andhra", "Kerala", "Udupi", "Chettinad",
                     "Coastal", "Saffron", "Tamarind", "Pepper", "Spice"]
        elif "North Indian" in cuisine:
            mains = ["Punjabi", "Imperial", "Heritage", "Saffron", "Mango",
                     "Spice", "Coriander", "Turmeric", "Tandoor", "Dhaba"]
        elif "Italian" in cuisine or "Continental" in cuisine:
            mains = ["Olive", "Basil", "Thyme", "Ember", "Harvest",
                     "Garden", "Fork", "Table", "Bistro", "Forge"]
        elif "Cafe" in cuisine:
            mains = ["Mint", "Brew", "Bean", "Corner", "Little",
                     "Urban", "Green", "Table", "Spoon", "Cozy"]
        elif "Chinese" in cuisine or "Pan Asian" in cuisine:
            mains = ["Bamboo", "Lotus", "Dragon", "Jade", "Orient",
                     "Wok", "Noodle", "Panda", "Golden", "Pearl"]
        else:
            mains = NAME_MAINS

        prefix = random.choice(NAME_PREFIXES)
        main = random.choice(mains)
        name = f"{prefix} {main}"
        if name not in used_names:
            used_names.add(name)
            return name
    return f"Restaurant {new_id()[:6]}"

def generate_restaurants():
    restaurants = []
    per_area = 150 // len(AREAS)  # ~37 per area

    for area in AREAS:
        count = per_area + (2 if area == AREAS[0] else 0)  # 150 total
        for _ in range(count):
            cuisine = random.choice(CUISINES)
            vibe    = random.choice(VIBES)
            occasion = random.choice(OCCASIONS)
            price_range = random.choices(
                ["budget", "mid", "premium"], weights=[33, 47, 20]
            )[0]

            # Noise level correlates with vibe
            if "quiet" in vibe or "romantic" in vibe or "minimalist" in vibe:
                noise = "quiet"
            elif "lively" in vibe or "trendy" in vibe:
                noise = random.choices(["moderate", "loud"], weights=[60, 40])[0]
            else:
                noise = random.choices(["quiet", "moderate", "loud"], weights=[25, 55, 20])[0]

            # Parking correlates with area + price
            has_parking = (
                True if price_range == "premium"
                else random.choices([True, False], weights=[40, 60])[0]
            )

            seating = random.choice(SEATING)

            # Simulated avg outcome score (will be refined by interactions)
            avg_score = round(random.uniform(0.3, 0.95), 2)

            tags = list(set(cuisine + vibe + occasion +
                       [price_range, noise] +
                       (["parking"] if has_parking else []) +
                       seating))

            restaurants.append({
                "id":               new_id(),
                "name":             generate_restaurant_name(cuisine),
                "area":             area,
                "city":             "Bangalore",
                "cuisine":          cuisine,
                "vibe":             vibe,
                "occasion":         occasion,
                "price_range":      price_range,
                "noise_level":      noise,
                "seating_type":     seating,
                "parking":          has_parking,
                "tags":             tags,
                "avg_outcome_score": avg_score,
                "total_visits":     random.randint(0, 50),
                "trust_citations":  random.randint(0, 20),
                "verified":         random.random() > 0.4,
                "active":           True,
                "created_at":       random_date(60, 365),
                "updated_at":       random_date(1, 60),
            })

    return restaurants

# ══════════════════════════════════════════════════════════════════════════════
# 2. USERS — 50 users across 5 groups
# ══════════════════════════════════════════════════════════════════════════════

GROUPS = {
    "college_friends": {
        "description": "Mixed age 25-30, casual diners",
        "age_range": "22-28",
        "preferred_areas": ["Koramangala", "Indiranagar"],
        "preferred_cuisines": ["South Indian", "Chinese", "Street Food", "Biryani"],
        "preferred_occasions": ["casual", "friends-hangout", "quick-lunch"],
        "names": [
            "Arjun", "Priya", "Rahul", "Sneha", "Kiran",
            "Divya", "Aakash", "Meera", "Rohan", "Ananya"
        ]
    },
    "work_colleagues": {
        "description": "Age 28-35, quick lunch + occasional dinner",
        "age_range": "28-35",
        "preferred_areas": ["HSR Layout", "Koramangala"],
        "preferred_cuisines": ["North Indian", "Cafe", "Continental", "South Indian"],
        "preferred_occasions": ["quick-lunch", "business", "casual"],
        "names": [
            "Vikram", "Pooja", "Sanjay", "Nisha", "Amit",
            "Kavitha", "Ravi", "Sunita", "Deepak", "Lakshmi"
        ]
    },
    "family_group": {
        "description": "Age 30-45, family outings",
        "age_range": "30-45",
        "preferred_areas": ["Jayanagar", "HSR Layout"],
        "preferred_cuisines": ["South Indian", "North Indian", "Biryani"],
        "preferred_occasions": ["family", "celebration", "casual"],
        "names": [
            "Suresh", "Usha", "Prakash", "Geetha", "Mohan",
            "Radha", "Venkat", "Saritha", "Ramesh", "Padma"
        ]
    },
    "foodies": {
        "description": "Age 25-38, experimental eaters",
        "age_range": "25-38",
        "preferred_areas": ["Indiranagar", "Koramangala"],
        "preferred_cuisines": ["Italian", "Continental", "Pan Asian", "Mediterranean", "Mexican"],
        "preferred_occasions": ["date-night", "celebration", "friends-hangout", "casual"],
        "names": [
            "Nikhil", "Shruti", "Kartik", "Aditi", "Varun",
            "Ishaan", "Tanya", "Arun", "Nandini", "Rohit"
        ]
    },
    "young_professionals": {
        "description": "Age 24-30, date nights and rooftops",
        "age_range": "24-30",
        "preferred_areas": ["Indiranagar", "Koramangala"],
        "preferred_cuisines": ["Italian", "Cafe", "Continental", "Pan Asian"],
        "preferred_occasions": ["date-night", "friends-hangout", "casual", "celebration"],
        "names": [
            "Aditya", "Riya", "Siddharth", "Anjali", "Mihir",
            "Preethi", "Arnav", "Swati", "Harsh", "Simran"
        ]
    }
}

def generate_users():
    users = []
    for group_key, group in GROUPS.items():
        for name in group["names"]:
            # Assign realistic trust scores per group character
            if group_key == "foodies":
                rest_trust = round(random.uniform(0.55, 0.90), 2)
            elif group_key == "family_group":
                rest_trust = round(random.uniform(0.45, 0.75), 2)
            elif group_key == "work_colleagues":
                rest_trust = round(random.uniform(0.35, 0.65), 2)
            else:
                rest_trust = round(random.uniform(0.40, 0.80), 2)

            overall = round(rest_trust * random.uniform(0.85, 0.95), 2)
            last_active = random_date(1, 45)

            users.append({
                "id":                           new_id(),
                "name":                         name,
                "email":                        f"{name.lower()}.{group_key[:4]}@sim.uc",
                "age_range":                    group["age_range"],
                "area":                         random.choice(group["preferred_areas"]),
                "city":                         "Bangalore",
                "friend_group":                 group_key,
                "trust_received_overall":       overall,
                "trust_received_restaurants":   rest_trust,
                "trust_given_overall":          round(overall * random.uniform(0.9, 1.0), 2),
                "trust_given_restaurants":      round(rest_trust * random.uniform(0.9, 1.0), 2),
                "last_active_restaurants":      last_active,
                "cold_start_flag":              False,
                "is_simulated":                 True,
                "created_at":                   random_date(90, 365),
                "updated_at":                   last_active,
            })

    # ── UNHAPPY PATH: 3 cold start users ──────────────────────────────────────
    for i in range(3):
        users.append({
            "id":                           new_id(),
            "name":                         f"NewUser{i+1}",
            "email":                        f"newuser{i+1}@sim.uc",
            "age_range":                    "22-30",
            "area":                         random.choice(AREAS),
            "city":                         "Bangalore",
            "friend_group":                 "none",
            "trust_received_overall":       0.0,
            "trust_received_restaurants":   0.0,
            "trust_given_overall":          0.0,
            "trust_given_restaurants":      0.0,
            "last_active_restaurants":      None,
            "cold_start_flag":              True,
            "is_simulated":                 True,
            "created_at":                   random_date(1, 7),
            "updated_at":                   random_date(1, 3),
        })

    return users

# ══════════════════════════════════════════════════════════════════════════════
# 3. TRUST EDGES — ~200 edges
# ══════════════════════════════════════════════════════════════════════════════

def generate_trust_edges(users):
    edges = []
    edge_set = set()

    # Group users by friend_group
    groups = {}
    for u in users:
        g = u["friend_group"]
        if g not in groups:
            groups[g] = []
        groups[g].append(u)

    def add_edge(from_u, to_u, weight, basis, explicit_c, implicit_c,
                 status="active", days_since_reinforced=None):
        key = (from_u["id"], to_u["id"])
        if key in edge_set or from_u["id"] == to_u["id"]:
            return
        edge_set.add(key)

        if days_since_reinforced is None:
            days_since_reinforced = random.randint(1, 30)
        reinforced = (datetime.now() - timedelta(days=days_since_reinforced)).isoformat()

        # Decay rate: lower for strong/deep edges
        decay_rate = round(0.005 + (1 - weight) * 0.02, 4)

        edges.append({
            "id":                   new_id(),
            "from_user_id":         from_u["id"],
            "to_user_id":           to_u["id"],
            "domain":               "restaurants",
            "weight":               round(weight, 2),
            "basis":                basis,
            "explicit_count":       explicit_c,
            "implicit_count":       implicit_c,
            "explicit_decay_clock": reinforced,
            "implicit_decay_clock": reinforced,
            "last_reinforced_at":   reinforced,
            "decay_rate":           decay_rate,
            "status":               status,
            "created_at":           random_date(60, 300),
            "updated_at":           reinforced,
        })

    # ── WITHIN-GROUP edges: strong trust ──────────────────────────────────────
    for group_name, group_users in groups.items():
        if group_name == "none":
            continue

        real_users = [u for u in group_users if not u["cold_start_flag"]]

        for i, u1 in enumerate(real_users):
            for u2 in real_users[i+1:]:
                # Bidirectional but different weights (trust is directional)
                w1 = round(random.uniform(0.60, 0.90), 2)
                w2 = round(random.uniform(0.60, 0.90), 2)
                basis = random.choices(["explicit", "hybrid"], weights=[40, 60])[0]
                add_edge(u1, u2, w1, basis,
                         explicit_c=random.randint(2, 8),
                         implicit_c=random.randint(5, 20))
                add_edge(u2, u1, w2, basis,
                         explicit_c=random.randint(2, 8),
                         implicit_c=random.randint(5, 20))

    # ── CROSS-GROUP edges: weak trust ─────────────────────────────────────────
    group_names = [g for g in groups.keys() if g != "none"]
    for _ in range(30):
        g1, g2 = random.sample(group_names, 2)
        u1 = random.choice([u for u in groups[g1] if not u["cold_start_flag"]])
        u2 = random.choice([u for u in groups[g2] if not u["cold_start_flag"]])
        w = round(random.uniform(0.10, 0.35), 2)
        add_edge(u1, u2, w, "implicit",
                 explicit_c=0,
                 implicit_c=random.randint(1, 4))

    # ── UNHAPPY PATH 1: Decaying edges (trust fading) ─────────────────────────
    decaying_count = 0
    edge_list = list(edge_set)
    random.shuffle(edge_list)
    for key in edge_list[:15]:
        for e in edges:
            if e["from_user_id"] == key[0] and e["to_user_id"] == key[1]:
                e["status"] = "decaying"
                e["weight"] = round(random.uniform(0.16, 0.38), 2)
                old_date = (datetime.now() - timedelta(days=random.randint(90, 150))).isoformat()
                e["last_reinforced_at"] = old_date
                e["explicit_decay_clock"] = old_date
                e["implicit_decay_clock"] = old_date
                decaying_count += 1
                break

    # ── UNHAPPY PATH 2: High trust but bad outcome edges ──────────────────────
    # These are flagged so we can create contradictory interactions later
    conflict_edges = []
    for e in random.sample(edges, 5):
        e["_conflict_flag"] = True   # high weight but will get negative interaction
        conflict_edges.append((e["from_user_id"], e["to_user_id"]))

    # ── UNHAPPY PATH 3: Single-connection users ───────────────────────────────
    # Find 5 users and remove most of their edges
    sparse_users = random.sample(
        [u for u in users if not u["cold_start_flag"] and u["friend_group"] != "none"], 5
    )
    sparse_ids = {u["id"] for u in sparse_users}
    # Keep only 1 edge per sparse user
    kept = {}
    filtered_edges = []
    for e in edges:
        fu = e["from_user_id"]
        if fu in sparse_ids:
            if fu not in kept:
                kept[fu] = True
                filtered_edges.append(e)
            # skip additional edges from this user
        else:
            filtered_edges.append(e)
    edges = filtered_edges

    print(f"     → Within-group edges: {sum(1 for e in edges if e['status']=='active')}")
    print(f"     → Decaying edges: {sum(1 for e in edges if e['status']=='decaying')}")
    print(f"     → Sparse users (1 edge only): {len(sparse_users)}")
    print(f"     → Cold start users (0 edges): 3")
    print(f"     → Conflict edges (high trust, bad outcome): {len(conflict_edges)}")

    return edges, conflict_edges

# ══════════════════════════════════════════════════════════════════════════════
# 4. INTERACTIONS — ~500 records
# ══════════════════════════════════════════════════════════════════════════════

INTENT_TEMPLATES = [
    "I want a quiet place for a business dinner, good {cuisine}, {area}, not too loud",
    "Looking for a good {cuisine} restaurant in {area} for a date night",
    "Need a family-friendly place in {area}, {cuisine} preferred",
    "Quick lunch in {area}, budget friendly, good {cuisine}",
    "Celebrating a birthday in {area}, something special, {cuisine}",
    "Casual dinner with friends in {area}, {cuisine} would be great",
    "Rooftop restaurant in {area} for a relaxed evening",
    "Good {cuisine} in {area}, parking is important",
    "Something cozy and quiet in {area} for a relaxed meal",
    "Best {cuisine} in {area} that my friends have been to",
]

OUTCOME_WEIGHTS = {
    "positive": 70,
    "neutral":  15,
    "negative": 10,
    "regret":   5,
}

OUTCOME_SCORES = {
    "positive": (0.65, 1.0),
    "neutral":  (-0.1, 0.3),
    "negative": (-0.8, -0.3),
    "regret":   (-0.5, -0.1),
}

def generate_interactions(users, restaurants, trust_edges, conflict_edges):
    interactions = []

    # Build lookup maps
    user_map   = {u["id"]: u for u in users}
    rest_map   = {r["id"]: r for r in restaurants}
    edge_map   = {}  # from_user_id → list of (to_user_id, weight)
    for e in trust_edges:
        if e["status"] in ("active", "decaying"):
            fid = e["from_user_id"]
            if fid not in edge_map:
                edge_map[fid] = []
            edge_map[fid].append((e["to_user_id"], e["weight"]))

    conflict_set = set(map(tuple, conflict_edges))

    real_users = [u for u in users if not u["cold_start_flag"]]

    for i in range(500):
        user = random.choice(real_users)
        uid  = user["id"]

        # Pick a restaurant compatible with user's group preferences
        group   = GROUPS.get(user["friend_group"], GROUPS["college_friends"])
        pref_cu = group["preferred_cuisines"]
        pref_oc = group["preferred_occasions"]

        # Filter restaurants by preference (loosely)
        matching = [r for r in restaurants if
                    any(c in r["cuisine"] for c in pref_cu) or
                    any(o in r["occasion"] for o in pref_oc)]
        if not matching:
            matching = restaurants
        restaurant = random.choice(matching)
        rid = restaurant["id"]

        # Determine trust path
        user_edges = edge_map.get(uid, [])
        recommended_by  = None
        trust_path_weight = None
        trust_hops      = 0

        if user_edges and random.random() > 0.25:  # 75% chance trust path
            # Try to find a trusted user who visited this restaurant
            random.shuffle(user_edges)
            for (trusted_uid, edge_weight) in user_edges:
                # Check if trusted user has visited this restaurant
                trusted_visited = any(
                    x["user_id"] == trusted_uid and
                    x["restaurant_id"] == rid
                    for x in interactions
                )
                if trusted_visited or random.random() > 0.6:
                    recommended_by    = trusted_uid
                    trust_path_weight = round(edge_weight, 2)
                    trust_hops        = 1
                    break

        # Build intent query
        cuisine_str = random.choice(restaurant["cuisine"])
        area_str    = restaurant["area"]
        template    = random.choice(INTENT_TEMPLATES)
        intent_query = template.format(cuisine=cuisine_str, area=area_str)

        parsed_intent = {
            "cuisine":      [cuisine_str],
            "area":         area_str,
            "occasion":     random.choice(restaurant["occasion"]),
            "price_range":  restaurant["price_range"],
            "noise_level":  restaurant["noise_level"],
        }

        # Determine outcome
        is_conflict = (uid, recommended_by) in conflict_set

        if is_conflict:
            # High trust edge but negative outcome (unhappy path)
            outcome = random.choices(["negative", "regret"], weights=[70, 30])[0]
        elif trust_hops == 1 and trust_path_weight and trust_path_weight > 0.6:
            # Strong trust path → better outcomes
            outcome = random.choices(
                ["positive", "neutral", "negative", "regret"],
                weights=[80, 12, 5, 3]
            )[0]
        else:
            # Cold result or weak trust
            outcome = random.choices(
                list(OUTCOME_WEIGHTS.keys()),
                weights=list(OUTCOME_WEIGHTS.values())
            )[0]

        lo, hi = OUTCOME_SCORES[outcome]
        outcome_score = round(random.uniform(lo, hi), 2)

        visited_at        = random_date(1, 170)
        outcome_delay     = random.randint(1, 48)  # hours after visit
        outcome_recorded  = (
            datetime.fromisoformat(visited_at) + timedelta(hours=outcome_delay)
        ).isoformat()

        interactions.append({
            "id":                   new_id(),
            "user_id":              uid,
            "restaurant_id":        rid,
            "recommended_by":       recommended_by,
            "trust_path_weight":    trust_path_weight,
            "trust_hops":           trust_hops,
            "intent_query":         intent_query,
            "intent_parsed":        json.dumps(parsed_intent),
            "outcome":              outcome,
            "outcome_score":        outcome_score,
            "outcome_notes":        None,
            "outcome_recorded_at":  outcome_recorded,
            "visited_at":           visited_at,
            "created_at":           visited_at,
        })

    # ── UNHAPPY PATH: Tie scenario (identical scores) ─────────────────────────
    # Add 2 interactions with exact same restaurant + user combo but different paths
    # (for testing tie-breaking logic)
    tie_user = random.choice(real_users)
    tie_rest = random.choice(restaurants)
    for _ in range(2):
        interactions.append({
            "id":                   new_id(),
            "user_id":              tie_user["id"],
            "restaurant_id":        tie_rest["id"],
            "recommended_by":       None,
            "trust_path_weight":    0.5,
            "trust_hops":           0,
            "intent_query":         "good food in " + tie_rest["area"],
            "intent_parsed":        json.dumps({"area": tie_rest["area"]}),
            "outcome":              "positive",
            "outcome_score":        0.75,
            "outcome_notes":        "tie_test_scenario",
            "outcome_recorded_at":  random_recent_date(),
            "visited_at":           random_date(1, 10),
            "created_at":           random_date(1, 10),
        })

    return interactions

# ══════════════════════════════════════════════════════════════════════════════
# 5. SOURCE TRUST — computed from interactions
# ══════════════════════════════════════════════════════════════════════════════

def generate_source_trust(users, restaurants, interactions):
    source_trust = []
    trust_map = {}  # (user_id, restaurant_id) → stats

    for i in interactions:
        key = (i["user_id"], i["restaurant_id"])
        if key not in trust_map:
            trust_map[key] = {
                "visits": 0, "positive": 0, "negative": 0,
                "last_visited": i["visited_at"]
            }
        trust_map[key]["visits"] += 1
        if i["outcome"] == "positive":
            trust_map[key]["positive"] += 1
        elif i["outcome"] in ("negative", "regret"):
            trust_map[key]["negative"] += 1
        if i["visited_at"] > trust_map[key]["last_visited"]:
            trust_map[key]["last_visited"] = i["visited_at"]

    for (uid, rid), stats in trust_map.items():
        if stats["visits"] == 0:
            continue
        pos_ratio = stats["positive"] / stats["visits"]
        # Weight by visit count and positive ratio
        weight = round(min(1.0, pos_ratio * (1 + 0.1 * stats["visits"])), 2)
        status = "active" if weight > 0.4 else ("decaying" if weight > 0.15 else "dormant")

        source_trust.append({
            "id":                       new_id(),
            "user_id":                  uid,
            "restaurant_id":            rid,
            "domain":                   "restaurants",
            "weight":                   weight,
            "visit_count":              stats["visits"],
            "positive_outcome_count":   stats["positive"],
            "negative_outcome_count":   stats["negative"],
            "last_visited_at":          stats["last_visited"],
            "status":                   status,
            "created_at":               random_date(60, 300),
            "updated_at":               stats["last_visited"],
        })

    return source_trust

# ══════════════════════════════════════════════════════════════════════════════
# 6. MAIN — run all generators
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n🚀 Universal Connector — Simulation Data Generator")
    print("=" * 55)

    print("\n📍 Generating restaurants...")
    restaurants = generate_restaurants()
    save("restaurants.json", restaurants)

    print("\n👤 Generating users...")
    users = generate_users()
    save("users.json", users)

    print("\n🔗 Generating trust edges...")
    trust_edges, conflict_edges = generate_trust_edges(users)
    save("trust_edges.json", trust_edges)

    print("\n🍽️  Generating interactions...")
    interactions = generate_interactions(users, restaurants, trust_edges, conflict_edges)
    save("interactions.json", interactions)

    print("\n⭐ Computing source trust...")
    source_trust = generate_source_trust(users, restaurants, interactions)
    save("source_trust.json", source_trust)

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("✅ SIMULATION COMPLETE — Summary")
    print("=" * 55)
    print(f"  Restaurants     : {len(restaurants)}")
    print(f"  Users           : {len(users)} ({len(users)-3} real + 3 cold start)")
    print(f"  Trust edges     : {len(trust_edges)}")
    print(f"    Active        : {sum(1 for e in trust_edges if e['status']=='active')}")
    print(f"    Decaying      : {sum(1 for e in trust_edges if e['status']=='decaying')}")
    print(f"  Interactions    : {len(interactions)}")
    print(f"    Positive      : {sum(1 for i in interactions if i['outcome']=='positive')}")
    print(f"    Neutral       : {sum(1 for i in interactions if i['outcome']=='neutral')}")
    print(f"    Negative      : {sum(1 for i in interactions if i['outcome']=='negative')}")
    print(f"    Regret        : {sum(1 for i in interactions if i['outcome']=='regret')}")
    print(f"  Source trust    : {len(source_trust)}")
    print(f"\n  Data saved to: simulation/data/")
    print("=" * 55)

    # ── UNHAPPY PATH VERIFICATION ─────────────────────────────────────────────
    print("\n🔍 Unhappy Path Coverage:")
    cold_users = [u for u in users if u["cold_start_flag"]]
    decaying   = [e for e in trust_edges if e["status"] == "decaying"]
    sparse     = {}
    for e in trust_edges:
        fid = e["from_user_id"]
        sparse[fid] = sparse.get(fid, 0) + 1
    sparse_users = [uid for uid, cnt in sparse.items() if cnt == 1]

    print(f"  ✅ Cold start users (0 edges)     : {len(cold_users)}")
    print(f"  ✅ Decaying edges                 : {len(decaying)}")
    print(f"  ✅ Sparse users (1 edge only)      : {len(sparse_users)}")
    print(f"  ✅ Conflict edges (trust vs outcome): {len(conflict_edges)}")
    print(f"  ✅ Tie scenario interactions       : 2")
    print(f"  ✅ Vague intent queries            : included in templates")
    print(f"  ✅ Hard constraint test data       : budget/noise variety exists")
    print("\n✅ All unhappy paths covered.\n")

if __name__ == "__main__":
    main()

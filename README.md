# Universal Connector — Phase 1
## Domain: Restaurants | Mode: Solo Stealth

---

## Project Structure

```
universal_connector/
├── db/
│   └── schema.sql          # Postgres table definitions
├── simulation/
│   ├── generator.py        # Generates all simulation data
│   └── data/               # Generated JSON files (git ignored)
│       ├── restaurants.json
│       ├── users.json
│       ├── trust_edges.json
│       ├── interactions.json
│       └── source_trust.json
├── scripts/
│   └── seed_db.py          # Seeds simulation data into Postgres
├── requirements.txt
├── .env.template
└── README.md
```

---

## Setup — From Scratch

### Step 1: Create a Supabase project
1. Go to https://supabase.com and create a free account
2. Create a new project (name it `universal-connector`)
3. Wait for it to provision (~2 minutes)
4. Go to: Project Settings → Database → Connection string → URI
5. Copy the connection string

### Step 2: Set up local environment
```bash
# Clone or create project folder
cd universal_connector

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.template .env
# Edit .env and paste your DATABASE_URL
```

### Step 3: Create database schema
```bash
# Option A — via Supabase SQL editor (recommended for first time)
# 1. Open Supabase dashboard
# 2. Go to SQL Editor
# 3. Paste contents of db/schema.sql
# 4. Click Run

# Option B — via psql
psql $DATABASE_URL -f db/schema.sql
```

### Step 4: Generate simulation data
```bash
python simulation/generator.py
```

Output:
```
✅ restaurants.json : 150 records
✅ users.json       : 53 records
✅ trust_edges.json : 439 records
✅ interactions.json: 502 records
✅ source_trust.json: 476 records
```

### Step 5: Seed database
```bash
python scripts/seed_db.py
```

Output:
```
✅ All data committed to database
restaurants    :   150 records
users          :    53 records
trust_edges    :   439 records
interactions   :   502 records
source_trust   :   476 records
```

---

## What Was Generated

### Restaurants (150)
- 4 areas: Koramangala, Indiranagar, HSR Layout, Jayanagar
- 15 cuisine types
- Full attribute coverage: vibe, occasion, price, noise, parking, seating

### Users (53)
- 50 real users across 5 friend groups
- 3 cold start users (no trust edges) — for testing

**Friend Groups:**
| Group | Profile | Size |
|---|---|---|
| college_friends | Casual diners, age 22-28 | 10 |
| work_colleagues | Quick lunch crowd, age 28-35 | 10 |
| family_group | Family outings, age 30-45 | 10 |
| foodies | Experimental eaters, age 25-38 | 10 |
| young_professionals | Date nights + rooftops, age 24-30 | 10 |

### Trust Edges (~439)
- ~425 active within-group edges (weight 0.6-0.9)
- ~14 decaying edges (testing decay logic)
- ~30 weak cross-group edges (weight 0.1-0.35)

### Interactions (~502)
- 70% positive, 15% neutral, 10% negative, 5% regret
- Trust-pathed results have better outcomes (validates core thesis)

### Unhappy Paths Covered
- ✅ 3 cold start users (zero trust edges)
- ✅ 14 decaying edges (trust fading over time)
- ✅ 5 sparse users (only 1 trust edge each)
- ✅ 5 conflict edges (high trust but bad outcome)
- ✅ Tie scenario (identical displacement scores)
- ✅ Vague intent queries
- ✅ Hard constraint test data

---

## Next Steps (Phase 1 Build)
1. Intent parser (GPT API)
2. Matching engine (SQL-based)
3. Trust path query
4. Displacement scoring
5. UI — 3 screens
6. Outcome capture flow

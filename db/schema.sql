-- ============================================================
-- UNIVERSAL CONNECTOR — Database Schema v1.0
-- Phase 1: Restaurants Domain
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLE 1: RESTAURANTS
-- Source nodes — the things being discovered
-- ============================================================
CREATE TABLE IF NOT EXISTS restaurants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    area                TEXT NOT NULL,
    city                TEXT NOT NULL DEFAULT 'Bangalore',

    -- Discovery attributes (matched against intent)
    cuisine             TEXT[]      NOT NULL,
    vibe                TEXT[]      NOT NULL,
    occasion            TEXT[]      NOT NULL,
    price_range         TEXT        NOT NULL CHECK (price_range IN ('budget', 'mid', 'premium')),
    noise_level         TEXT        NOT NULL CHECK (noise_level IN ('quiet', 'moderate', 'loud')),
    seating_type        TEXT[]      NOT NULL,
    parking             BOOLEAN     NOT NULL DEFAULT false,
    tags                TEXT[]      NOT NULL DEFAULT '{}',

    -- Computed quality signals
    avg_outcome_score   FLOAT       DEFAULT 0.0,
    total_visits        INTEGER     DEFAULT 0,
    trust_citations     INTEGER     DEFAULT 0,

    -- Meta
    verified            BOOLEAN     DEFAULT false,
    active              BOOLEAN     DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE 2: USERS
-- Person nodes — the people in the trust graph
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                        TEXT NOT NULL,
    email                       TEXT UNIQUE,
    age_range                   TEXT,
    area                        TEXT,
    city                        TEXT DEFAULT 'Bangalore',
    friend_group                TEXT,       -- which simulated group they belong to

    -- Trust scores — domain specific + overall fallback
    trust_received_overall      FLOAT DEFAULT 0.0,
    trust_received_restaurants  FLOAT DEFAULT 0.0,
    trust_given_overall         FLOAT DEFAULT 0.0,
    trust_given_restaurants     FLOAT DEFAULT 0.0,

    -- Activity
    last_active_restaurants     TIMESTAMPTZ,
    cold_start_flag             BOOLEAN DEFAULT true,   -- true until first trust edge exists

    -- Meta
    is_simulated                BOOLEAN DEFAULT false,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE 3: TRUST EDGES (PERSON → PERSON)
-- The soul of the trust graph
-- ============================================================
CREATE TABLE IF NOT EXISTS trust_edges (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain                  TEXT NOT NULL DEFAULT 'restaurants',

    -- Trust weight — the core signal
    weight                  FLOAT NOT NULL DEFAULT 0.0
                            CHECK (weight >= 0.0 AND weight <= 1.0),

    -- Signal basis
    basis                   TEXT NOT NULL DEFAULT 'explicit'
                            CHECK (basis IN ('explicit', 'implicit', 'hybrid')),
    explicit_count          INTEGER DEFAULT 0,
    implicit_count          INTEGER DEFAULT 0,

    -- Decay tracking
    explicit_decay_clock    TIMESTAMPTZ DEFAULT NOW(),
    implicit_decay_clock    TIMESTAMPTZ DEFAULT NOW(),
    last_reinforced_at      TIMESTAMPTZ DEFAULT NOW(),
    decay_rate              FLOAT DEFAULT 0.02,

    -- Lifecycle
    status                  TEXT DEFAULT 'active'
                            CHECK (status IN ('active', 'decaying', 'dormant', 'killed')),

    -- Meta
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),

    -- No self-loops, no duplicates per domain
    CONSTRAINT no_self_trust CHECK (from_user_id != to_user_id),
    CONSTRAINT unique_trust_per_domain UNIQUE (from_user_id, to_user_id, domain)
);

-- ============================================================
-- TABLE 4: SOURCE TRUST (PERSON → RESTAURANT)
-- Transactional trust — built through direct experience
-- ============================================================
CREATE TABLE IF NOT EXISTS source_trust (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id           UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    domain                  TEXT NOT NULL DEFAULT 'restaurants',

    weight                  FLOAT NOT NULL DEFAULT 0.0
                            CHECK (weight >= 0.0 AND weight <= 1.0),

    -- Interaction counts
    visit_count             INTEGER DEFAULT 0,
    positive_outcome_count  INTEGER DEFAULT 0,
    negative_outcome_count  INTEGER DEFAULT 0,

    -- Recency
    last_visited_at         TIMESTAMPTZ,
    status                  TEXT DEFAULT 'active'
                            CHECK (status IN ('active', 'decaying', 'dormant', 'killed')),

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_source_trust UNIQUE (user_id, restaurant_id)
);

-- ============================================================
-- TABLE 5: INTERACTIONS
-- Visit history + outcomes — feeds the feedback loop
-- ============================================================
CREATE TABLE IF NOT EXISTS interactions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id           UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,

    -- Trust path that led to this visit
    recommended_by          UUID REFERENCES users(id),   -- NULL = cold result
    trust_path_weight       FLOAT,                       -- weight of path at time of visit
    trust_hops              INTEGER DEFAULT 0,           -- 0 = cold, 1 = direct, 2 = 2nd hop

    -- Intent that was searched
    intent_query            TEXT,
    intent_parsed           JSONB,

    -- Outcome
    outcome                 TEXT CHECK (outcome IN ('positive', 'negative', 'neutral', 'regret')),
    outcome_score           FLOAT CHECK (outcome_score >= -1.0 AND outcome_score <= 1.0),
    outcome_notes           TEXT,
    outcome_recorded_at     TIMESTAMPTZ,

    -- Timing
    visited_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE 6: INTENT LOGS
-- Every search query — for debugging and learning
-- ============================================================
CREATE TABLE IF NOT EXISTS intent_logs (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID REFERENCES users(id),
    raw_query               TEXT NOT NULL,
    parsed_intent           JSONB,
    results_returned        INTEGER DEFAULT 0,
    top_result_id           UUID REFERENCES restaurants(id),
    top_result_score        FLOAT,
    had_trust_path          BOOLEAN DEFAULT false,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE 7: CONTENT
-- Reviews, recommendations, shares
-- ============================================================
CREATE TABLE IF NOT EXISTS content (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_type            TEXT NOT NULL
                            CHECK (content_type IN ('review', 'recommendation', 'share', 'reaction')),
    created_by              UUID NOT NULL REFERENCES users(id),
    restaurant_id           UUID NOT NULL REFERENCES restaurants(id),
    domain                  TEXT DEFAULT 'restaurants',

    -- Signal quality
    signal_type             TEXT CHECK (signal_type IN ('explicit', 'implicit')),
    sentiment_score         FLOAT CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
    credibility_weight      FLOAT DEFAULT 0.5,
    motivation              TEXT DEFAULT 'organic'
                            CHECK (motivation IN ('organic', 'incentivised')),

    body                    TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES — for query performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_trust_edges_from     ON trust_edges(from_user_id);
CREATE INDEX IF NOT EXISTS idx_trust_edges_to       ON trust_edges(to_user_id);
CREATE INDEX IF NOT EXISTS idx_trust_edges_status   ON trust_edges(status);
CREATE INDEX IF NOT EXISTS idx_interactions_user    ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_rest    ON interactions(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_interactions_rec_by  ON interactions(recommended_by);
CREATE INDEX IF NOT EXISTS idx_restaurants_area     ON restaurants(area);
CREATE INDEX IF NOT EXISTS idx_source_trust_user    ON source_trust(user_id);

-- ============================================================
-- DONE
-- ============================================================

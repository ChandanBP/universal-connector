-- ============================================================
-- MIGRATION 004 — Ghost Nodes + Community Edges + Shared Graph
-- Run after 001, 002, 003.
--
-- Implements the core vision:
--   1. ghost_sources     — offline sources entered by reference (the rice retailer)
--   2. user_community    — user → community membership (village, profession, family)
--   3. target_profile    — bidirectional matching: sources declare who they're for
--   4. tenants           — external apps that contribute to + query the trust graph
--   5. tenant_contributions — trust events submitted by external apps
-- ============================================================

-- ── 1. Ghost sources — offline nodes that don't exist on the platform yet ──────
-- Entered by someone who knows them ("my uncle sells the best rice in Mandya").
-- They can materialize into full nodes if/when they join.

CREATE TABLE IF NOT EXISTS ghost_sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain          TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    attributes      JSONB NOT NULL DEFAULT '{}',
    entered_by      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_hint    TEXT,          -- "call +91-xxx" / "find them at X market"
    location_hint   TEXT,          -- physical location description
    community_tags  TEXT[] NOT NULL DEFAULT '{}',  -- shared context tags
    is_materialized BOOLEAN NOT NULL DEFAULT false,
    materialized_to UUID,          -- link to real source_id when they join
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ghost_sources_domain   ON ghost_sources(domain) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_ghost_sources_entered  ON ghost_sources(entered_by);

-- ── 2. User community membership — what contexts a user belongs to ─────────────
-- context_type = village | profession | family | neighborhood | school | workplace | other
-- context_value = "Mandya" | "Software Engineer" | "IIT Bombay" | etc.
-- Shared membership creates implicit trust between users (community_edges layer).

CREATE TABLE IF NOT EXISTS user_community (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_type  TEXT NOT NULL CHECK (context_type IN (
                      'village','profession','family','neighborhood',
                      'school','workplace','other')),
    context_value TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, context_type, context_value)
);

CREATE INDEX IF NOT EXISTS idx_user_community_user    ON user_community(user_id);
CREATE INDEX IF NOT EXISTS idx_user_community_context ON user_community(context_type, context_value);

-- ── 3. Bidirectional matching: sources declare who they're for ─────────────────
-- target_profile JSONB mirrors the domain's intent fields.
-- e.g. restaurants: {"occasion": ["business"], "vibe": ["formal", "quiet"]}
-- Matching engine uses this to boost sources that actively want this type of user.

ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS target_profile JSONB;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS target_profile JSONB;

-- ── 4. Tenants — external apps that contribute to and query the trust graph ────
-- The trust graph as shared infrastructure (like DNS).
-- Any app can contribute trust events; any app can query the graph.
-- api_key is generated outside DB for flexibility.

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL UNIQUE,
    api_key     TEXT NOT NULL UNIQUE,
    domains     TEXT[] NOT NULL DEFAULT '{}',   -- which domains they can access
    can_write   BOOLEAN NOT NULL DEFAULT true,
    can_read    BOOLEAN NOT NULL DEFAULT true,
    active      BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key) WHERE active = true;

-- ── 5. Tenant contributions — trust events submitted by external apps ──────────
-- A village community app can submit "Ravi from Mandya recommends this rice seller".
-- These flow into ghost_sources, user_community, or trust_edges after processing.

CREATE TABLE IF NOT EXISTS tenant_contributions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contribution_type   TEXT NOT NULL CHECK (contribution_type IN (
                            'ghost_source', 'community_membership', 'trust_signal')),
    payload             JSONB NOT NULL,
    processed           BOOLEAN NOT NULL DEFAULT false,
    processed_at        TIMESTAMPTZ,
    result_id           UUID,       -- ID of the created record (ghost_source.id etc.)
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_contrib_tenant    ON tenant_contributions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_contrib_unprocessed
    ON tenant_contributions(tenant_id)
    WHERE processed = false;

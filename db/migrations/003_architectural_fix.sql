-- ============================================================
-- MIGRATION 003 — Architectural Fix
-- Run after 001 (schema.sql) and 002 (electronics) are applied.
--
-- Changes:
--   1. Add last_intent_parsed, last_outcome to source_trust
--      → enables hot-path intent similarity without touching interactions
--   2. Replace full unique constraint on source_trust with partial indexes
--      → makes ON CONFLICT clause domain-agnostic
--   3. Add composite indexes on interactions(user_id, source_id)
--      → covers the JOIN pattern used in taste_profile and cold-path lookups
--   4. Add source_trust lookup indexes
--      → covers the (source_id, domain) JOIN in find_best_trust_signal layers
-- ============================================================

-- ── 1. source_trust: add context columns ─────────────────────────────────────

ALTER TABLE source_trust
    ADD COLUMN IF NOT EXISTS last_intent_parsed JSONB,
    ADD COLUMN IF NOT EXISTS last_outcome       TEXT
        CHECK (last_outcome IN ('positive', 'negative', 'neutral', 'regret'));

-- ── 2. source_trust: replace full unique constraint with partial indexes ──────
-- The full constraint UNIQUE (user_id, restaurant_id) cannot be used with
-- ON CONFLICT ... WHERE {fk} IS NOT NULL (partial index syntax).
-- Replacing it with a partial index makes the UPSERT clause domain-agnostic.

ALTER TABLE source_trust DROP CONSTRAINT IF EXISTS unique_source_trust;

CREATE UNIQUE INDEX IF NOT EXISTS idx_source_trust_restaurant
    ON source_trust(user_id, restaurant_id)
    WHERE restaurant_id IS NOT NULL;

-- idx_source_trust_product already exists from migration 002.

-- ── 3. interactions: composite indexes for (user_id, source_id) JOINs ────────

CREATE INDEX IF NOT EXISTS idx_interactions_user_restaurant
    ON interactions(user_id, restaurant_id);

CREATE INDEX IF NOT EXISTS idx_interactions_user_product
    ON interactions(user_id, product_id);

-- ── 4. source_trust: indexes for source lookup in trust signal layers ─────────

CREATE INDEX IF NOT EXISTS idx_source_trust_restaurant_domain
    ON source_trust(restaurant_id, domain)
    WHERE restaurant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_source_trust_product_domain
    ON source_trust(product_id, domain)
    WHERE product_id IS NOT NULL;

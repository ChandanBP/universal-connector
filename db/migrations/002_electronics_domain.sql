-- ============================================================
-- MIGRATION 002 — Electronics Domain
-- Run after 001 (schema.sql) is applied.
-- ============================================================

-- ── Products table (source nodes for electronics) ─────────────────────────────

CREATE TABLE IF NOT EXISTS products (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    brand               TEXT[] NOT NULL,
    category            TEXT NOT NULL
                        CHECK (category IN (
                            'phone','laptop','tablet','headphones',
                            'smartwatch','camera','tv','speaker','monitor','keyboard'
                        )),
    use_case            TEXT[] NOT NULL DEFAULT '{}',
    price_range         TEXT NOT NULL CHECK (price_range IN ('budget','mid','premium')),
    condition           TEXT NOT NULL DEFAULT 'new'
                        CHECK (condition IN ('new','refurbished')),
    connectivity        TEXT[] NOT NULL DEFAULT '{}',
    battery_life        TEXT CHECK (battery_life IN ('excellent','good','average','na')),
    portability         TEXT CHECK (portability IN ('highly-portable','portable','desktop')),
    tags                TEXT[] NOT NULL DEFAULT '{}',

    avg_outcome_score   FLOAT   DEFAULT 0.0,
    total_visits        INTEGER DEFAULT 0,
    trust_citations     INTEGER DEFAULT 0,

    active              BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Extend interactions — add product_id FK ───────────────────────────────────

ALTER TABLE interactions
    ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE CASCADE;

-- Deduplicate pending interactions before creating unique indexes.
-- Keeps the most-recent pending row per (user_id, restaurant_id) pair;
-- older duplicates are deleted. Same logic for product_id.
DELETE FROM interactions
WHERE outcome IS NULL
  AND restaurant_id IS NOT NULL
  AND id NOT IN (
    SELECT DISTINCT ON (user_id, restaurant_id) id
    FROM interactions
    WHERE outcome IS NULL AND restaurant_id IS NOT NULL
    ORDER BY user_id, restaurant_id, created_at DESC
  );

DELETE FROM interactions
WHERE outcome IS NULL
  AND product_id IS NOT NULL
  AND id NOT IN (
    SELECT DISTINCT ON (user_id, product_id) id
    FROM interactions
    WHERE outcome IS NULL AND product_id IS NOT NULL
    ORDER BY user_id, product_id, created_at DESC
  );

DELETE FROM interactions                                                                                          
  WHERE outcome IS NULL                                                                                             
    AND restaurant_id IS NOT NULL                                                                                   
    AND id NOT IN (                                                                                               
      SELECT DISTINCT ON (user_id, restaurant_id) id
      FROM interactions                                                                                             
      WHERE outcome IS NULL AND restaurant_id IS NOT NULL
      ORDER BY user_id, restaurant_id, created_at DESC                                                              
    );  

-- Pending interaction uniqueness per domain
-- Ensures a repeat search overwrites the old pending row rather than stacking
CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_pending_rest
    ON interactions(user_id, restaurant_id)
    WHERE outcome IS NULL AND restaurant_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_interactions_pending_prod
    ON interactions(user_id, product_id)
    WHERE outcome IS NULL AND product_id IS NOT NULL;

-- ── Extend source_trust — add product_id FK ───────────────────────────────────

ALTER TABLE source_trust
    ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_source_trust_product
    ON source_trust(user_id, product_id)
    WHERE product_id IS NOT NULL;

-- ── Extend users — electronics trust scores ───────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS trust_received_electronics FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS trust_given_electronics    FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS last_active_electronics    TIMESTAMPTZ;

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_products_category  ON products(category);
CREATE INDEX IF NOT EXISTS idx_interactions_prod  ON interactions(product_id);
CREATE INDEX IF NOT EXISTS idx_source_trust_prod  ON source_trust(product_id);

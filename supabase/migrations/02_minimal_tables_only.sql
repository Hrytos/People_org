-- ============================================================================
-- MINIMAL SCHEMA: Use your existing accounts + contacts tables
-- ============================================================================
-- This migration only creates enrichment_history (optional tracking).
-- We do NOT create accounts or contacts – we use your existing:
--   - public.accounts  (for account_id lookups by company name)
--   - public.contacts  (enriched contacts; schema you provided)
-- ============================================================================

-- ============================================================================
-- Enrichment history (optional – track runs and credit usage)
-- ============================================================================

CREATE TABLE IF NOT EXISTS enrichment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name TEXT NOT NULL,
    contacts_count INTEGER DEFAULT 0,
    with_linkedin INTEGER DEFAULT 0,
    source TEXT DEFAULT 'streamlit',
    status TEXT DEFAULT 'pending',
    credits_used INTEGER DEFAULT 0,
    contacts_inserted INTEGER DEFAULT 0,
    contacts_updated INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_enrichment_history_status ON enrichment_history(status);
CREATE INDEX IF NOT EXISTS idx_enrichment_history_started ON enrichment_history(started_at DESC);

COMMENT ON TABLE enrichment_history IS 'Enrichment run history and credit tracking (app-only). Uses existing accounts + contacts.';

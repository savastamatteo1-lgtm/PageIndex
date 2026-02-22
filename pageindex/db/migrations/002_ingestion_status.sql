-- 002_ingestion_status.sql
-- Adds ingestion pipeline tracking columns to the documents table.
-- Tracks pipeline progress (pending/processing/complete/failed) and
-- flags documents where metadata extraction was incomplete.

-- =============================================================================
-- New columns on documents table
-- =============================================================================

ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingestion_status TEXT DEFAULT 'pending';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;

-- =============================================================================
-- Index for filtering by ingestion status (e.g., retry failed documents)
-- =============================================================================

CREATE INDEX IF NOT EXISTS documents_ingestion_status_idx ON documents (ingestion_status);

-- Add priority column to announcements table (missing from original schema)
ALTER TABLE announcements
    ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'medium';

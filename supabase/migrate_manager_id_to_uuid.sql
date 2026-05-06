-- Migration: manager_id / lead_id TEXT → UUID FK
-- Run in Supabase SQL Editor BEFORE deploying the corresponding code changes.
-- Safe to re-run: all steps use IF EXISTS / IF NOT EXISTS guards.
--
-- What this does:
--   1. Adds temporary UUID columns on users and onboarding_requests
--   2. Backfills them from the existing TEXT values (treated as firebase_uid)
--   3. Drops the old TEXT columns
--   4. Renames the UUID columns back to manager_id / lead_id
--   5. Adds ON DELETE SET NULL foreign-key constraints

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. users table
-- ─────────────────────────────────────────────────────────────────────────────

-- Add temp UUID columns (idempotent)
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS manager_uuid UUID,
    ADD COLUMN IF NOT EXISTS lead_uuid    UUID;

-- Backfill: resolve firebase_uid → id
UPDATE users u
SET manager_uuid = m.id
FROM users m
WHERE m.firebase_uid = u.manager_id
  AND u.manager_id IS NOT NULL;

UPDATE users u
SET lead_uuid = l.id
FROM users l
WHERE l.firebase_uid = u.lead_id
  AND u.lead_id IS NOT NULL;

-- Drop old TEXT columns
ALTER TABLE users
    DROP COLUMN IF EXISTS manager_id,
    DROP COLUMN IF EXISTS lead_id;

-- Rename UUID columns
ALTER TABLE users RENAME COLUMN manager_uuid TO manager_id;
ALTER TABLE users RENAME COLUMN lead_uuid    TO lead_id;

-- Add foreign-key constraints
ALTER TABLE users
    ADD CONSTRAINT fk_users_manager_id
        FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE users
    ADD CONSTRAINT fk_users_lead_id
        FOREIGN KEY (lead_id) REFERENCES users(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. onboarding_requests table
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE onboarding_requests
    ADD COLUMN IF NOT EXISTS manager_uuid UUID,
    ADD COLUMN IF NOT EXISTS lead_uuid    UUID;

UPDATE onboarding_requests r
SET manager_uuid = m.id
FROM users m
WHERE m.firebase_uid = r.manager_id
  AND r.manager_id IS NOT NULL;

UPDATE onboarding_requests r
SET lead_uuid = l.id
FROM users l
WHERE l.firebase_uid = r.lead_id
  AND r.lead_id IS NOT NULL;

ALTER TABLE onboarding_requests
    DROP COLUMN IF EXISTS manager_id,
    DROP COLUMN IF EXISTS lead_id;

ALTER TABLE onboarding_requests RENAME COLUMN manager_uuid TO manager_id;
ALTER TABLE onboarding_requests RENAME COLUMN lead_uuid    TO lead_id;

ALTER TABLE onboarding_requests
    ADD CONSTRAINT fk_onboarding_manager_id
        FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE onboarding_requests
    ADD CONSTRAINT fk_onboarding_lead_id
        FOREIGN KEY (lead_id) REFERENCES users(id) ON DELETE SET NULL;

COMMIT;

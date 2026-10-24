-- Finalize existing pending entries created by directors.
-- Directors are the final operational authority for attendance, so their
-- entries should not remain queued for a higher-level self-review.
WITH director_entries AS (
    SELECT
        a.id,
        a.date,
        a.pending_status,
        a.pending_check_in_time,
        a.pending_check_out_time,
        a.pending_notes,
        a.marked_by,
        s.start_time AS shift_start_time,
        s.end_time AS shift_end_time
    FROM public.attendance AS a
    JOIN public.users AS creator ON creator.id = a.marked_by
    LEFT JOIN public.shifts AS s ON s.id = a.shift_allocation_id
    WHERE a.approval_status = 'pending'
      AND creator.role = 'director'
), normalized AS (
    SELECT
        id,
        date,
        pending_status,
        pending_notes,
        marked_by,
        CASE
            WHEN pending_check_in_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                THEN date + pending_check_in_time::time
            ELSE NULL
        END AS check_in_time,
        CASE
            WHEN pending_check_out_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                THEN date + pending_check_out_time::time
                     + CASE
                         WHEN pending_check_in_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
                          AND pending_check_out_time::time <= pending_check_in_time::time
                          AND shift_start_time IS NOT NULL
                          AND shift_end_time < shift_start_time
                             THEN interval '1 day'
                         ELSE interval '0 day'
                       END
            ELSE NULL
        END AS check_out_time
    FROM director_entries
)
UPDATE public.attendance AS a
SET status = COALESCE(n.pending_status, a.status),
    check_in_time = n.check_in_time,
    check_out_time = n.check_out_time,
    total_hours = CASE
        WHEN n.check_in_time IS NOT NULL AND n.check_out_time IS NOT NULL
            THEN ROUND((EXTRACT(EPOCH FROM (n.check_out_time - n.check_in_time)) / 3600)::numeric, 2)
        ELSE 0
    END,
    notes = COALESCE(n.pending_notes, a.notes),
    approval_status = 'approved',
    reviewed_by = n.marked_by,
    is_week_off = COALESCE(n.pending_status, a.status) = 'week_off',
    is_comp_off = COALESCE(n.pending_status, a.status) = 'comp_off',
    updated_at = NOW()
FROM normalized AS n
WHERE a.id = n.id
  AND a.approval_status = 'pending';

NOTIFY pgrst, 'reload schema';

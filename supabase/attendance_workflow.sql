-- Attendance shift linkage, correction queue, and review tracking.
ALTER TABLE public.attendance
    ADD COLUMN IF NOT EXISTS shift_allocation_id UUID REFERENCES public.shifts(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'approved',
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS review_reason TEXT,
    ADD COLUMN IF NOT EXISTS pending_status TEXT,
    ADD COLUMN IF NOT EXISTS pending_check_in_time TEXT,
    ADD COLUMN IF NOT EXISTS pending_check_out_time TEXT,
    ADD COLUMN IF NOT EXISTS pending_notes TEXT,
    ADD COLUMN IF NOT EXISTS correction_reason TEXT;

UPDATE public.attendance SET approval_status = 'approved' WHERE approval_status IS NULL;
UPDATE public.attendance SET status = 'week_off' WHERE is_week_off = TRUE AND status = 'leave';
UPDATE public.attendance SET status = 'comp_off' WHERE is_comp_off = TRUE AND status = 'leave';

CREATE INDEX IF NOT EXISTS attendance_review_queue_idx
    ON public.attendance (approval_status, created_at DESC);
CREATE INDEX IF NOT EXISTS attendance_shift_allocation_idx
    ON public.attendance (shift_allocation_id);

NOTIFY pgrst, 'reload schema';

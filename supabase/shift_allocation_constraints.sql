-- Keep reusable shift definitions separate from employee allocations.
CREATE TABLE IF NOT EXISTS public.shift_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    notes TEXT,
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS shift_templates_unique_name
    ON public.shift_templates (lower(name));

DROP INDEX IF EXISTS public.shift_templates_unique_active_name;

-- Keep an employee from receiving two concurrent ongoing shift allocations.
-- Past one-off allocations remain valid history and do not block reassignment.
ALTER TABLE public.shifts
    ADD COLUMN IF NOT EXISTS start_time TEXT,
    ADD COLUMN IF NOT EXISTS end_time TEXT,
    ADD COLUMN IF NOT EXISTS shift_template_id UUID REFERENCES public.shift_templates(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

-- Earlier versions referenced shifts itself; repair that FK for existing installs.
UPDATE public.shifts AS allocation
SET shift_template_id = NULL
WHERE allocation.shift_template_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.shift_templates AS template
      WHERE template.id = allocation.shift_template_id
  );
ALTER TABLE public.shifts
    DROP CONSTRAINT IF EXISTS shifts_shift_template_id_fkey;
ALTER TABLE public.shifts
    ADD CONSTRAINT shifts_shift_template_id_fkey
    FOREIGN KEY (shift_template_id) REFERENCES public.shift_templates(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS shifts_one_open_ongoing_allocation_per_employee
    ON public.shifts (employee_id)
    WHERE employee_id IS NOT NULL
      AND shift_date IS NULL
      AND status IN ('pending', 'approved');

NOTIFY pgrst, 'reload schema';


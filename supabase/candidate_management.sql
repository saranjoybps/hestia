-- Candidate recruitment pipeline, interview scheduling, and employee conversion.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.recruitment_candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name TEXT NOT NULL,
    last_name TEXT,
    email TEXT NOT NULL,
    phone TEXT,
    department TEXT,
    designation TEXT NOT NULL,
    source TEXT,
    current_company TEXT,
    current_designation TEXT,
    experience_years NUMERIC(5,2),
    notice_period_days INTEGER,
    expected_salary NUMERIC(14,2),
    location TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'screening', 'shortlisted', 'interview_scheduled', 'interview_completed', 'selected', 'offer_sent', 'hired', 'rejected', 'withdrawn')),
    owner_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    converted_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    converted_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recruitment_candidates_department_status_idx
    ON public.recruitment_candidates (department, status, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS recruitment_candidates_email_idx
    ON public.recruitment_candidates (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS recruitment_candidates_active_email_unique_idx
    ON public.recruitment_candidates (lower(email))
    WHERE deleted_at IS NULL AND status NOT IN ('rejected', 'withdrawn');

CREATE TABLE IF NOT EXISTS public.candidate_activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID NOT NULL REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL CHECK (activity_type IN ('note', 'interview', 'meeting')),
    title TEXT NOT NULL,
    body TEXT,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    meeting_url TEXT,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS candidate_activities_candidate_date_idx
    ON public.candidate_activities (candidate_id, starts_at DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS public.candidate_activity_interviewers (
    activity_id UUID NOT NULL REFERENCES public.candidate_activities(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (activity_id, interviewer_id)
);
CREATE INDEX IF NOT EXISTS candidate_activity_interviewer_scope_idx
    ON public.candidate_activity_interviewers (interviewer_id, candidate_id);

-- Expand the permissions catalog for clients that display role permission metadata.
UPDATE public.permissions SET permissions = array_append(permissions, 'manage_candidates'), updated_at = now()
WHERE role IN ('hr', 'director') AND NOT ('manage_candidates' = ANY(permissions));
UPDATE public.permissions SET permissions = array_append(permissions, 'view_department_candidates'), updated_at = now()
WHERE role = 'manager' AND NOT ('view_department_candidates' = ANY(permissions));
UPDATE public.permissions SET permissions = array_append(permissions, 'view_assigned_candidates'), updated_at = now()
WHERE role = 'lead' AND NOT ('view_assigned_candidates' = ANY(permissions));

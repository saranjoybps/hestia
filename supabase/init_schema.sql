-- Supabase PostgreSQL Schema for Hestia Application
-- Execute this directly in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firebase_uid TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    last_name TEXT,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'employee',
    department TEXT,
    designation TEXT,
    date_of_joining DATE,
    manager_id TEXT,
    lead_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- Attendance table
CREATE TABLE IF NOT EXISTS attendance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status TEXT NOT NULL,
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    total_hours NUMERIC(5, 2),
    marked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    corrected_by UUID REFERENCES users(id) ON DELETE SET NULL,
    corrected_at TIMESTAMPTZ,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    review_reason TEXT,
    pending_status TEXT,
    pending_check_in_time TEXT,
    pending_check_out_time TEXT,
    pending_notes TEXT,
    correction_reason TEXT,
    is_week_off BOOLEAN DEFAULT FALSE,
    is_comp_off BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, date)
);

CREATE INDEX idx_attendance_user_id ON attendance(user_id);
CREATE INDEX idx_attendance_date ON attendance(date);

-- Leaves table
CREATE TABLE IF NOT EXISTS leaves (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    number_of_days DECIMAL(5, 2),
    reason TEXT,
    status TEXT DEFAULT 'pending',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_leaves_user_id ON leaves(user_id);
CREATE INDEX idx_leaves_status ON leaves(status);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    assigned_to UUID REFERENCES users(id) ON DELETE CASCADE,
    assignee_name TEXT,
    assignee_email TEXT,
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by_name TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    start_date DATE,
    -- Nullable so task forms can clear deadlines by sending NULL.
    due_date DATE,
    attachments JSONB DEFAULT '[]'::jsonb,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_status ON tasks(status);

-- Performance reviews table
CREATE TABLE IF NOT EXISTS performance_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_name TEXT,
    user_email TEXT,
    reviewer_name TEXT,
    reviewer_role TEXT,
    review_type TEXT,
    rating INTEGER,
    context TEXT,
    review_date DATE,
    review_period_start DATE,
    review_period_end DATE,
    overall_rating DECIMAL(3, 1),
    technical_skills_rating DECIMAL(3, 1),
    communication_rating DECIMAL(3, 1),
    teamwork_rating DECIMAL(3, 1),
    leadership_rating DECIMAL(3, 1),
    comments TEXT,
    goals_for_next_period TEXT,
    status TEXT DEFAULT 'draft',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approver_name TEXT,
    approval_date TIMESTAMPTZ,
    rejected_by UUID REFERENCES users(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    rejection_date TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_performance_reviews_employee_id ON performance_reviews(employee_id);

-- Announcements table
CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium',
    target_audience JSONB DEFAULT '[]'::jsonb,
    expiry_date TEXT,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_by_name TEXT,
    status TEXT DEFAULT 'published',
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_announcements_created_by ON announcements(created_by);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_name TEXT,
    actor_email TEXT,
    module TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    result TEXT,
    target_type TEXT,
    target_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_actor_id ON audit_logs(actor_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role TEXT UNIQUE NOT NULL,
    permissions TEXT[] NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert default permissions
INSERT INTO permissions (role, permissions, description) VALUES
    ('director', ARRAY['view_all', 'create_user', 'edit_user', 'delete_user', 'approve_leaves', 'view_reports', 'manage_roles'], 'Full system access'),
    ('hr', ARRAY['view_all', 'create_user', 'edit_user', 'manage_leaves', 'view_attendance', 'view_reports'], 'HR management'),
    ('manager', ARRAY['view_team', 'manage_team_attendance', 'approve_leaves', 'create_tasks'], 'Team management'),
    ('lead', ARRAY['view_team', 'manage_team_attendance', 'create_tasks'], 'Team lead'),
    ('employee', ARRAY['view_own', 'apply_leave', 'view_attendance', 'view_tasks'], 'Employee self-service')
ON CONFLICT (role) DO NOTHING;

-- Departments table
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    head_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Reusable shift definitions are separate from employee allocations.
CREATE TABLE IF NOT EXISTS shift_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    notes TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS shift_templates_unique_name
    ON public.shift_templates (lower(name));

-- Employee shift allocations
CREATE TABLE IF NOT EXISTS shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    employee_name TEXT,
    employee_email TEXT,
    shift_type TEXT,
    shift_template_id UUID REFERENCES shift_templates(id) ON DELETE SET NULL,
    shift_date TEXT,
    start_time TEXT,
    end_time TEXT,
    notes TEXT,
    status TEXT DEFAULT 'pending',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by_name TEXT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_by_name TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Onboarding table
CREATE TABLE IF NOT EXISTS onboarding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    onboarding_date DATE,
    status TEXT DEFAULT 'pending',
    assigned_mentor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    checklist_items JSONB,
    notes TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS onboarding_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    last_name TEXT,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'employee',
    department TEXT,
    designation TEXT,
    date_of_joining DATE,
    manager_id TEXT,
    lead_id TEXT,
    notes TEXT,
    status TEXT DEFAULT 'pending',
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    requested_by_name TEXT,
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_by_name TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ
);

-- Letters table
CREATE TABLE IF NOT EXISTS letters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    letter_type TEXT NOT NULL,
    issued_date DATE,
    reason TEXT,
    document_url TEXT,
    status TEXT DEFAULT 'generated',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS letter_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    employee_name TEXT,
    employee_email TEXT,
    department TEXT,
    designation TEXT,
    letter_type TEXT NOT NULL,
    last_working_day TEXT,
    reason_for_exit TEXT,
    additional_comments TEXT,
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    requested_by_name TEXT,
    join_date TEXT,
    annual_salary TEXT,
    start_date TEXT,
    probation_period TEXT,
    notice_period TEXT,
    status TEXT DEFAULT 'pending',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_by_name TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ
);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    generated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    filters JSONB,
    data JSONB,
    file_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE IF EXISTS attendance
    ADD COLUMN IF NOT EXISTS total_hours NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS marked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS shift_allocation_id UUID REFERENCES shifts(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'approved',
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS review_reason TEXT,
    ADD COLUMN IF NOT EXISTS pending_status TEXT,
    ADD COLUMN IF NOT EXISTS pending_check_in_time TEXT,
    ADD COLUMN IF NOT EXISTS pending_check_out_time TEXT,
    ADD COLUMN IF NOT EXISTS pending_notes TEXT,
    ADD COLUMN IF NOT EXISTS correction_reason TEXT,
    ADD COLUMN IF NOT EXISTS is_week_off BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_comp_off BOOLEAN DEFAULT FALSE;

ALTER TABLE IF EXISTS tasks
    ADD COLUMN IF NOT EXISTS assignee_name TEXT,
    ADD COLUMN IF NOT EXISTS assignee_email TEXT,
    ADD COLUMN IF NOT EXISTS created_by_name TEXT,
    ADD COLUMN IF NOT EXISTS attachments JSONB DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS performance_reviews
    ADD COLUMN IF NOT EXISTS user_name TEXT,
    ADD COLUMN IF NOT EXISTS user_email TEXT,
    ADD COLUMN IF NOT EXISTS reviewer_name TEXT,
    ADD COLUMN IF NOT EXISTS reviewer_role TEXT,
    ADD COLUMN IF NOT EXISTS review_type TEXT,
    ADD COLUMN IF NOT EXISTS rating INTEGER,
    ADD COLUMN IF NOT EXISTS context TEXT,
    ADD COLUMN IF NOT EXISTS review_date DATE,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approver_name TEXT,
    ADD COLUMN IF NOT EXISTS approval_date TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS rejection_date TIMESTAMPTZ;

ALTER TABLE IF EXISTS announcements
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS target_audience JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS expiry_date TEXT,
    ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_by_name TEXT;

ALTER TABLE IF EXISTS shifts
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS employee_name TEXT,
    ADD COLUMN IF NOT EXISTS employee_email TEXT,
    ADD COLUMN IF NOT EXISTS shift_type TEXT,
    ADD COLUMN IF NOT EXISTS shift_template_id UUID REFERENCES shift_templates(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS shift_date TEXT,
    ADD COLUMN IF NOT EXISTS start_time TEXT,
    ADD COLUMN IF NOT EXISTS end_time TEXT,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by_name TEXT,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_by_name TEXT,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE UNIQUE INDEX IF NOT EXISTS shifts_one_open_ongoing_allocation_per_employee
    ON public.shifts (employee_id)
    WHERE employee_id IS NOT NULL
      AND shift_date IS NULL
      AND status IN ('pending', 'approved');

ALTER TABLE IF EXISTS letter_requests
    ADD COLUMN IF NOT EXISTS requested_on TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_on TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_on TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS employment_period TEXT,
    ADD COLUMN IF NOT EXISTS reference_number TEXT,
    ADD COLUMN IF NOT EXISTS pdf_files JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS experience_letter_link TEXT,
    ADD COLUMN IF NOT EXISTS experience_file_id TEXT,
    ADD COLUMN IF NOT EXISTS exit_letter_link TEXT,
    ADD COLUMN IF NOT EXISTS exit_file_id TEXT,
    ADD COLUMN IF NOT EXISTS offer_letter_link TEXT,
    ADD COLUMN IF NOT EXISTS offer_file_id TEXT,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approver_name TEXT,
    ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Documents template system; canonical migration is supabase/documents_templates.sql

-- Versioned document templates and immutable issued-document snapshots.
CREATE TABLE IF NOT EXISTS public.document_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'employment',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    active_version INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.document_template_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES public.document_templates(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    signature_title TEXT NOT NULL DEFAULT 'Authorized Signatory',
    fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    published_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    UNIQUE (template_id, version)
);

CREATE TABLE IF NOT EXISTS public.document_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name TEXT NOT NULL DEFAULT 'Hestia',
    company_address TEXT NOT NULL DEFAULT '',
    company_email TEXT NOT NULL DEFAULT '',
    company_phone TEXT NOT NULL DEFAULT '',
    labour_identification_number TEXT NOT NULL DEFAULT '',
    reference_prefix TEXT NOT NULL DEFAULT 'HESTIA/HR',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL
);
INSERT INTO public.document_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.letter_requests
    ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES public.document_templates(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS template_version INTEGER,
    ADD COLUMN IF NOT EXISTS template_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS document_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS generation_status TEXT NOT NULL DEFAULT 'not_generated',
    ADD COLUMN IF NOT EXISTS generation_error TEXT,
    ADD COLUMN IF NOT EXISTS requested_on TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approver_name TEXT,
    ADD COLUMN IF NOT EXISTS approved_on TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejected_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rejected_on TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS employment_period TEXT,
    ADD COLUMN IF NOT EXISTS reference_number TEXT,
    ADD COLUMN IF NOT EXISTS pdf_files JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS experience_file_id TEXT,
    ADD COLUMN IF NOT EXISTS exit_file_id TEXT,
    ADD COLUMN IF NOT EXISTS offer_file_id TEXT;

CREATE INDEX IF NOT EXISTS document_template_versions_lookup
    ON public.document_template_versions (template_id, version DESC);
CREATE INDEX IF NOT EXISTS letter_requests_employee_date
    ON public.letter_requests (employee_id, requested_on DESC);

-- English is the single supported template language in this first release.
WITH seeds(template_key, name, category, title, body, signature_title, fields) AS (
    VALUES
    ('offer', 'Offer Letter', 'employment', 'OFFER OF EMPLOYMENT',
     'Dear {{employeeName}},\n\nWe are pleased to offer you the position of {{designation}} in the {{department}} department. Your proposed start date is {{startDate}}.\n\nAnnual compensation: INR {{annualSalary}}.\nProbation period: {{probationPeriod}}.\nNotice period: {{noticePeriod}}.\n\nPlease confirm your acceptance of this offer.', 'Director',
     '[{"key":"startDate","label":"Start date","type":"date","required":true},{"key":"annualSalary","label":"Annual compensation (INR)","type":"text","required":true},{"key":"probationPeriod","label":"Probation period","type":"text","required":false},{"key":"noticePeriod","label":"Notice period","type":"text","required":false}]'::jsonb),
    ('appointment', 'Appointment Letter', 'employment', 'APPOINTMENT LETTER',
     'Dear {{employeeName}},\n\nWe appoint you as {{designation}} with {{companyName}}, effective {{startDate}}. Your employment type is {{employmentType}}.\n\nWages and compensation: {{annualSalary}}.\nProbation period: {{probationPeriod}}.\nNotice period: {{noticePeriod}}.\nBroad nature of duties: {{duties}}.\nSocial security applicability: {{socialSecurity}}.\n\nAll other terms are governed by the applicable employment policies and the terms accepted by you.', 'Authorized Signatory',
     '[{"key":"startDate","label":"Date of joining","type":"date","required":true},{"key":"employmentType","label":"Employment type","type":"text","required":true},{"key":"annualSalary","label":"Wages / compensation","type":"text","required":true},{"key":"probationPeriod","label":"Probation period","type":"text","required":false},{"key":"noticePeriod","label":"Notice period","type":"text","required":false},{"key":"duties","label":"Broad duties","type":"textarea","required":true},{"key":"socialSecurity","label":"Social security applicability","type":"text","required":false}]'::jsonb),
    ('experience', 'Experience Certificate', 'employment', 'EXPERIENCE CERTIFICATE',
     'This is to certify that {{employeeName}} was employed with {{companyName}} as {{designation}} in the {{department}} department from {{joinDate}} to {{lastWorkingDay}}.\n\nWe wish {{employeeName}} success in future endeavours.', 'Director',
     '[{"key":"joinDate","label":"Date of joining","type":"date","required":true},{"key":"lastWorkingDay","label":"Last working day","type":"date","required":true}]'::jsonb),
    ('relieving', 'Relieving Letter', 'separation', 'RELIEVING LETTER',
     'Dear {{employeeName}},\n\nThis is to confirm that you have been relieved from your duties as {{designation}} with {{companyName}}, effective {{lastWorkingDay}}.\n\nWe thank you for your service and wish you success in your future endeavours.', 'Director',
     '[{"key":"lastWorkingDay","label":"Last working day","type":"date","required":true}]'::jsonb),
    ('salary_revision', 'Salary Revision Letter', 'employment', 'SALARY REVISION',
     'Dear {{employeeName}},\n\nWe are pleased to inform you that your annual compensation will be revised to INR {{annualSalary}}, effective {{effectiveDate}}. Your designation remains {{designation}}.\n\nAll other terms and conditions of your employment remain unchanged.', 'Authorized Signatory',
     '[{"key":"annualSalary","label":"Revised annual compensation (INR)","type":"text","required":true},{"key":"effectiveDate","label":"Effective date","type":"date","required":true}]'::jsonb),
    ('promotion', 'Promotion / Role Change Letter', 'employment', 'ROLE CHANGE LETTER',
     'Dear {{employeeName}},\n\nWe are pleased to confirm your appointment to the position of {{newDesignation}}, effective {{effectiveDate}}.\n\nWe congratulate you on this achievement and wish you continued success.', 'Authorized Signatory',
     '[{"key":"newDesignation","label":"New designation","type":"text","required":true},{"key":"effectiveDate","label":"Effective date","type":"date","required":true}]'::jsonb),
    ('employment_verification', 'Employment Verification Letter', 'employee_request', 'EMPLOYMENT VERIFICATION',
     'To whom it may concern:\n\nThis is to confirm that {{employeeName}} is employed by {{companyName}} as {{designation}} in the {{department}} department. Date of joining: {{joinDate}}.\n\nPurpose: {{verificationPurpose}}.', 'Authorized Signatory',
     '[{"key":"joinDate","label":"Date of joining","type":"date","required":true},{"key":"verificationPurpose","label":"Purpose","type":"text","required":true}]'::jsonb),
    ('salary_certificate', 'Salary Certificate', 'employee_request', 'SALARY CERTIFICATE',
     'To whom it may concern:\n\nThis is to certify that {{employeeName}}, employed as {{designation}} at {{companyName}}, has an annual compensation of INR {{annualSalary}}.\n\nPurpose: {{certificationPurpose}}.', 'Authorized Signatory',
     '[{"key":"annualSalary","label":"Annual compensation (INR)","type":"text","required":true},{"key":"certificationPurpose","label":"Purpose","type":"text","required":true}]'::jsonb),
    ('noc', 'No Objection Certificate', 'employee_request', 'NO OBJECTION CERTIFICATE',
     'To whom it may concern:\n\nThis is to certify that {{companyName}} has no objection to {{employeeName}}, employed as {{designation}}, for the following purpose: {{nocPurpose}}.', 'Authorized Signatory',
     '[{"key":"nocPurpose","label":"Purpose","type":"textarea","required":true}]'::jsonb),
    ('nda', 'Confidentiality and IP Agreement', 'onboarding', 'CONFIDENTIALITY AND INTELLECTUAL PROPERTY UNDERTAKING',
     'This undertaking is made by {{employeeName}}, appointed as {{designation}} with {{companyName}}, effective {{startDate}}.\n\nTerms: {{agreementTerms}}\n\nI acknowledge that I have read and agree to the terms stated above.', 'Employee Acknowledgement',
     '[{"key":"startDate","label":"Effective date","type":"date","required":true},{"key":"agreementTerms","label":"Agreement terms","type":"textarea","required":true}]'::jsonb),
    ('policy_acknowledgement', 'Policy Acknowledgement', 'onboarding', 'POLICY ACKNOWLEDGEMENT',
     'I, {{employeeName}}, employed as {{designation}} with {{companyName}}, acknowledge receipt of and agree to follow the policy titled {{policyName}}.\n\nAcknowledgement: {{acknowledgementText}}', 'Employee Acknowledgement',
     '[{"key":"policyName","label":"Policy name","type":"text","required":true},{"key":"acknowledgementText","label":"Acknowledgement text","type":"textarea","required":true}]'::jsonb)
), upserted AS (
    INSERT INTO public.document_templates (template_key, name, category, active_version)
    SELECT template_key, name, category, 1 FROM seeds
    ON CONFLICT (template_key) DO UPDATE SET
        name = EXCLUDED.name, category = EXCLUDED.category, updated_at = now()
    RETURNING id, template_key
)
INSERT INTO public.document_template_versions (template_id, version, title, body, signature_title, fields, status, published_at)
SELECT t.id, 1, s.title, s.body, s.signature_title, s.fields, 'published', now()
FROM seeds s JOIN public.document_templates t ON t.template_key = s.template_key
WHERE NOT EXISTS (
    SELECT 1 FROM public.document_template_versions v WHERE v.template_id = t.id AND v.version = 1
);

UPDATE public.document_templates SET active_version = 1 WHERE active_version IS NULL;

-- Recruitment candidates and interview activity. Kept in sync with
-- supabase/candidate_management.sql for existing installations.
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
CREATE INDEX IF NOT EXISTS recruitment_candidates_department_status_idx ON public.recruitment_candidates (department, status, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS recruitment_candidates_email_idx ON public.recruitment_candidates (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS recruitment_candidates_active_email_unique_idx ON public.recruitment_candidates (lower(email)) WHERE deleted_at IS NULL AND status NOT IN ('rejected', 'withdrawn');

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
CREATE INDEX IF NOT EXISTS candidate_activities_candidate_date_idx ON public.candidate_activities (candidate_id, starts_at DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS public.candidate_activity_interviewers (
    activity_id UUID NOT NULL REFERENCES public.candidate_activities(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES public.recruitment_candidates(id) ON DELETE CASCADE,
    interviewer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (activity_id, interviewer_id)
);
CREATE INDEX IF NOT EXISTS candidate_activity_interviewer_scope_idx ON public.candidate_activity_interviewers (interviewer_id, candidate_id);

UPDATE public.permissions SET permissions = array_append(permissions, 'manage_candidates'), updated_at = now()
WHERE role IN ('hr', 'director') AND NOT ('manage_candidates' = ANY(permissions));
UPDATE public.permissions SET permissions = array_append(permissions, 'view_department_candidates'), updated_at = now()
WHERE role = 'manager' AND NOT ('view_department_candidates' = ANY(permissions));
UPDATE public.permissions SET permissions = array_append(permissions, 'view_assigned_candidates'), updated_at = now()
WHERE role = 'lead' AND NOT ('view_assigned_candidates' = ANY(permissions));

-- Asset inventory, employee custody, requests, and immutable assignment history.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.asset_categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  requires_return BOOLEAN NOT NULL DEFAULT true,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.asset_catalog (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  category_id UUID NOT NULL REFERENCES public.asset_categories(id),
  name TEXT NOT NULL,
  manufacturer TEXT,
  model TEXT,
  tracking_mode TEXT NOT NULL CHECK (tracking_mode IN ('serialized', 'bulk')),
  notes TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category_id, name, manufacturer, model)
);
CREATE INDEX IF NOT EXISTS asset_catalog_active_category_idx ON public.asset_catalog (category_id, active, name);

CREATE TABLE IF NOT EXISTS public.asset_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  asset_tag TEXT NOT NULL UNIQUE,
  serial_number TEXT UNIQUE,
  department TEXT,
  location TEXT,
  purchase_date DATE,
  purchase_cost NUMERIC(14,2) CHECK (purchase_cost IS NULL OR purchase_cost >= 0),
  warranty_expires_at DATE,
  condition TEXT NOT NULL DEFAULT 'new' CHECK (condition IN ('new', 'good', 'fair', 'damaged')),
  status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'issued', 'returned', 'maintenance', 'lost', 'retired')),
  notes TEXT,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_items_scope_status_idx ON public.asset_items (department, status, catalog_id);
CREATE UNIQUE INDEX IF NOT EXISTS asset_items_asset_tag_ci_unique_idx ON public.asset_items (lower(asset_tag));
CREATE UNIQUE INDEX IF NOT EXISTS asset_items_serial_ci_unique_idx ON public.asset_items (lower(serial_number)) WHERE serial_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.asset_stock_balances (
  catalog_id UUID PRIMARY KEY REFERENCES public.asset_catalog(id),
  quantity_total INTEGER NOT NULL DEFAULT 0 CHECK (quantity_total >= 0),
  quantity_available INTEGER NOT NULL DEFAULT 0 CHECK (quantity_available >= 0 AND quantity_available <= quantity_total),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.asset_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  employee_id UUID NOT NULL REFERENCES public.users(id),
  department TEXT,
  requested_by UUID NOT NULL REFERENCES public.users(id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled', 'fulfilled')),
  reason TEXT,
  decision_note TEXT,
  reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_requests_employee_status_idx ON public.asset_requests (employee_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS asset_requests_status_idx ON public.asset_requests (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.asset_request_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  request_id UUID NOT NULL REFERENCES public.asset_requests(id) ON DELETE CASCADE,
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS public.asset_assignments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  employee_id UUID NOT NULL REFERENCES public.users(id),
  department TEXT,
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  asset_item_id UUID REFERENCES public.asset_items(id),
  request_id UUID REFERENCES public.asset_requests(id) ON DELETE SET NULL,
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
  returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0 AND returned_quantity <= quantity),
  assigned_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
  due_date DATE,
  status TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'partially_returned', 'return_requested', 'returned', 'overdue', 'lost')),
  acknowledged_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (due_date IS NULL OR due_date >= issue_date),
  CHECK ((asset_item_id IS NULL AND quantity >= 1) OR (asset_item_id IS NOT NULL AND quantity = 1))
);
ALTER TABLE public.asset_assignments ADD COLUMN IF NOT EXISTS department TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS asset_assignments_one_active_unit_idx ON public.asset_assignments (asset_item_id) WHERE asset_item_id IS NOT NULL AND status IN ('issued', 'partially_returned', 'return_requested', 'overdue');
CREATE INDEX IF NOT EXISTS asset_assignments_employee_status_idx ON public.asset_assignments (employee_id, status, issue_date DESC);
CREATE INDEX IF NOT EXISTS asset_assignments_catalog_status_idx ON public.asset_assignments (catalog_id, status);

CREATE TABLE IF NOT EXISTS public.asset_assignment_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  assignment_id UUID NOT NULL REFERENCES public.asset_assignments(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('issued', 'acknowledged', 'return_requested', 'partially_returned', 'returned', 'damaged', 'lost', 'status_changed')),
  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  condition TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_assignment_events_history_idx ON public.asset_assignment_events (assignment_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.asset_stock_movements (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  catalog_id UUID NOT NULL REFERENCES public.asset_catalog(id),
  assignment_id UUID REFERENCES public.asset_assignments(id) ON DELETE SET NULL,
  actor_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  movement_type TEXT NOT NULL CHECK (movement_type IN ('received', 'issued', 'returned', 'damaged_return', 'lost', 'adjustment')),
  quantity_change INTEGER NOT NULL,
  reference TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_stock_movements_catalog_history_idx ON public.asset_stock_movements (catalog_id, created_at DESC);

INSERT INTO public.asset_categories (name, description, requires_return) VALUES
  ('IT Equipment', 'Computers, peripherals, and other IT equipment', true),
  ('ID Cards', 'Employee identity and access cards', true),
  ('Gifts', 'Company gifts and welcome kits', false),
  ('Office Equipment', 'Shared or assigned office equipment', true)
ON CONFLICT (name) DO NOTHING;

CREATE OR REPLACE FUNCTION public.receive_asset_stock(
  p_catalog_id UUID, p_actor_id UUID, p_quantity INTEGER, p_reference TEXT, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  v_balance public.asset_stock_balances%ROWTYPE;
BEGIN
  IF p_quantity < 1 THEN RAISE EXCEPTION 'Received quantity must be positive'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.asset_catalog WHERE id=p_catalog_id AND active=true AND tracking_mode='bulk') THEN
    RAISE EXCEPTION 'Active bulk asset type not found';
  END IF;
  INSERT INTO public.asset_stock_balances (catalog_id,quantity_total,quantity_available)
  VALUES (p_catalog_id,p_quantity,p_quantity)
  ON CONFLICT (catalog_id) DO UPDATE SET quantity_total=asset_stock_balances.quantity_total+p_quantity, quantity_available=asset_stock_balances.quantity_available+p_quantity, updated_at=now()
  RETURNING * INTO v_balance;
  INSERT INTO public.asset_stock_movements (catalog_id,actor_id,movement_type,quantity_change,reference,notes)
  VALUES (p_catalog_id,p_actor_id,'received',p_quantity,p_reference,p_notes);
  RETURN to_jsonb(v_balance);
END;
$$;

CREATE OR REPLACE FUNCTION public.issue_assets(
  p_actor_id UUID, p_lines JSONB, p_issue_date DATE, p_due_date DATE, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  line JSONB;
  v_employee UUID;
  v_catalog UUID;
  v_item UUID;
  v_request UUID;
  v_quantity INTEGER;
  v_mode TEXT;
  v_status TEXT;
  v_department TEXT;
  v_available INTEGER;
  v_assignment UUID;
  v_ids JSONB := '[]'::JSONB;
BEGIN
  IF p_due_date IS NOT NULL AND p_due_date < p_issue_date THEN RAISE EXCEPTION 'Due date cannot be earlier than issue date'; END IF;
  FOR line IN SELECT value FROM jsonb_array_elements(p_lines) LOOP
    v_employee := (line->>'employee_id')::UUID;
    v_catalog := (line->>'catalog_id')::UUID;
    v_item := NULLIF(line->>'asset_item_id', '')::UUID;
    v_request := NULLIF(line->>'request_id', '')::UUID;
    v_quantity := COALESCE((line->>'quantity')::INTEGER, 1);
    SELECT department INTO v_department FROM public.users WHERE id=v_employee AND status='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'An employee in this issue batch is inactive or missing'; END IF;
    SELECT tracking_mode INTO v_mode FROM public.asset_catalog WHERE id=v_catalog AND active=true FOR UPDATE;
    IF v_mode IS NULL THEN RAISE EXCEPTION 'An asset catalog item is unavailable'; END IF;
    IF v_mode='serialized' THEN
      IF v_quantity<>1 THEN RAISE EXCEPTION 'Serialized assets are issued one physical item per employee'; END IF;
      IF v_item IS NULL THEN
        SELECT id INTO v_item FROM public.asset_items WHERE catalog_id=v_catalog AND status IN ('available','returned') ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
      END IF;
      IF v_item IS NULL THEN RAISE EXCEPTION 'No physical unit is available for a recipient'; END IF;
      SELECT status INTO v_status FROM public.asset_items WHERE id=v_item AND catalog_id=v_catalog FOR UPDATE;
      IF v_status NOT IN ('available','returned') OR v_status IS NULL THEN RAISE EXCEPTION 'A selected asset item is no longer available'; END IF;
      UPDATE public.asset_items SET status='issued', department=v_department, updated_at=now() WHERE id=v_item;
    ELSE
      IF v_item IS NOT NULL THEN RAISE EXCEPTION 'Bulk stock does not accept a serialized item id'; END IF;
      SELECT quantity_available INTO v_available FROM public.asset_stock_balances WHERE catalog_id=v_catalog FOR UPDATE;
      IF v_available IS NULL OR v_available < v_quantity THEN RAISE EXCEPTION 'Not enough available stock'; END IF;
      UPDATE public.asset_stock_balances SET quantity_available=quantity_available-v_quantity, updated_at=now() WHERE catalog_id=v_catalog;
    END IF;
    INSERT INTO public.asset_assignments (employee_id,department,catalog_id,asset_item_id,request_id,quantity,assigned_by,issue_date,due_date,status,notes)
    VALUES (v_employee,v_department,v_catalog,v_item,v_request,v_quantity,p_actor_id,p_issue_date,p_due_date,'issued',p_notes) RETURNING id INTO v_assignment;
    INSERT INTO public.asset_assignment_events (assignment_id,actor_id,event_type,quantity,notes)
    VALUES (v_assignment,p_actor_id,'issued',v_quantity,p_notes);
    IF v_mode='bulk' THEN
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (v_catalog,v_assignment,p_actor_id,'issued',-v_quantity,p_notes);
    END IF;
    v_ids := v_ids || jsonb_build_array(v_assignment);
  END LOOP;
  IF v_request IS NOT NULL THEN
    UPDATE public.asset_requests SET status='fulfilled', updated_at=now() WHERE id=v_request AND status='approved';
    IF NOT FOUND THEN RAISE EXCEPTION 'The approved asset request changed before it could be fulfilled'; END IF;
  END IF;
  RETURN v_ids;
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_asset_return(
  p_assignment_id UUID, p_actor_id UUID, p_quantity INTEGER, p_condition TEXT, p_notes TEXT
) RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  a public.asset_assignments%ROWTYPE;
  v_remaining INTEGER;
  v_status TEXT;
BEGIN
  SELECT * INTO a FROM public.asset_assignments WHERE id=p_assignment_id FOR UPDATE;
  IF NOT FOUND OR a.status NOT IN ('issued','partially_returned','return_requested','overdue') THEN RAISE EXCEPTION 'This assignment cannot be returned'; END IF;
  v_remaining := a.quantity-a.returned_quantity;
  IF p_quantity < 1 OR p_quantity > v_remaining THEN RAISE EXCEPTION 'Return quantity exceeds the outstanding quantity'; END IF;
  IF p_condition='lost' AND p_quantity<>v_remaining THEN RAISE EXCEPTION 'Mark all outstanding units lost together'; END IF;
  IF a.asset_item_id IS NOT NULL AND p_quantity<>1 THEN RAISE EXCEPTION 'A serialized asset must be returned as one physical item'; END IF;
  IF p_condition NOT IN ('new','good','fair','damaged','lost') THEN RAISE EXCEPTION 'Unsupported return condition'; END IF;
  IF p_condition='lost' THEN
    v_status := 'lost';
    IF a.asset_item_id IS NOT NULL THEN UPDATE public.asset_items SET status='lost',condition='damaged',updated_at=now() WHERE id=a.asset_item_id; END IF;
  ELSE
    v_status := CASE WHEN a.returned_quantity+p_quantity=a.quantity THEN 'returned' ELSE 'partially_returned' END;
    IF a.asset_item_id IS NOT NULL THEN
      UPDATE public.asset_items SET status=CASE WHEN p_condition='damaged' THEN 'maintenance' ELSE 'returned' END, condition=p_condition, updated_at=now() WHERE id=a.asset_item_id;
    ELSIF p_condition='damaged' THEN
      UPDATE public.asset_stock_balances SET quantity_total=quantity_total-p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (a.catalog_id,a.id,p_actor_id,'damaged_return',-p_quantity,p_notes);
    ELSE
      UPDATE public.asset_stock_balances SET quantity_available=quantity_available+p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
      INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
      VALUES (a.catalog_id,a.id,p_actor_id,'returned',p_quantity,p_notes);
    END IF;
  END IF;
  UPDATE public.asset_assignments SET returned_quantity=returned_quantity+p_quantity,status=v_status,updated_at=now() WHERE id=a.id;
  INSERT INTO public.asset_assignment_events (assignment_id,actor_id,event_type,quantity,condition,notes)
  VALUES (a.id,p_actor_id,CASE WHEN p_condition='lost' THEN 'lost' WHEN p_condition='damaged' THEN 'damaged' WHEN v_status='returned' THEN 'returned' ELSE 'partially_returned' END,p_quantity,p_condition,p_notes);
  IF p_condition='lost' AND a.asset_item_id IS NULL THEN
    UPDATE public.asset_stock_balances SET quantity_total=quantity_total-p_quantity, updated_at=now() WHERE catalog_id=a.catalog_id;
    INSERT INTO public.asset_stock_movements (catalog_id,assignment_id,actor_id,movement_type,quantity_change,notes)
    VALUES (a.catalog_id,a.id,p_actor_id,'lost',-p_quantity,p_notes);
  END IF;
  RETURN (SELECT to_jsonb(x) FROM public.asset_assignments x WHERE x.id=a.id);
END;
$$;

UPDATE public.permissions SET permissions=array_append(permissions,'manage_assets'),updated_at=now()
WHERE role IN ('hr','director','super_admin') AND NOT ('manage_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_department_assets'),updated_at=now()
WHERE role='manager' AND NOT ('view_department_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_reporting_assets'),updated_at=now()
WHERE role='lead' AND NOT ('view_reporting_assets'=ANY(permissions));
UPDATE public.permissions SET permissions=array_append(permissions,'view_own_assets'),updated_at=now()
WHERE role='employee' AND NOT ('view_own_assets'=ANY(permissions));

REVOKE ALL ON FUNCTION public.issue_assets(UUID,JSONB,DATE,DATE,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.complete_asset_return(UUID,UUID,INTEGER,TEXT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.receive_asset_stock(UUID,UUID,INTEGER,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.issue_assets(UUID,JSONB,DATE,DATE,TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_asset_return(UUID,UUID,INTEGER,TEXT,TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.receive_asset_stock(UUID,UUID,INTEGER,TEXT,TEXT) TO service_role;

ALTER TABLE public.asset_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_stock_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_request_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_assignment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_stock_movements ENABLE ROW LEVEL SECURITY;

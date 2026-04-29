-- Supabase PostgreSQL Schema for JoyHR Application
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

-- Shifts table
CREATE TABLE IF NOT EXISTS shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    employee_name TEXT,
    employee_email TEXT,
    shift_type TEXT,
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
    ADD COLUMN IF NOT EXISTS target_audience JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS expiry_date TEXT,
    ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_by_name TEXT;

ALTER TABLE IF EXISTS shifts
    ADD COLUMN IF NOT EXISTS employee_id UUID REFERENCES users(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS employee_name TEXT,
    ADD COLUMN IF NOT EXISTS employee_email TEXT,
    ADD COLUMN IF NOT EXISTS shift_type TEXT,
    ADD COLUMN IF NOT EXISTS shift_date TEXT,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by_name TEXT,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_by_name TEXT,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

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

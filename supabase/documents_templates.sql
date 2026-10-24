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

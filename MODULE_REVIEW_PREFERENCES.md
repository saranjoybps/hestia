# Module-by-module review preferences

For each module review, use the server-readable HttpOnly Firebase session cookie for authenticated SSR and user-scoped data prefetching; avoid visible loading states and unnecessary copy; verify complete CRUD flows and list/detail behavior; verify counts, filters, and tab navigation; enforce immutable account email after creation; and inspect role-based access plus reporting hierarchy at both the UI and API layers.

Do not run lint, build, type checks, or tests unless the user explicitly asks. When the user adds review requirements, update this checklist and apply them to the current and subsequent modules.

For every drawer/sheet design, provide clear, consistent internal padding around the header, fields, content, and actions; never let drawer content touch the panel edges. Use responsive drawer sizing so the spacing remains usable on narrow screens.

Leave requests must offer every configured leave type and must not impose arbitrary per-type or total-day caps unless an explicit organization policy is defined. Compute requested days from the submitted date range on the server, prevent overlapping active requests, and enforce approver access through the reporting hierarchy.

For authenticated dashboard modules, fetch the initial user-scoped data on the server from the HttpOnly session cookie and pass it into the client screen. Do not show a first-load spinner or skeleton; keep filters local when the prefetched dataset is sufficient. Apply role and hierarchy checks in backend endpoints as well as in the visible UI. Draft announcements must only be visible to their author and authorized administrators.

Use the Attendance module's compact four-card summary pattern as the shared card design language for dashboard modules: responsive grid, concise metric label, clear count, and a small colored icon.

For task workflows, keep employees limited to their own assigned tasks; leads and managers can see and manage same-department tasks plus tasks assigned within their reporting hierarchy, including reportees in another department. When their department is unset, do not apply a department filter. Directors can view and manage tasks across departments. Keep task assignee choices and API assignment checks consistent with these rules. Do not add task file upload functionality until explicitly requested.

Keep personal tabs strictly self-scoped. Show team or organization records in separately named tabs that match the viewer's reporting scope; keep pending approval queues separate from approved history so reviewed records remain discoverable.

For Documents, support English templates only in the initial implementation; do not add a language selector. Keep templates customizable through versioned drafts and explicit publishing, and snapshot the published template and employee/company data on each issued request. Keep generated PDFs private and serve downloads through authorized backend endpoints. HR and Directors may submit documents for employees; Director approval is required for HR requests, while a Director's own request may be issued directly. HR, Directors, and super administrators may manage templates and company document settings. Do not expose employee documents through public Drive links.

For Organization and Profile, make Profile reachable from the header only and hide Settings from the header UI. Employees may change only their own name and phone; email, role, department, designation, joining date, status, and reporting lines are controlled organizational data. HR, Directors, and super administrators can manage organizational attributes and department structure; HR remains outside the employee reporting chain, while Directors retain organization-wide visibility and approval authority. Validate reporting-role compatibility and reject hierarchy cycles in the API. Server-prefetch the user's profile, reporting person, organization users, and departments; avoid first-load spinners. Include an in-app Roles & Access help view that explains reporting lines, department scope, and each role's application access.

For dashboard workflows, use a right-side panel for forms, details, approvals, and help content instead of centered popup modals. Keep generous internal padding, readable widths on mobile, and a clear header/footer in each panel.

For Reports & Analytics, server-render the initial report data from the HttpOnly session cookie and keep first-load free of spinners. Apply the same role and reporting-hierarchy scope to each report, department filters, and exports. Validate date ranges, include overlapping leave periods, use actual database foreign-key fields for performance reviews, and make period-based employee metrics honor the selected dates. Offer only export formats the backend supports.

For the Dashboard, server-prefetch the current user's authorized attendance/team scope, relevant pending leave count, visible published announcements, and department count. Keep the initial view free of loading placeholders, use India local dates for attendance, and do not show organization-wide totals to users whose access is limited to their team or themselves.

# Candidate / Recruitment module
- Provide server-rendered initial candidate rows, counts, departments, and eligible people; keep the first paint free of a blocking loading screen and prefetch candidate details on likely navigation where practical.
- Keep the recruitment pipeline scoped by role and department: HR/Director/Super Admin organization-wide; Managers own department only; Leads only candidates for which they are assigned interviewers; Employees no access. Enforce all rules on the backend.
- Support candidate create/edit, pipeline updates, interview/meeting scheduling, interviewer assignments, chronological notes/feedback, and permission-scoped deletion.
- Convert only selected/offer-sent candidates into employees with department, designation, role, reporting manager, joining date, and Firebase one-time password setup email; never expose or persist a temporary password.
- Use the Hestia UI language, right-side drawers with generous padding, clear validation, and no popup modals for the module workflows.

# Assets module
- Keep reusable asset catalog types separate from serialized physical units and bulk stock, with per-employee assignment and immutable issue/return history.
- Apply backend-enforced role scope: HR, Director, and Super Admin can administer inventory organization-wide; managers view their department and reporting team; leads view their reporting team; employees view only their own assignments.
- Support multi-employee issuance, stock receipts, approval requests, employee receipt acknowledgement, return requests, verified full/partial returns, damaged/lost/retired states, and audit events.
- Use atomic database operations for stock movement, batch issuance, and returns so concurrent requests cannot oversubscribe inventory or corrupt assignment history.
- SSR-prefetch the authenticated user's permitted inventory, assignment, request, and summary data from the HttpOnly session cookie. Keep first render free of a loading placeholder and use padded right-side drawers for workflows.

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import AssetsClient, { type AssetPageData } from './AssetsClient';

export const dynamic = 'force-dynamic';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const ACCESS_ROLES = ['employee', 'lead', 'manager', 'hr', 'director', 'super_admin'];

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

export default async function AssetsPage({ searchParams }: { searchParams: Promise<{ employee?: string }> }) {
  const params = await searchParams;
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) redirect('/login');
  const me = await apiGet('/users/me', token);
  if (!me || !ACCESS_ROLES.includes(String(me.role || '').toLowerCase())) redirect('/dashboard');
  const [inventory, assignments, requests, summary, options] = await Promise.all([
    apiGet('/assets?page=1&limit=100', token),
    apiGet(`/assets/assignments?page=1&limit=100${params.employee ? `&employee_id=${encodeURIComponent(params.employee)}` : ''}`, token),
    apiGet('/assets/requests', token),
    apiGet('/assets/summary', token),
    apiGet('/assets/options', token),
  ]);
  const initialData: AssetPageData = {
    role: String(me.role).toLowerCase(),
    userId: String(me.uid || ''),
    employeeId: String(options?.currentEmployeeId || ''),
    focusEmployee: params.employee || '',
    inventory: Array.isArray(inventory?.catalog) ? inventory.catalog : [],
    items: Array.isArray(inventory?.items) ? inventory.items : [],
    assignments: Array.isArray(assignments?.assignments) ? assignments.assignments : [],
    requests: Array.isArray(requests?.requests) ? requests.requests : [],
    summary: summary || { available: 0, issued: 0, returned: 0, pendingRequests: 0, overdue: 0 },
    categories: Array.isArray(options?.categories) ? options.categories : [],
    departments: Array.isArray(options?.departments) ? options.departments : [],
    employees: Array.isArray(options?.employees) ? options.employees : [],
    serverFetched: Boolean(inventory && assignments && requests && summary && options),
  };
  return <AssetsClient initialData={initialData} />;
}

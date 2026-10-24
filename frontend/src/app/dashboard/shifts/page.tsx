import { cookies } from 'next/headers';
import ShiftsClient, { type ShiftPageData } from './ShiftsClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

const emptyData: ShiftPageData = { role: 'employee', templates: [], allocations: [], pending: [], employees: [], serverFetched: false };

export default async function ShiftsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <ShiftsClient initialData={emptyData} />;

  const me = await apiGet('/users/me', token);
  if (!me) return <ShiftsClient initialData={emptyData} />;

  const role = me.role || 'employee';
  const canAllocate = ['lead', 'manager', 'hr', 'director', 'super_admin'].includes(role);
  const canApprove = ['manager', 'director', 'super_admin'].includes(role);
  const [templateData, allocationData, pendingData, employeeData] = await Promise.all([
    canAllocate ? apiGet('/shift-templates', token) : Promise.resolve(null),
    apiGet('/shifts', token),
    canApprove ? apiGet('/shifts/pending-approvals', token) : Promise.resolve(null),
    role === 'hr' || role === 'director' || role === 'super_admin'
      ? apiGet('/users?limit=500', token)
      : role === 'manager' || role === 'lead'
        ? apiGet(`/users/${me.uid}/reportees`, token)
        : Promise.resolve(null),
  ]);

  const employees = Array.isArray(employeeData?.users) ? employeeData.users : Array.isArray(employeeData) ? employeeData : [];
  return <ShiftsClient initialData={{
    role,
    templates: templateData?.templates || [],
    allocations: allocationData?.shifts || [],
    pending: pendingData?.shifts || [],
    employees: employees.filter((employee: any) => employee.uid !== me.uid && employee.status !== 'inactive'),
    serverFetched: true,
  }} />;
}

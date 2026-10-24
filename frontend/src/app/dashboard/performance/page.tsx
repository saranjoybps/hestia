import { cookies } from 'next/headers';
import PerformanceClient from './PerformanceClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const EMPTY = { user: { uid: '', name: '', role: 'employee' }, reviews: [], pending: [], employees: [], stats: null };

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

export default async function PerformancePage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <PerformanceClient initialData={EMPTY} />;
  const user = await apiGet('/users/me', token);
  if (!user) return <PerformanceClient initialData={EMPTY} />;

  const role = user.role || 'employee';
  const canCreate = ['lead', 'manager', 'hr', 'director', 'super_admin'].includes(role);
  const canReview = ['director', 'super_admin'].includes(role);
  const canReport = ['hr', 'director', 'super_admin'].includes(role);
  const employeePath = ['lead', 'manager'].includes(role)
    ? `/users/${encodeURIComponent(user.uid)}/reportees`
    : '/users?status=active&limit=500';
  const [reviews, pending, employees, stats] = await Promise.all([
    apiGet('/performance', token),
    canReview ? apiGet('/performance/pending-approvals', token) : Promise.resolve([]),
    canCreate ? apiGet(employeePath, token) : Promise.resolve([]),
    canReport ? apiGet('/performance/stats', token) : Promise.resolve(null),
  ]);
  const employeeList = Array.isArray(employees) ? employees : employees?.users || [];

  return <PerformanceClient initialData={{
    user: { uid: user.uid, name: user.name, role }, reviews: reviews || [], pending: pending || [],
    employees: employeeList.filter((employee: any) => employee.uid !== user.uid && employee.status !== 'inactive'), stats,
  }} />;
}

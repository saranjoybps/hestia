import { cookies } from 'next/headers';
import LeavesClient from './LeavesClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const EMPTY = { user: { uid: '', name: '', role: 'employee' }, leaves: [], pending: [], stats: null };

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

export default async function LeavesPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <LeavesClient initialData={EMPTY} />;
  const user = await apiGet('/users/me', token);
  if (!user) return <LeavesClient initialData={EMPTY} />;

  const role = user.role || 'employee';
  const canApprove = ['lead', 'manager', 'director', 'hr', 'super_admin'].includes(role);
  const canReport = ['hr', 'director', 'super_admin'].includes(role);
  const [leaves, pending, stats] = await Promise.all([
    apiGet('/leaves', token),
    canApprove ? apiGet('/leaves/pending-approvals', token) : Promise.resolve([]),
    canReport ? apiGet('/leaves/stats', token) : Promise.resolve(null),
  ]);

  return <LeavesClient initialData={{ user: { uid: user.uid, name: user.name, role }, leaves: leaves || [], pending: pending || [], stats }} />;
}

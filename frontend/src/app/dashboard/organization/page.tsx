import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import OrganizationClient, { type OrganizationPageData } from './OrganizationClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function OrganizationPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) redirect('/login');
  const user = await apiGet('/users/me', token);
  if (!user || !['hr', 'director', 'super_admin'].includes(String(user.role).toLowerCase())) redirect('/dashboard');

  const [usersResult, departmentResult] = await Promise.all([
    apiGet('/users?page=1&limit=500', token),
    apiGet('/departments', token),
  ]);
  const rawUsers = Array.isArray(usersResult?.users) ? usersResult.users : [];
  const uidById = new Map(rawUsers.map((person: any) => [String(person.id), String(person.uid)]));
  const users = rawUsers.map((person: any) => {
    const managerId = person.manager_id ?? person.managerId ?? person.lead_id ?? person.leadId;
    const managerUid = managerId ? (uidById.get(String(managerId)) || String(managerId)) : undefined;
    return { ...person, manager_id: managerUid, managerName: rawUsers.find((manager: any) => String(manager.uid) === managerUid)?.name };
  });
  const initialData: OrganizationPageData = {
    user: { uid: String(user.uid), name: String(user.name || ''), role: String(user.role).toLowerCase() },
    users,
    departments: Array.isArray(departmentResult?.departments) ? departmentResult.departments : [],
  };
  return <OrganizationClient initialData={initialData} />;
}

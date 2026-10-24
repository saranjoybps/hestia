import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import ProfileClient, { type ProfilePageData } from './ProfileClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function ProfilePage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) redirect('/login');
  const user = await apiGet('/users/me', token);
  if (!user) redirect('/login');
  const reportingId = user.manager_id || user.managerId || user.lead_id || user.leadId;
  const manager = reportingId ? await apiGet(`/users/${encodeURIComponent(reportingId)}`, token) : null;
  const initialData: ProfilePageData = {
    user,
    reportingPersonName: manager?.name || manager?.email || null,
  };
  return <ProfileClient initialData={initialData} />;
}

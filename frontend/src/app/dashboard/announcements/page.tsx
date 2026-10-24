import { cookies } from 'next/headers';
import AnnouncementsClient from './AnnouncementsClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const EMPTY = { user: { uid: '', name: '', role: 'employee' }, announcements: [], mine: [] };

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch { return null; }
}

export default async function AnnouncementsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <AnnouncementsClient initialData={EMPTY} />;
  const user = await apiGet('/users/me', token);
  if (!user) return <AnnouncementsClient initialData={EMPTY} />;
  const canManage = ['lead', 'manager', 'hr', 'director', 'super_admin'].includes(user.role);
  const [announcements, mine] = await Promise.all([
    apiGet('/announcements', token),
    canManage ? apiGet('/announcements/my-announcements', token) : Promise.resolve([]),
  ]);
  return <AnnouncementsClient initialData={{
    user: { uid: user.uid, name: user.name, role: user.role }, announcements: announcements || [], mine: mine || [],
  }} />;
}

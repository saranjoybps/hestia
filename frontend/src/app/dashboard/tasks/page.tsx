import { cookies } from 'next/headers';
import TasksClient from './TasksClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const EMPTY = { user: { uid: '', name: '', role: 'employee', department: '' }, tasks: [], employees: [] };

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function TasksPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <TasksClient initialData={EMPTY} />;

  const user = await apiGet('/users/me', token);
  if (!user) return <TasksClient initialData={EMPTY} />;

  const [tasks, employees] = await Promise.all([
    apiGet('/tasks', token),
    ['lead', 'manager', 'director', 'hr', 'super_admin'].includes(String(user.role || '').toLowerCase())
      ? apiGet('/tasks/assignees', token)
      : Promise.resolve([]),
  ]);

  return <TasksClient initialData={{
    user: { uid: user.uid, name: user.name, role: user.role, department: user.department || '' },
    tasks: tasks || [],
    employees: employees || [],
  }} />;
}

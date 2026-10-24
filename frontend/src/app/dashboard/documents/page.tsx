import { cookies } from 'next/headers';
import DocumentsClient, { type DocumentsPageData } from './DocumentsClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const EMPTY: DocumentsPageData = {
  user: { uid: '', name: '', role: 'employee' }, employees: [], requests: [], pendingRequests: [],
  issuedLetters: [], templates: [], settings: null,
};

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function DocumentsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <DocumentsClient initialData={EMPTY} />;

  const user = await apiGet('/users/me', token);
  if (!user) return <DocumentsClient initialData={EMPTY} />;
  const role = String(user.role || '').toLowerCase();
  const hasLettersAccess = role === 'hr' || role === 'director';
  const canManageTemplates = ['hr', 'director', 'super_admin'].includes(role);
  const [employees, requests, pendingRequests, issuedLetters, templates, settings] = await Promise.all([
    hasLettersAccess ? apiGet('/users?page=1&limit=500', token) : Promise.resolve(null),
    hasLettersAccess ? apiGet('/letters/requests', token) : Promise.resolve([]),
    role === 'director' ? apiGet('/letters/pending', token) : Promise.resolve([]),
    hasLettersAccess ? apiGet('/letters/issued', token) : Promise.resolve([]),
    canManageTemplates ? apiGet('/letters/templates', token) : Promise.resolve([]),
    canManageTemplates ? apiGet('/letters/settings', token) : Promise.resolve(null),
  ]);

  return <DocumentsClient initialData={{
    user: { uid: user.uid, name: user.name, role },
    employees: Array.isArray(employees?.users) ? employees.users : [],
    requests: Array.isArray(requests) ? requests : [],
    pendingRequests: Array.isArray(pendingRequests) ? pendingRequests : [],
    issuedLetters: Array.isArray(issuedLetters) ? issuedLetters : [],
    templates: Array.isArray(templates) ? templates : [],
    settings: settings || null,
  }} />;
}

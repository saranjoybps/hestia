import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import CandidatesClient, { type CandidatePageData } from './CandidatesClient';

export const dynamic = 'force-dynamic';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const ACCESS_ROLES = ['lead', 'manager', 'hr', 'director', 'super_admin'];

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

export default async function CandidatesPage({ searchParams }: { searchParams: Promise<{ status?: string; department?: string; q?: string; page?: string }> }) {
  const params = await searchParams;
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) redirect('/login');
  const me = await apiGet('/users/me', token);
  if (!me || !ACCESS_ROLES.includes(String(me.role || '').toLowerCase())) redirect('/dashboard');

  const page = Math.max(1, Number(params.page) || 1);
  const query = new URLSearchParams({ page: String(page), limit: '20' });
  if (params.status && params.status !== 'all') query.set('status', params.status);
  if (params.department && params.department !== 'all') query.set('department', params.department);
  if (params.q?.trim()) query.set('search', params.q.trim());

  const [list, options] = await Promise.all([
    apiGet(`/candidates?${query}`, token),
    apiGet('/candidates/options', token),
  ]);
  const initialData: CandidatePageData = {
    role: String(me.role).toLowerCase(),
    candidates: Array.isArray(list?.candidates) ? list.candidates : [],
    total: Number(list?.total || 0),
    page: Number(list?.page || page),
    totalPages: Number(list?.totalPages || 0),
    departments: Array.isArray(options?.departments) ? options.departments : [],
    interviewers: Array.isArray(options?.interviewers) ? options.interviewers : [],
    filters: { status: params.status || 'all', department: params.department || 'all', search: params.q || '' },
    serverFetched: Boolean(list && options),
  };
  return <CandidatesClient key={`${initialData.filters.status}:${initialData.filters.department}:${initialData.filters.search}:${initialData.page}`} initialData={initialData} />;
}

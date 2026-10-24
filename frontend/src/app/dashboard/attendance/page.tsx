import { cookies } from 'next/headers';
import AttendanceClient, { type AttendancePageData } from './AttendanceClient';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

function localToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

async function apiGet(path: string, token: string) {
  try {
    const response = await fetch(`${API}${path}`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
    });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}

const emptyData: AttendancePageData = {
  user: { uid: '', name: '', role: 'employee' }, team: [], roster: [], records: [], pending: [],
  selfShift: null, selfRecord: null, serverFetched: false,
};

export default async function AttendancePage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return <AttendanceClient initialData={emptyData} />;

  const me = await apiGet('/users/me', token);
  if (!me) return <AttendanceClient initialData={emptyData} />;
  const today = localToday();
  const start = `${today.slice(0, 7)}-01`;
  const endDate = new Date(Number(today.slice(0, 4)), Number(today.slice(5, 7)), 0);
  const end = `${today.slice(0, 7)}-${String(endDate.getDate()).padStart(2, '0')}`;
  const role = me.role || 'employee';
  const dashboard = await apiGet(`/attendance/dashboard?start_date=${start}&end_date=${end}&day=${today}`, token);

  return <AttendanceClient initialData={{
    user: dashboard?.user || { uid: me.uid, name: me.name, role },
    team: dashboard?.team || [], roster: dashboard?.roster || [],
    records: dashboard?.records || [], pending: dashboard?.pending || [],
    selfShift: dashboard?.selfShift || null, selfRecord: dashboard?.selfRecord || null,
    startDate: start, endDate: end, selectedDate: today, serverFetched: true,
  }} />;
}

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import DashboardClient, { type DashboardPageData } from './DashboardClient';

export const dynamic = 'force-dynamic';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const ORG_WIDE_ROLES = new Set(['hr', 'director', 'super_admin']);
const APPROVER_ROLES = new Set(['lead', 'manager', 'hr', 'director', 'super_admin']);

async function getApiData<T>(path: string, token: string): Promise<T | null> {
  try {
    const response = await fetch(`${API}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!response.ok) return null;
    return await response.json() as T;
  } catch {
    return null;
  }
}

function indiaDateParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function dateLabel(value?: string) {
  if (!value) return 'Recently';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently';
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
  }).format(date);
}

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) redirect('/login');

  const me = await getApiData<{ uid: string; name?: string; role: string; department?: string; status?: string }>('/users/me', token);
  if (!me?.uid) redirect('/login');
  const role = String(me.role || 'employee').toLowerCase();
  const todayParts = indiaDateParts(new Date());
  const today = `${todayParts.year}-${todayParts.month}-${todayParts.day}`;

  const departmentPath = ORG_WIDE_ROLES.has(role)
    ? '/departments'
    : role === 'lead' || role === 'manager'
      ? '/reports/departments'
      : null;
  const pendingPath = APPROVER_ROLES.has(role) ? '/leaves/pending-approvals' : '/leaves?status=pending';

  const [attendance, pendingLeaves, announcementRows, departmentData] = await Promise.all([
    getApiData<any>(`/attendance/dashboard?start_date=${today}&end_date=${today}&day=${today}`, token),
    getApiData<any[]>(pendingPath, token),
    getApiData<any[]>('/announcements', token),
    departmentPath ? getApiData<any>(departmentPath, token) : Promise.resolve(null),
  ]);

  const team = Array.isArray(attendance?.team) ? attendance.team : [];
  const people = new Map<string, any>();
  if (me.status !== 'inactive') people.set(me.uid, me);
  for (const person of team) {
    if (person?.uid && person.status !== 'inactive') people.set(String(person.uid), person);
  }

  const roster = Array.isArray(attendance?.roster) ? attendance.roster : [];
  const attendanceByUid = new Map<string, any>();
  for (const row of attendance?.records || []) {
    if (row?.userId) attendanceByUid.set(String(row.userId), row);
  }
  for (const person of roster) {
    if (person?.uid && person.attendance) attendanceByUid.set(String(person.uid), person.attendance);
  }
  if (me.uid && attendance?.selfRecord) attendanceByUid.set(me.uid, attendance.selfRecord);

  const scheduled: string[] = roster
    .filter((person: any) => person?.uid && person.shift)
    .map((person: any) => String(person.uid));
  if (me.uid && attendance?.selfShift) scheduled.push(me.uid);
  const uniqueScheduled = [...new Set(scheduled)];
  let presentToday = 0;
  let halfDayToday = 0;
  let attendanceWeight = 0;
  let attendanceDenominator = 0;
  for (const uid of uniqueScheduled) {
    const row = attendanceByUid.get(uid);
    const status = row?.status;
    if (status === 'on-leave' || status === 'week-off' || status === 'holiday' || row?.isLeaveDerived) continue;
    attendanceDenominator += 1;
    if ((row?.approvalStatus || 'approved') !== 'approved') continue;
    if (status === 'present') {
      presentToday += 1;
      attendanceWeight += 1;
    } else if (status === 'half-day' || status === 'half_day') {
      halfDayToday += 1;
      attendanceWeight += 0.5;
    }
  }

  const departmentList = Array.isArray(departmentData?.departments) ? departmentData.departments : [];
  const ownDepartmentCount = me.department ? 1 : 0;
  const totalDepartments = departmentData ? departmentList.length : ownDepartmentCount;
  const announcements = (Array.isArray(announcementRows) ? announcementRows : [])
    .slice(0, 3)
    .map((announcement: any) => ({
      id: String(announcement.id),
      title: String(announcement.title || 'Announcement'),
      description: announcement.description ? String(announcement.description) : '',
      createdAt: announcement.createdAt ? String(announcement.createdAt) : undefined,
      createdAtLabel: dateLabel(announcement.createdAt),
      priority: String(announcement.priority || 'medium'),
    }));

  const lastUpdated = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true,
  }).format(new Date());
  const scopeDescription = ORG_WIDE_ROLES.has(role)
    ? 'Active people across the organization'
    : role === 'lead' || role === 'manager'
      ? 'You and active people in your reporting scope'
      : 'Your account';
  const pendingLeavesDescription = APPROVER_ROLES.has(role)
    ? 'Requests in your approval queue'
    : 'Your requests awaiting review';

  const initialData: DashboardPageData = {
    stats: {
      peopleInScope: people.size,
      presentToday,
      halfDayToday,
      attendancePercentage: attendanceDenominator ? attendanceWeight / attendanceDenominator * 100 : 0,
      pendingLeaves: Array.isArray(pendingLeaves) ? pendingLeaves.length : 0,
      totalDepartments,
    },
    role,
    scopeDescription,
    pendingLeavesDescription,
    announcements,
    lastUpdated,
    hasPartialData: !attendance || !pendingLeaves || !announcementRows || (!!departmentPath && !departmentData),
  };

  return <DashboardClient initialData={initialData} />;
}

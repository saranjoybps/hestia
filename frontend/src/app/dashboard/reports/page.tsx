import { getReportsData, getReportsViewer } from './_actions/reportActions';
import { ReportsView } from './ReportsView';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

interface PageProps {
  searchParams: Promise<{
    startDate?: string;
    endDate?: string;
    department?: string;
  }>;
}

export default async function ReportsPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const nowParts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const parts = Object.fromEntries(nowParts.map((part) => [part.type, part.value]));
  const monthStart = `${parts.year}-${parts.month}-01`;
  const monthEnd = `${parts.year}-${parts.month}-${new Date(Number(parts.year), Number(parts.month), 0).getDate().toString().padStart(2, '0')}`;
  const validDate = (value?: string) => {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  };
  let startDate = validDate(params.startDate) ? params.startDate! : monthStart;
  let endDate = validDate(params.endDate) ? params.endDate! : monthEnd;
  if (endDate < startDate) { startDate = monthStart; endDate = monthEnd; }
  const department = params.department || 'all';

  // Verify auth via cookie (same as server actions)
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) {
    redirect('/login');
  }

  let viewer;
  try {
    viewer = await getReportsViewer();
  } catch {
    redirect('/login');
  }
  if (!['lead', 'manager', 'director', 'hr', 'super_admin'].includes(String(viewer?.role || '').toLowerCase())) redirect('/dashboard');

  // Fetch reports data server-side
  const data = await getReportsData(startDate, endDate, department === 'all' ? undefined : department);

  return (
    <ReportsView
      key={`${startDate}:${endDate}:${department}`}
      initialData={data}
      startDate={startDate}
      endDate={endDate}
      selectedDepartment={department}
    />
  );
}

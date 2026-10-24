import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const REPORT_TYPES = new Set(['attendance', 'leave', 'performance', 'employee']);

export async function GET(request: NextRequest, context: { params: Promise<{ type: string }> }) {
  const { type } = await context.params;
  if (!REPORT_TYPES.has(type)) return NextResponse.json({ error: 'Unknown report type' }, { status: 404 });

  const startDate = request.nextUrl.searchParams.get('startDate') || '';
  const endDate = request.nextUrl.searchParams.get('endDate') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(startDate) || !/^\d{4}-\d{2}-\d{2}$/.test(endDate) || endDate < startDate) {
    return NextResponse.json({ error: 'Invalid report date range' }, { status: 422 });
  }

  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });

  const params = new URLSearchParams({ startDate, endDate, format: 'csv' });
  const department = request.nextUrl.searchParams.get('department');
  if (department) params.set('department', department);

  try {
    const upstream = await fetch(`${API}/reports/export/${type}?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!upstream.ok) {
      return NextResponse.json({ error: 'Unable to export report' }, { status: upstream.status });
    }
    return new Response(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'text/csv; charset=utf-8',
        'Content-Disposition': upstream.headers.get('content-disposition') || `attachment; filename="${type}_report.csv"`,
        'Cache-Control': 'private, no-store',
      },
    });
  } catch {
    return NextResponse.json({ error: 'Report service is unavailable' }, { status: 502 });
  }
}

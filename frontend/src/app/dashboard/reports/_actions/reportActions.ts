'use server';

import { cookies } from 'next/headers';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get('hestia_session')?.value || cookieStore.get('joyhr_session')?.value;
  if (!token) throw new Error('Authentication required');
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function getReportsViewer() {
  return fetchJson<{ role?: string }>('/users/me');
}

export interface AttendanceReport {
  department: string;
  totalEmployees: number;
  presentCount: number;
  absentCount: number;
  leaveCount: number;
  halfDayCount: number;
  attendanceRate: number;
  avgWorkingHours: number;
}

export interface LeaveReport {
  department: string;
  totalLeaves: number;
  approvedLeaves: number;
  pendingLeaves: number;
  rejectedLeaves: number;
  leaveTypeCounts: Record<string, number>;
  avgLeaveDuration: number;
}

export interface PerformanceMetric {
  department: string;
  employeeCount: number;
  avgRating: number;
  positiveReviews: number;
  negativeReviews: number;
  pendingReviews: number;
  topPerformer: string;
}

export interface EmployeeMetric {
  name: string;
  department: string;
  designation: string;
  attendanceRate: number;
  leavesUsed: number;
  avgRating: number;
  tasksCompleted: number;
}

export interface ReportsData {
  attendance: AttendanceReport[];
  leaves: LeaveReport[];
  performance: PerformanceMetric[];
  employees: EmployeeMetric[];
  summary: {
    totalEmployees: number;
    avgAttendanceRate: number;
    totalLeaves: number;
    avgPerformanceRating: number;
  };
  departments: string[];
}

export async function getReportsData(
  startDate: string,
  endDate: string,
  department?: string
): Promise<ReportsData> {
  const params = new URLSearchParams({
    startDate,
    endDate,
    ...(department && department !== 'all' && { department }),
  });

  const [attendanceRes, leaveRes, performanceRes, employeeRes, deptRes] = await Promise.all([
    fetchJson<{ summary: { totalEmployees: number; avgAttendanceRate: number }; byDepartment: AttendanceReport[] }>(`/reports/attendance?${params}`),
    fetchJson<{ summary: { totalLeaves: number }; byDepartment: LeaveReport[] }>(`/reports/leaves?${params}`),
    fetchJson<{ summary: { avgRating: number }; byDepartment: PerformanceMetric[] }>(`/reports/performance?${params}`),
    fetchJson<{ employees: EmployeeMetric[] }>(`/reports/employees?${params}`),
    fetchJson<{ departments: string[] }>(`/reports/departments`),
  ]);

  return {
    attendance: attendanceRes.byDepartment || [],
    leaves: leaveRes.byDepartment || [],
    performance: performanceRes.byDepartment || [],
    employees: employeeRes.employees || [],
    summary: {
      totalEmployees: attendanceRes.summary?.totalEmployees || 0,
      avgAttendanceRate: attendanceRes.summary?.avgAttendanceRate || 0,
      totalLeaves: leaveRes.summary?.totalLeaves || 0,
      avgPerformanceRating: performanceRes.summary?.avgRating || 0,
    },
    departments: deptRes.departments || [],
  };
}


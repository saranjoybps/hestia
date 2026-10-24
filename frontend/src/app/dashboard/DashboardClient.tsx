'use client';

import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Users, Calendar, FileText, Building2, RefreshCw, Megaphone } from 'lucide-react';

interface DashboardAnnouncement {
  id: string;
  title: string;
  description?: string;
  createdAt?: string;
  createdAtLabel: string;
  priority: string;
}

export interface DashboardPageData {
  stats: {
    peopleInScope: number;
    presentToday: number;
    halfDayToday: number;
    attendancePercentage: number;
    pendingLeaves: number;
    totalDepartments: number;
  };
  role: string;
  scopeDescription: string;
  pendingLeavesDescription: string;
  announcements: DashboardAnnouncement[];
  lastUpdated: string;
  hasPartialData: boolean;
}

export default function DashboardClient({ initialData }: { initialData: DashboardPageData }) {
  const router = useRouter();
  const { stats } = initialData;
  const cards = [
    { title: 'People in scope', value: stats.peopleInScope, description: initialData.scopeDescription, icon: Users, color: 'text-blue-600', bg: 'bg-blue-50' },
    { title: 'Present today', value: stats.presentToday, description: `${stats.halfDayToday} half-day - ${stats.attendancePercentage.toFixed(1)}% of scheduled staff`, icon: Calendar, color: 'text-green-600', bg: 'bg-green-50' },
    { title: 'Pending leave requests', value: stats.pendingLeaves, description: initialData.pendingLeavesDescription, icon: FileText, color: 'text-amber-600', bg: 'bg-amber-50' },
    { title: 'Departments in scope', value: stats.totalDepartments, description: 'Departments represented in your access scope', icon: Building2, color: 'text-purple-600', bg: 'bg-purple-50' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-gray-500">A current overview of your authorized team and HR activity.</p>
          <p className="mt-1 text-xs text-gray-400">Updated {initialData.lastUpdated} IST</p>
        </div>
        <Button onClick={() => router.refresh()} variant="outline" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {initialData.hasPartialData && (
        <Alert>
          <AlertDescription>Some dashboard information could not be retrieved. Refresh to try again.</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ title, value, description, icon: Icon, color, bg }) => (
          <Card key={title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">{title}</CardTitle>
              <div className={`rounded-lg p-2 ${bg}`}><Icon className={`h-5 w-5 ${color}`} /></div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-gray-900">{value}</div>
              <p className="mt-1 text-xs text-gray-500">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Megaphone className="h-5 w-5 text-blue-600" />Recent announcements</CardTitle>
            <CardDescription>Published announcements visible to your role and department.</CardDescription>
          </CardHeader>
          <CardContent>
            {initialData.announcements.length ? (
              <div className="space-y-4">
                {initialData.announcements.map((announcement) => (
                  <div key={announcement.id} className="flex items-start gap-3">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${announcement.priority === 'urgent' ? 'bg-red-500' : announcement.priority === 'high' ? 'bg-orange-500' : announcement.priority === 'medium' ? 'bg-amber-500' : 'bg-blue-500'}`} />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900">{announcement.title}</p>
                      {announcement.description && <p className="mt-1 line-clamp-2 text-sm text-gray-600">{announcement.description}</p>}
                      <p className="mt-1 text-xs text-gray-500">{announcement.createdAtLabel}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-sm text-gray-500">No recent announcements.</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>At a glance</CardTitle>
            <CardDescription>Your reporting scope and items waiting for review.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Your access level</p>
              <p className="mt-1 font-semibold capitalize text-slate-900">{initialData.role.replace(/_/g, ' ')}</p>
              <p className="mt-1 text-sm text-slate-600">{initialData.scopeDescription}</p>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div>
                <p className="font-medium text-slate-900">Leave requests</p>
                <p className="text-sm text-slate-500">{initialData.pendingLeavesDescription}</p>
              </div>
              <span className="text-2xl font-semibold text-amber-600">{stats.pendingLeaves}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

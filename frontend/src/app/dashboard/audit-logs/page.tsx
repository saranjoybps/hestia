'use client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { AlertCircle, ClipboardList, RefreshCw } from 'lucide-react';

interface AuditLog {
  id: string;
  actor_id: string;
  actor_name?: string;
  actor_email?: string;
  module?: string;
  action: string;
  description?: string;
  result?: string;
  target_type?: string;
  target_id?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export default function AuditLogsPage() {
  const { userData, user } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [moduleFilter, setModuleFilter] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const hasAccess = userData?.role === 'director' || userData?.role === 'super_admin';

  useEffect(() => {
    if (user && hasAccess) {
      fetchLogs();
    }
  }, [user, hasAccess]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: '1',
        limit: '500',
      });

      const response = await fetch(`${API_BASE_URL}/audit-logs?${params}`, {
        headers: { 'Authorization': `Bearer ${await user?.getIdToken()}` },
      });
      if (!response.ok) throw new Error('Failed to load audit logs');
      const data = await response.json();
      setLogs(data || []);
    } catch (error) {
      console.error('Error fetching audit logs:', error);
      toast.error('Failed to fetch audit logs');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = (items: AuditLog[]) => {
    const from = fromDate ? new Date(fromDate).getTime() : null;
    const to = toDate ? new Date(toDate).getTime() : null;
    const moduleQuery = moduleFilter.trim().toLowerCase();

    return items.filter((log) => {
      const created = new Date(log.created_at).getTime();
      if (from && created < from) return false;
      if (to && created > to) return false;
      if (moduleQuery && !(log.module || '').toLowerCase().includes(moduleQuery)) return false;
      return true;
    });
  };

  const filteredLogs = applyFilters(logs);
  const totalPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const paginatedLogs = filteredLogs.slice(startIndex, startIndex + pageSize);

  if (!hasAccess) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Access Denied</h2>
          <p className="text-gray-600 mt-2">You don't have permission to view audit logs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-gray-600 mt-1">Track logins, sign-outs, and key actions across the system</p>
        </div>
        <Button onClick={fetchLogs} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Filter by date range and module</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="from-date">From</Label>
              <Input
                id="from-date"
                type="datetime-local"
                value={fromDate}
                onChange={(e) => {
                  setPage(1);
                  setFromDate(e.target.value);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="to-date">To</Label>
              <Input
                id="to-date"
                type="datetime-local"
                value={toDate}
                onChange={(e) => {
                  setPage(1);
                  setToDate(e.target.value);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="module-filter">Module</Label>
              <Input
                id="module-filter"
                value={moduleFilter}
                onChange={(e) => {
                  setPage(1);
                  setModuleFilter(e.target.value);
                }}
                placeholder="auth, attendance, leave_request..."
              />
            </div>
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setPage(1);
                  setFromDate('');
                  setToDate('');
                  setModuleFilter('');
                }}
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Events</CardTitle>
          <CardDescription>Latest audit entries</CardDescription>
        </CardHeader>
        <CardContent>
          {paginatedLogs.length > 0 ? (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Who</TableHead>
                    <TableHead>Module</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead className="w-[360px]">What Happened</TableHead>
                    <TableHead>Result</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{log.actor_name || 'Unknown'}</span>
                          <span className="text-xs text-gray-500">{log.actor_email || log.actor_id}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{log.module || '-'}</TableCell>
                      <TableCell className="font-medium">{log.action}</TableCell>
                      <TableCell
                        className="max-w-[360px] truncate"
                        title={log.description || ''}
                      >
                        {log.description || '-'}
                      </TableCell>
                      <TableCell>{log.result || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12">
              <ClipboardList className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No audit entries found</p>
            </div>
          )}

          {filteredLogs.length > 0 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-gray-500">
                Showing {startIndex + 1}-{Math.min(startIndex + pageSize, filteredLogs.length)} of {filteredLogs.length}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={safePage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Prev
                </Button>
                <span className="text-sm text-gray-600">
                  Page {safePage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={safePage >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

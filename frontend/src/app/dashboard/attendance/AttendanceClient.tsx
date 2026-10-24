'use client';

import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { CalendarDays, Check, Clock3, Download, Edit, UserCheck, Users, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const todayLocal = () => {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
};
const yesterdayLocal = () => {
  const previous = new Date(`${todayLocal()}T00:00:00Z`);
  previous.setUTCDate(previous.getUTCDate() - 1);
  return previous.toISOString().slice(0, 10);
};
const rolesWithTeam = ['lead', 'manager', 'hr', 'director', 'super_admin'];

export interface AttendanceRecord {
  id: string; userId: string; userName: string; date: string; checkIn: string | null; checkOut: string | null;
  status: string; workHours: number; notes: string; approvalStatus: 'approved' | 'pending' | 'rejected';
  pendingStatus?: string; pendingCheckIn?: string; pendingCheckOut?: string; pendingNotes?: string;
  correctionReason?: string; reviewReason?: string; isLeaveDerived?: boolean;
}

interface Employee { uid: string; name: string; email?: string; department?: string; designation?: string }
interface RosterRow extends Employee { shift: null | { id: string; name: string; start_time: string; end_time: string }; attendance: AttendanceRecord | null }
export interface AttendancePageData {
  user: { uid: string; name: string; role: string }; team: Employee[]; roster: RosterRow[];
  records: AttendanceRecord[]; pending: AttendanceRecord[]; selfShift: any; selfRecord: AttendanceRecord | null;
  startDate?: string; endDate?: string; selectedDate?: string; serverFetched: boolean;
}

export default function AttendanceClient({ initialData }: { initialData: AttendancePageData }) {
  const { user } = useAuth();
  const [records, setRecords] = useState(initialData.records);
  const [roster, setRoster] = useState(initialData.roster);
  const [pending, setPending] = useState(initialData.pending);
  const [selfRecord, setSelfRecord] = useState(initialData.selfRecord);
  const [selfShift, setSelfShift] = useState(initialData.selfShift);
  const [selectedDate, setSelectedDate] = useState(initialData.selectedDate || todayLocal());
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isSelfRequest, setIsSelfRequest] = useState(false);
  const [selfRequestDate, setSelfRequestDate] = useState(yesterdayLocal());
  const [editing, setEditing] = useState<AttendanceRecord | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [form, setForm] = useState({ status: 'present', check_in: '', check_out: '', reason: '' });
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);

  const role = initialData.user.role;
  const canManageTeam = rolesWithTeam.includes(role);
  const canReview = ['lead', 'manager', 'director', 'super_admin'].includes(role);
  const mine = useMemo(() => records.filter((row) => row.userId === initialData.user.uid), [records, initialData.user.uid]);
  const filteredRoster = roster.filter((row) => `${row.name} ${row.email || ''} ${row.department || ''}`.toLowerCase().includes(search.toLowerCase()));
  const stats = {
    present: mine.filter((row) => row.approvalStatus === 'approved' && row.status === 'present').length,
    absent: mine.filter((row) => row.approvalStatus === 'approved' && row.status === 'absent').length,
    leave: mine.filter((row) => row.approvalStatus === 'approved' && ['on-leave', 'leave'].includes(row.status)).length,
    hours: mine.filter((row) => row.approvalStatus === 'approved').reduce((total, row) => total + (row.workHours || 0), 0),
  };

  const apiRequest = async (path: string, init: RequestInit = {}) => {
    const token = await user?.getIdToken();
    if (!token) throw new Error('Please sign in again');
    const response = await fetch(`${API}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(init.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed');
    return data;
  };

  const refresh = async (day = selectedDate) => {
    const token = await user?.getIdToken();
    if (!token) return;
    const dateStart = `${day.slice(0, 7)}-01`;
    const monthEnd = new Date(Number(day.slice(0, 4)), Number(day.slice(5, 7)), 0).getDate();
    const dateEnd = `${day.slice(0, 7)}-${String(monthEnd).padStart(2, '0')}`;
    const response = await fetch(`${API}/attendance/dashboard?start_date=${dateStart}&end_date=${dateEnd}&day=${day}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    if (!response.ok) throw new Error('Unable to refresh attendance');
    const dashboard = await response.json();
    setRecords(dashboard.records || []); setSelfRecord(dashboard.selfRecord || null); setSelfShift(dashboard.selfShift || null);
    if (canManageTeam) setRoster(dashboard.roster || []);
    if (canReview) setPending(dashboard.pending || []);
  };

  const changeAttendanceDate = async (day: string) => {
    if (!day) return;
    setSelectedDate(day);
    try { await refresh(day); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to load attendance'); }
  };

  const updateRosterRow = (employeeUid: string, attendance: AttendanceRecord) => {
    setRoster((current) => current.map((row) => row.uid === employeeUid ? { ...row, attendance } : row));
    setRecords((current) => [attendance, ...current.filter((row) => row.id !== attendance.id)]);
  };

  const punch = async (action: 'check-in' | 'check-out') => {
    setSaving(true);
    try {
      const result = await apiRequest(`/attendance/${action}`, { method: 'POST' });
      setSelfRecord(result);
      setRecords((current) => [result, ...current.filter((row) => row.id !== result.id)]);
      toast.success(action === 'check-in' ? 'Check-in recorded' : 'Check-out recorded');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to record attendance'); }
    finally { setSaving(false); }
  };

  const openManualEntry = (employee: RosterRow) => {
    setSelectedEmployee(employee); setEditing(null); setIsSelfRequest(false);
    setForm({ status: employee.shift ? 'present' : 'week_off', check_in: '', check_out: '', reason: '' }); setDrawerOpen(true);
  };

  const openCorrection = (employee: RosterRow, record: AttendanceRecord) => {
    setSelectedEmployee(employee); setEditing(record); setIsSelfRequest(false);
    const normalizedStatus = record.status.replace('-', '_');
    setForm({ status: normalizedStatus === 'on_leave' ? 'leave' : normalizedStatus, check_in: record.checkIn || '', check_out: record.checkOut || '', reason: '' }); setDrawerOpen(true);
  };

  const openSelfRequest = () => {
    setSelectedEmployee({ uid: initialData.user.uid, name: initialData.user.name });
    setEditing(null); setIsSelfRequest(true); setSelfRequestDate(yesterdayLocal());
    setForm({ status: 'present', check_in: '', check_out: '', reason: '' }); setDrawerOpen(true);
  };

  const saveManual = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedEmployee) return;
    if (form.status === 'present' && (!form.check_in || !form.check_out)) { toast.error('Enter both check-in and check-out times'); return; }
    if (isSelfRequest && !form.reason.trim()) { toast.error('Add a reason for the missed attendance'); return; }
    setSaving(true);
    try {
      const payload = { user_id: selectedEmployee.uid, date: isSelfRequest ? selfRequestDate : selectedDate, status: form.status, check_in: form.check_in || null, check_out: form.check_out || null, reason: form.reason };
      const path = isSelfRequest ? '/attendance/self-request' : editing ? `/attendance/${editing.id}` : '/attendance';
      const result = await apiRequest(path, { method: editing ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      if (isSelfRequest) {
        setRecords((current) => [result, ...current.filter((row) => row.id !== result.id)]);
        if (canReview) setPending((current) => [result, ...current.filter((row) => row.id !== result.id)]);
      } else updateRosterRow(selectedEmployee.uid, result);
      if (result.approvalStatus === 'pending') setPending((current) => [result, ...current.filter((row) => row.id !== result.id)]);
      setDrawerOpen(false);
      toast.success(isSelfRequest ? 'Past attendance submitted for review' : result.approvalStatus === 'pending' ? 'Submitted for review' : 'Attendance saved');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to save attendance'); }
    finally { setSaving(false); }
  };

  const review = async (record: AttendanceRecord, decision: 'approve' | 'reject', reason = '') => {
    if (decision === 'reject' && !reason.trim()) { toast.error('Enter a rejection reason'); return; }
    try {
      const result = await apiRequest(`/attendance/${record.id}/${decision}`, { method: 'PATCH', body: JSON.stringify({ reason }) });
      setPending((current) => current.filter((row) => row.id !== record.id));
      setRejectingId(null); setRejectionReason('');
      setRecords((current) => current.map((row) => row.id === record.id ? result : row));
      setRoster((current) => current.map((row) => row.uid === result.userId ? { ...row, attendance: result } : row));
      toast.success(decision === 'approve' ? 'Attendance approved' : 'Attendance request rejected');
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to review attendance'); }
  };

  const statusBadge = (record: AttendanceRecord) => {
    if (record.approvalStatus === 'pending') return <Badge className="bg-amber-100 text-amber-800">Pending review</Badge>;
    if (record.approvalStatus === 'rejected') return <Badge variant="destructive">Rejected</Badge>;
    const color = record.status === 'present' ? 'bg-emerald-100 text-emerald-800' : record.status === 'absent' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700';
    return <Badge className={color}>{record.status.replace('-', ' ')}</Badge>;
  };

  const exportRecords = () => {
    const monthEnd = new Date(Number(selectedDate.slice(0, 4)), Number(selectedDate.slice(5, 7)), 0).getDate();
    const params = new URLSearchParams({ startDate: `${selectedDate.slice(0, 7)}-01`, endDate: `${selectedDate.slice(0, 7)}-${String(monthEnd).padStart(2, '0')}` });
    void (async () => {
      try {
        const token = await user?.getIdToken();
        const response = await fetch(`${API}/reports/attendance/team-export?${params.toString()}`, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) throw new Error('Unable to export attendance');
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a'); link.href = url; link.download = `attendance_${params.get('startDate')}_${params.get('endDate')}.csv`; link.click(); URL.revokeObjectURL(url);
      } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to export attendance'); }
    })();
  };

  const canSelfCheckIn = selectedDate === todayLocal() && (!selfRecord || selfRecord.approvalStatus === 'rejected') && !!selfShift;
  const canSelfCheckOut = selectedDate === todayLocal() && !!selfRecord?.checkIn && !selfRecord?.checkOut;

  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-3xl font-bold">Attendance</h1><p className="mt-1 text-muted-foreground">Shift-based check-in, team records, and reviewed corrections.</p></div>
      <div className="flex flex-wrap items-end gap-2"><div className="space-y-1"><Label htmlFor="attendance-view-date">Attendance date</Label><Input id="attendance-view-date" type="date" value={selectedDate} max={todayLocal()} onChange={(event) => void changeAttendanceDate(event.target.value)}/></div>{canSelfCheckIn && <Button onClick={() => punch('check-in')} disabled={saving}><Clock3 className="mr-2 h-4 w-4" />Check In</Button>}{canSelfCheckOut && <Button onClick={() => punch('check-out')} disabled={saving}><UserCheck className="mr-2 h-4 w-4" />Check Out</Button>}<Button variant="outline" onClick={openSelfRequest}>Request Past Attendance</Button>{canManageTeam && <Button variant="outline" onClick={exportRecords}><Download className="mr-2 h-4 w-4" />Export</Button>}</div>
    </div>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card><CardContent className="flex items-center gap-3 p-5"><CalendarDays className="h-5 w-5 text-primary"/><div><p className="text-sm text-muted-foreground">Present this month</p><p className="text-2xl font-semibold">{stats.present}</p></div></CardContent></Card>
      <Card><CardContent className="flex items-center gap-3 p-5"><X className="h-5 w-5 text-red-600"/><div><p className="text-sm text-muted-foreground">Absent</p><p className="text-2xl font-semibold">{stats.absent}</p></div></CardContent></Card>
      <Card><CardContent className="flex items-center gap-3 p-5"><Users className="h-5 w-5 text-blue-600"/><div><p className="text-sm text-muted-foreground">Leave / exceptions</p><p className="text-2xl font-semibold">{stats.leave}</p></div></CardContent></Card>
      <Card><CardContent className="flex items-center gap-3 p-5"><Clock3 className="h-5 w-5 text-violet-600"/><div><p className="text-sm text-muted-foreground">Recorded hours</p><p className="text-2xl font-semibold">{stats.hours.toFixed(1)}h</p></div></CardContent></Card>
    </div>

    <Card><CardHeader><CardTitle>Shift attendance</CardTitle><CardDescription>{selectedDate}{selfShift ? ` · ${selfShift.name} · ${selfShift.start_time}–${selfShift.end_time}` : ' · No approved shift assigned'}</CardDescription></CardHeader><CardContent>
      {selfRecord ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div><p className="font-medium">{statusBadge(selfRecord)}</p><p className="mt-2 text-sm text-muted-foreground">Check-in {selfRecord.checkIn || '—'} · Check-out {selfRecord.checkOut || '—'} · {selfRecord.workHours.toFixed(2)} hours</p></div>{selfRecord.approvalStatus === 'pending' && <p className="text-sm text-amber-700">Waiting for review</p>}</div>
        : selfShift ? <p className="text-sm text-muted-foreground">Your assigned shift is ready. Check in when your shift begins.</p> : <p className="text-sm text-muted-foreground">An approved shift is required before attendance can be recorded.</p>}
    </CardContent></Card>

    <Tabs defaultValue="mine" className="space-y-4">
      <TabsList><TabsTrigger value="mine">My attendance ({mine.length})</TabsTrigger>{canManageTeam && <TabsTrigger value="team">Team ({roster.length})</TabsTrigger>}{canReview && <TabsTrigger value="approvals">For review ({pending.length})</TabsTrigger>}</TabsList>
      <TabsContent value="mine"><RecordsTable records={mine} statusBadge={statusBadge}/></TabsContent>
      {canManageTeam && <TabsContent value="team"><Card><CardHeader className="flex flex-wrap flex-row items-center justify-between gap-3"><div><CardTitle>Team roster</CardTitle><CardDescription>Employees and their approved shift for the selected date.</CardDescription></div><div className="flex gap-2"><Input className="max-w-xs" placeholder="Search team" value={search} onChange={(event) => setSearch(event.target.value)}/></div></CardHeader><CardContent>
        {filteredRoster.length ? <Table><TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Assigned shift</TableHead><TableHead>Attendance</TableHead><TableHead>Review</TableHead><TableHead>Action</TableHead></TableRow></TableHeader><TableBody>{filteredRoster.map((row) => <TableRow key={row.uid}><TableCell><div className="font-medium">{row.name}</div><div className="text-xs text-muted-foreground">{row.department || row.email}</div></TableCell><TableCell>{row.shift ? <span>{row.shift.name} · {row.shift.start_time}–{row.shift.end_time}</span> : <span className="text-muted-foreground">No approved shift</span>}</TableCell><TableCell>{row.attendance ? statusBadge(row.attendance) : 'Not recorded'}</TableCell><TableCell>{row.attendance?.checkIn || '—'} – {row.attendance?.checkOut || '—'}</TableCell><TableCell>{row.attendance?.isLeaveDerived ? <span className="text-sm text-muted-foreground">From approved leave</span> : row.attendance?.approvalStatus === 'pending' ? <span className="text-sm text-amber-700">Pending review</span> : row.attendance && row.attendance.approvalStatus !== 'rejected' ? <Button size="sm" variant="outline" onClick={() => openCorrection(row, row.attendance!)}><Edit className="mr-1 h-4 w-4"/>Request correction</Button> : <Button size="sm" onClick={() => openManualEntry(row)}>Record</Button>}</TableCell></TableRow>)}</TableBody></Table> : <p className="py-10 text-center text-muted-foreground">No employees in your attendance scope.</p>}
      </CardContent></Card></TabsContent>}
      {canReview && <TabsContent value="approvals"><Card><CardHeader><CardTitle>Attendance requests</CardTitle><CardDescription>Review manual entries and corrections from your authorized reporting level.</CardDescription></CardHeader><CardContent>{pending.length ? <Table><TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Date</TableHead><TableHead>Requested status</TableHead><TableHead>Times</TableHead><TableHead>Reason</TableHead><TableHead>Review</TableHead></TableRow></TableHeader><TableBody>{pending.map((row) => <TableRow key={row.id}><TableCell>{row.userName}</TableCell><TableCell>{row.date}</TableCell><TableCell>{(row.pendingStatus || row.status).replace('-', ' ')}</TableCell><TableCell>{row.pendingCheckIn || row.checkIn || '—'} – {row.pendingCheckOut || row.checkOut || '—'}</TableCell><TableCell>{row.correctionReason || row.pendingNotes || row.notes || '—'}</TableCell><TableCell>{rejectingId === row.id ? <div className="flex min-w-52 gap-2"><Input aria-label="Rejection reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} placeholder="Reason"/><Button size="sm" variant="destructive" onClick={() => review(row, 'reject', rejectionReason)}>Confirm</Button><Button size="icon" variant="ghost" aria-label="Cancel rejection" onClick={() => { setRejectingId(null); setRejectionReason(''); }}><X className="h-4 w-4"/></Button></div> : <div className="flex gap-2"><Button size="sm" onClick={() => review(row, 'approve')}><Check className="mr-1 h-4 w-4"/>Approve</Button><Button size="sm" variant="destructive" onClick={() => { setRejectingId(row.id); setRejectionReason(''); }}><X className="mr-1 h-4 w-4"/>Reject</Button></div>}</TableCell></TableRow>)}</TableBody></Table> : <p className="py-10 text-center text-muted-foreground">No attendance requests to review.</p>}</CardContent></Card></TabsContent>}
    </Tabs>

    <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}><SheetContent className="w-full max-w-lg overflow-y-auto p-6"><SheetHeader className="p-0 pr-8"><SheetTitle>{isSelfRequest ? 'Request past attendance' : editing ? 'Request attendance correction' : 'Record team attendance'}</SheetTitle><SheetDescription>{selectedEmployee?.name} · {isSelfRequest ? selfRequestDate : selectedDate}. {isSelfRequest ? 'Past entries are sent to your reporting hierarchy for review.' : 'Changes are reviewed according to the reporting hierarchy.'}</SheetDescription></SheetHeader>
      <form onSubmit={saveManual} className="mt-6 space-y-5">
        {isSelfRequest ? <div className="space-y-2"><Label>Attendance date</Label><Input type="date" value={selfRequestDate} max={yesterdayLocal()} onChange={(event) => event.target.value && setSelfRequestDate(event.target.value)}/></div> : <div className="space-y-2"><Label>Status</Label><Select value={form.status} onValueChange={(value) => setForm((current) => ({ ...current, status: value }))}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="present">Present</SelectItem><SelectItem value="absent">Absent</SelectItem><SelectItem value="half_day">Half day</SelectItem><SelectItem value="leave">On leave</SelectItem><SelectItem value="holiday">Holiday</SelectItem><SelectItem value="week_off">Week off</SelectItem><SelectItem value="comp_off">Comp off</SelectItem></SelectContent></Select></div>}
        <div className="grid grid-cols-2 gap-3"><div className="space-y-2"><Label>Check-in</Label><Input type="time" value={form.check_in} onChange={(event) => setForm((current) => ({ ...current, check_in: event.target.value }))}/></div><div className="space-y-2"><Label>Check-out</Label><Input type="time" value={form.check_out} onChange={(event) => setForm((current) => ({ ...current, check_out: event.target.value }))}/></div></div>
        <div className="space-y-2"><Label>{isSelfRequest || editing || ['leave', 'holiday', 'week_off', 'comp_off', 'absent'].includes(form.status) ? 'Reason / notes *' : 'Notes'}</Label><textarea required={isSelfRequest || !!editing || ['leave', 'holiday', 'week_off', 'comp_off', 'absent'].includes(form.status)} maxLength={1000} className="min-h-24 w-full rounded-md border bg-transparent px-3 py-2 text-sm" value={form.reason} onChange={(event) => setForm((current) => ({ ...current, reason: event.target.value }))}/></div>
        <Button className="w-full" type="submit" disabled={saving}>{isSelfRequest ? 'Submit past attendance' : editing ? 'Submit correction' : 'Submit attendance'}</Button>
      </form>
    </SheetContent></Sheet>
  </div>;
}

function RecordsTable({ records, statusBadge }: { records: AttendanceRecord[]; statusBadge: (record: AttendanceRecord) => ReactNode }) {
  return <Card><CardHeader><CardTitle>Attendance history</CardTitle><CardDescription>Your records for this month.</CardDescription></CardHeader><CardContent>{records.length ? <Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Status</TableHead><TableHead>Check-in</TableHead><TableHead>Check-out</TableHead><TableHead>Hours</TableHead><TableHead>Review</TableHead></TableRow></TableHeader><TableBody>{records.map((record) => <TableRow key={record.id}><TableCell>{record.date}</TableCell><TableCell>{statusBadge(record)}</TableCell><TableCell>{record.checkIn || '—'}</TableCell><TableCell>{record.checkOut || '—'}</TableCell><TableCell>{record.workHours.toFixed(2)}</TableCell><TableCell>{record.approvalStatus === 'rejected' ? record.reviewReason || 'Rejected' : record.approvalStatus}</TableCell></TableRow>)}</TableBody></Table> : <p className="py-10 text-center text-muted-foreground">No attendance records for this month.</p>}</CardContent></Card>;
}

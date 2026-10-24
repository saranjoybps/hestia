'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { Clock, Edit, Plus, Trash2, Users, Check, X, Eye } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface ShiftTemplate {
  id: string;
  name: string;
  start_time: string;
  end_time: string;
  notes?: string;
}

export interface ShiftAllocation {
  id: string;
  name: string;
  employee_id: string;
  employee_name?: string;
  employee_email?: string;
  shift_type: string;
  shift_template_id?: string | null;
  shift_date?: string | null;
  start_time: string;
  end_time: string;
  notes?: string;
  status: 'pending' | 'approved' | 'rejected';
  created_by?: string;
  created_by_name?: string;
  approved_by_name?: string;
  rejection_reason?: string;
}

export interface ShiftEmployee {
  uid: string;
  name: string;
  email: string;
  role: string;
  department?: string;
}

export interface ShiftPageData {
  role: string;
  templates: ShiftTemplate[];
  allocations: ShiftAllocation[];
  pending: ShiftAllocation[];
  employees: ShiftEmployee[];
  serverFetched: boolean;
}

export default function ShiftsClient({ initialData }: { initialData: ShiftPageData }) {
  const { user, userData } = useAuth();
  const [templates, setTemplates] = useState(initialData.templates);
  const [allocations, setAllocations] = useState(initialData.allocations);
  const [pending, setPending] = useState(initialData.pending);
  const [employees] = useState(initialData.employees);
  const [activeTab, setActiveTab] = useState(initialData.role === 'employee' ? 'mine' : 'allocations');
  const [query, setQuery] = useState('');
  const [templateOpen, setTemplateOpen] = useState(false);
  const [allocationOpen, setAllocationOpen] = useState(false);
  const [viewAllocation, setViewAllocation] = useState<ShiftAllocation | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<ShiftTemplate | null>(null);
  const [editingAllocation, setEditingAllocation] = useState<ShiftAllocation | null>(null);
  const [templateForm, setTemplateForm] = useState({ name: '', start_time: '09:00', end_time: '17:00', notes: '' });
  const [allocationForm, setAllocationForm] = useState({ employee_id: '', shift_template_id: '', notes: '' });
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [saving, setSaving] = useState(false);
  const skipInitialFetch = useRef(initialData.serverFetched);

  const role = userData?.role || initialData.role;
  const canManageTemplates = ['hr', 'director', 'super_admin'].includes(role);
  const canAllocate = ['lead', 'manager', 'hr', 'director', 'super_admin'].includes(role);
  const canApprove = ['manager', 'director', 'super_admin'].includes(role);
  const myAllocations = allocations.filter((item) => item.employee_id === userData?.uid);

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

  const refresh = async () => {
    const requests: Promise<any>[] = [apiRequest('/shifts')];
    if (canAllocate) requests.push(apiRequest('/shift-templates'));
    if (canApprove) requests.push(apiRequest('/shifts/pending-approvals'));
    const [shiftData, templateData, pendingData] = await Promise.all(requests);
    setAllocations(shiftData.shifts || []);
    if (canAllocate) setTemplates(templateData?.templates || []);
    if (canApprove) setPending(pendingData?.shifts || []);
  };

  useEffect(() => {
    if (!user) return;
    if (skipInitialFetch.current) {
      skipInitialFetch.current = false;
      return;
    }
    refresh().catch((error) => toast.error(error.message));
  // Initial data is server-prefetched; refresh is used after writes and role changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, role]);

  const openCreateTemplate = () => {
    setEditingTemplate(null);
    setTemplateForm({ name: '', start_time: '09:00', end_time: '17:00', notes: '' });
    setTemplateOpen(true);
  };

  const openEditTemplate = (template: ShiftTemplate) => {
    setEditingTemplate(template);
    setTemplateForm({ name: template.name, start_time: template.start_time, end_time: template.end_time, notes: template.notes || '' });
    setTemplateOpen(true);
  };

  const saveTemplate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!templateForm.name.trim()) {
      toast.error('Enter a shift name');
      return;
    }
    if (templateForm.start_time === templateForm.end_time) {
      toast.error('Start and end times must be different');
      return;
    }
    setSaving(true);
    try {
      const path = editingTemplate ? `/shift-templates/${editingTemplate.id}` : '/shift-templates';
      const result = await apiRequest(path, { method: editingTemplate ? 'PATCH' : 'POST', body: JSON.stringify(templateForm) });
      setTemplates((current) => editingTemplate ? current.map((item) => item.id === result.id ? result : item) : [...current, result]);
      setTemplateOpen(false);
      toast.success(editingTemplate ? 'Shift updated' : 'Shift created');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save shift');
    } finally {
      setSaving(false);
    }
  };

  const deleteTemplate = async (template: ShiftTemplate) => {
    if (!window.confirm(`Delete the ${template.name} shift template?`)) return;
    try {
      await apiRequest(`/shift-templates/${template.id}`, { method: 'DELETE' });
      setTemplates((current) => current.filter((item) => item.id !== template.id));
      toast.success('Shift deleted');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to delete shift');
    }
  };

  const openCreateAllocation = () => {
    setEditingAllocation(null);
    setAllocationForm({ employee_id: '', shift_template_id: '', notes: '' });
    setAllocationOpen(true);
  };

  const openEditAllocation = (allocation: ShiftAllocation) => {
    const template = templates.find((item) => item.id === allocation.shift_template_id)
      || templates.find((item) => item.name === allocation.shift_type || item.name === allocation.name);
    setEditingAllocation(allocation);
    setAllocationForm({ employee_id: allocation.employee_id, shift_template_id: template?.id || '', notes: allocation.notes || '' });
    setAllocationOpen(true);
  };

  const saveAllocation = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const path = editingAllocation ? `/shifts/${editingAllocation.id}` : '/shifts';
      const result = await apiRequest(path, { method: editingAllocation ? 'PATCH' : 'POST', body: JSON.stringify(allocationForm) });
      setAllocations((current) => editingAllocation ? current.map((item) => item.id === result.id ? result : item) : [result, ...current]);
      setPending((current) => result.status === 'pending' && !current.some((item) => item.id === result.id) ? [result, ...current] : current.filter((item) => item.id !== result.id));
      setAllocationOpen(false);
      toast.success(result.status === 'pending' ? 'Allocation submitted for approval' : 'Shift allocated');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to allocate shift');
    } finally {
      setSaving(false);
    }
  };

  const deleteAllocation = async (allocation: ShiftAllocation) => {
    if (!window.confirm(`Remove ${allocation.shift_type} from ${allocation.employee_name}?`)) return;
    try {
      await apiRequest(`/shifts/${allocation.id}`, { method: 'DELETE' });
      setAllocations((current) => current.filter((item) => item.id !== allocation.id));
      setPending((current) => current.filter((item) => item.id !== allocation.id));
      toast.success('Allocation removed');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to remove allocation');
    }
  };

  const approveAllocation = async (allocation: ShiftAllocation) => {
    try {
      const result = await apiRequest(`/shifts/${allocation.id}/approve`, { method: 'PATCH' });
      setPending((current) => current.filter((item) => item.id !== allocation.id));
      setAllocations((current) => current.map((item) => item.id === allocation.id ? result : item));
      toast.success('Allocation approved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to approve allocation');
    }
  };

  const rejectAllocation = async (allocation: ShiftAllocation) => {
    if (!rejectionReason.trim()) {
      toast.error('Enter a reason for rejection');
      return;
    }
    try {
      const result = await apiRequest(`/shifts/${allocation.id}/reject`, { method: 'PATCH', body: JSON.stringify({ rejection_reason: rejectionReason }) });
      setPending((current) => current.filter((item) => item.id !== allocation.id));
      setAllocations((current) => current.map((item) => item.id === allocation.id ? result : item));
      setRejectingId(null);
      setRejectionReason('');
      toast.success('Allocation rejected');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to reject allocation');
    }
  };

  const statusBadge = (status: ShiftAllocation['status']) => {
    const styles = { pending: 'bg-amber-100 text-amber-800', approved: 'bg-green-100 text-green-800', rejected: 'bg-red-100 text-red-800' };
    return <Badge className={styles[status]}>{status}</Badge>;
  };

  const visibleAllocations = allocations.filter((allocation) => {
    const value = `${allocation.employee_name || ''} ${allocation.employee_email || ''} ${allocation.shift_type}`.toLowerCase();
    return value.includes(query.toLowerCase());
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Shift Management</h1>
          <p className="mt-1 text-muted-foreground">Define reusable shifts and assign them to employees.</p>
        </div>
        <div className="flex gap-2">
          {canManageTemplates && <Button variant="outline" onClick={openCreateTemplate}><Plus className="mr-2 h-4 w-4" />Create Shift</Button>}
          {canAllocate && <Button onClick={openCreateAllocation}><Users className="mr-2 h-4 w-4" />Allocate Shift</Button>}
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {canAllocate && <TabsTrigger value="allocations">Allocations ({allocations.length})</TabsTrigger>}
          {canManageTemplates && <TabsTrigger value="templates">Shift Types ({templates.length})</TabsTrigger>}
          {canApprove && <TabsTrigger value="approvals">Pending Approvals ({pending.length})</TabsTrigger>}
          <TabsTrigger value="mine">My Shift ({myAllocations.length})</TabsTrigger>
        </TabsList>

        {canAllocate && <TabsContent value="allocations">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle>Employee Allocations</CardTitle>
              <Input className="max-w-xs" placeholder="Search employee or shift" value={query} onChange={(event) => setQuery(event.target.value)} />
            </CardHeader>
            <CardContent>
              {visibleAllocations.length ? <Table>
                <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Shift</TableHead><TableHead>Hours</TableHead><TableHead>Status</TableHead><TableHead>Notes</TableHead><TableHead>Actions</TableHead></TableRow></TableHeader>
                <TableBody>{visibleAllocations.map((allocation) => <TableRow key={allocation.id}>
                  <TableCell><div className="font-medium">{allocation.employee_name}</div><div className="text-xs text-muted-foreground">{allocation.employee_email}</div></TableCell>
                  <TableCell>{allocation.shift_type}</TableCell>
                  <TableCell>{allocation.start_time}–{allocation.end_time}</TableCell>
                  <TableCell>{statusBadge(allocation.status)}</TableCell>
                  <TableCell className="max-w-xs truncate">{allocation.notes || '—'}</TableCell>
                  <TableCell><div className="flex gap-1">
                    <Button size="icon" variant="ghost" aria-label="View allocation" onClick={() => setViewAllocation(allocation)}><Eye className="h-4 w-4" /></Button>
                    {(canManageTemplates || (allocation.created_by === userData?.uid && allocation.status === 'pending')) && <Button size="icon" variant="ghost" aria-label="Edit allocation" onClick={() => openEditAllocation(allocation)}><Edit className="h-4 w-4" /></Button>}
                    {(canManageTemplates || (allocation.created_by === userData?.uid && allocation.status === 'pending')) && <Button size="icon" variant="ghost" aria-label="Delete allocation" onClick={() => deleteAllocation(allocation)}><Trash2 className="h-4 w-4 text-red-600" /></Button>}
                  </div></TableCell>
                </TableRow>)}</TableBody>
              </Table> : <p className="py-12 text-center text-muted-foreground">No shift allocations found.</p>}
            </CardContent>
          </Card>
        </TabsContent>}

        {canManageTemplates && <TabsContent value="templates">
          <Card><CardHeader><CardTitle>Shift Types</CardTitle></CardHeader><CardContent>
            {templates.length ? <Table>
              <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Start</TableHead><TableHead>End</TableHead><TableHead>Notes</TableHead><TableHead>Actions</TableHead></TableRow></TableHeader>
              <TableBody>{templates.map((template) => <TableRow key={template.id}>
                <TableCell className="font-medium">{template.name}</TableCell><TableCell>{template.start_time}</TableCell><TableCell>{template.end_time}</TableCell><TableCell>{template.notes || '—'}</TableCell>
                <TableCell><div className="flex gap-1"><Button size="icon" variant="ghost" aria-label="Edit shift" onClick={() => openEditTemplate(template)}><Edit className="h-4 w-4" /></Button><Button size="icon" variant="ghost" aria-label="Delete shift" onClick={() => deleteTemplate(template)}><Trash2 className="h-4 w-4 text-red-600" /></Button></div></TableCell>
              </TableRow>)}</TableBody>
            </Table> : <p className="py-12 text-center text-muted-foreground">No shifts defined yet.</p>}
          </CardContent></Card>
        </TabsContent>}

        {canApprove && <TabsContent value="approvals">
          <Card><CardHeader><CardTitle>Pending Allocations</CardTitle></CardHeader><CardContent>
            {pending.length ? <Table>
              <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Shift</TableHead><TableHead>Hours</TableHead><TableHead>Requested By</TableHead><TableHead>Notes</TableHead><TableHead>Review</TableHead></TableRow></TableHeader>
              <TableBody>{pending.map((allocation) => <TableRow key={allocation.id}>
                <TableCell><div className="font-medium">{allocation.employee_name}</div><div className="text-xs text-muted-foreground">{allocation.employee_email}</div></TableCell>
                <TableCell>{allocation.shift_type}</TableCell><TableCell>{allocation.start_time}–{allocation.end_time}</TableCell><TableCell>{allocation.created_by_name}</TableCell><TableCell>{allocation.notes || '—'}</TableCell>
                <TableCell><div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" onClick={() => approveAllocation(allocation)}><Check className="mr-1 h-4 w-4" />Approve</Button>
                  {rejectingId === allocation.id ? <><Input className="w-40" placeholder="Reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} /><Button size="sm" variant="destructive" onClick={() => rejectAllocation(allocation)}>Confirm</Button><Button size="icon" variant="ghost" onClick={() => { setRejectingId(null); setRejectionReason(''); }}><X className="h-4 w-4" /></Button></> : <Button size="sm" variant="outline" onClick={() => setRejectingId(allocation.id)}>Reject</Button>}
                </div></TableCell>
              </TableRow>)}</TableBody>
            </Table> : <p className="py-12 text-center text-muted-foreground">No pending shift approvals.</p>}
          </CardContent></Card>
        </TabsContent>}

        <TabsContent value="mine">
          <Card><CardHeader><CardTitle>My Shift Assignment</CardTitle></CardHeader><CardContent>
            {myAllocations.length ? <div className="space-y-4">{myAllocations.map((allocation) => <div key={allocation.id} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{allocation.shift_type}</h3><p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground"><Clock className="h-4 w-4" />{allocation.start_time}–{allocation.end_time}</p></div>{statusBadge(allocation.status)}</div>
              {allocation.notes && <><Separator className="my-3" /><p className="text-sm">{allocation.notes}</p></>}
              <p className="mt-3 text-xs text-muted-foreground">Assigned by {allocation.created_by_name || '—'}</p>
            </div>)}</div> : <p className="py-12 text-center text-muted-foreground">No shift assigned to you.</p>}
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      <Sheet open={templateOpen} onOpenChange={setTemplateOpen}><SheetContent className="w-full max-w-lg overflow-y-auto p-6">
        <SheetHeader className="p-0 pr-8"><SheetTitle>{editingTemplate ? 'Edit Shift' : 'Create Shift'}</SheetTitle><SheetDescription>Set a reusable shift name and its daily hours.</SheetDescription></SheetHeader>
        <form className="mt-6 space-y-5" onSubmit={saveTemplate}>
          <div className="space-y-2"><Label htmlFor="shift-name">Shift name *</Label><Input id="shift-name" required minLength={2} maxLength={80} value={templateForm.name} onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3"><div className="space-y-2"><Label htmlFor="shift-start">Start time *</Label><Input id="shift-start" type="time" required value={templateForm.start_time} onChange={(e) => setTemplateForm({ ...templateForm, start_time: e.target.value })} /></div><div className="space-y-2"><Label htmlFor="shift-end">End time *</Label><Input id="shift-end" type="time" required value={templateForm.end_time} onChange={(e) => setTemplateForm({ ...templateForm, end_time: e.target.value })} /></div></div>
          <div className="space-y-2"><Label htmlFor="shift-notes">Notes</Label><textarea id="shift-notes" maxLength={1000} className="min-h-24 w-full rounded-md border bg-transparent px-3 py-2 text-sm" value={templateForm.notes} onChange={(e) => setTemplateForm({ ...templateForm, notes: e.target.value })} /></div>
          <Button type="submit" disabled={saving} className="w-full">{editingTemplate ? 'Save Shift' : 'Create Shift'}</Button>
        </form>
      </SheetContent></Sheet>

      <Sheet open={allocationOpen} onOpenChange={setAllocationOpen}><SheetContent className="w-full max-w-lg overflow-y-auto p-6">
        <SheetHeader className="p-0 pr-8"><SheetTitle>{editingAllocation ? 'Edit Allocation' : 'Allocate Shift'}</SheetTitle><SheetDescription>Choose an employee and a saved shift. The assignment applies to attendance after approval.</SheetDescription></SheetHeader>
        <form className="mt-6 space-y-5" onSubmit={saveAllocation}>
          <div className="space-y-2"><Label>Employee *</Label><Select required value={allocationForm.employee_id} onValueChange={(value) => setAllocationForm({ ...allocationForm, employee_id: value })}><SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger><SelectContent>{employees.map((employee) => <SelectItem key={employee.uid} value={employee.uid}>{employee.name} — {employee.department || employee.email}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-2"><Label>Shift *</Label><Select required value={allocationForm.shift_template_id} onValueChange={(value) => setAllocationForm({ ...allocationForm, shift_template_id: value })}><SelectTrigger><SelectValue placeholder="Select shift" /></SelectTrigger><SelectContent>{templates.map((template) => <SelectItem key={template.id} value={template.id}>{template.name} ({template.start_time}–{template.end_time})</SelectItem>)}</SelectContent></Select></div>
          {templates.length === 0 && <p className="text-sm text-muted-foreground">A shift type must be created by HR or a director before it can be allocated.</p>}
          <div className="space-y-2"><Label htmlFor="allocation-notes">Notes</Label><textarea id="allocation-notes" maxLength={1000} className="min-h-24 w-full rounded-md border bg-transparent px-3 py-2 text-sm" value={allocationForm.notes} onChange={(e) => setAllocationForm({ ...allocationForm, notes: e.target.value })} /></div>
          <Button type="submit" disabled={saving || employees.length === 0 || templates.length === 0} className="w-full">{editingAllocation ? 'Save Allocation' : 'Submit Allocation'}</Button>
        </form>
      </SheetContent></Sheet>

      <Sheet open={!!viewAllocation} onOpenChange={(open) => !open && setViewAllocation(null)}><SheetContent className="w-full max-w-lg overflow-y-auto p-6">
        <SheetHeader className="p-0 pr-8"><SheetTitle>Shift Allocation</SheetTitle><SheetDescription>Assignment details and approval state.</SheetDescription></SheetHeader>
        {viewAllocation && <div className="mt-6 space-y-4"><div><p className="text-sm text-muted-foreground">Employee</p><p className="font-medium">{viewAllocation.employee_name} · {viewAllocation.employee_email}</p></div><div><p className="text-sm text-muted-foreground">Shift</p><p className="font-medium">{viewAllocation.shift_type} · {viewAllocation.start_time}–{viewAllocation.end_time}</p></div><div><p className="text-sm text-muted-foreground">Status</p>{statusBadge(viewAllocation.status)}</div><div><p className="text-sm text-muted-foreground">Notes</p><p>{viewAllocation.notes || '—'}</p></div>{viewAllocation.rejection_reason && <div><p className="text-sm text-muted-foreground">Rejection reason</p><p>{viewAllocation.rejection_reason}</p></div>}</div>}
      </SheetContent></Sheet>
    </div>
  );
}

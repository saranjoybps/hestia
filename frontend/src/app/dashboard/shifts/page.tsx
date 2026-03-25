'use client';

import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Clock,
  Plus,
  Edit,
  Eye,
  Trash2,
  Calendar,
  Users,
  CheckCircle,
  XCircle
} from 'lucide-react';

interface Shift {
  id: string;
  employee_id: string;
  employee_name?: string;
  employee_email?: string;
  shift_type: 'morning' | 'afternoon' | 'evening' | 'night' | 'rotating';
  shift_date: string;
  start_time: string;
  end_time: string;
  notes?: string;
  status: 'pending' | 'approved' | 'rejected';
  created_by: string;
  created_by_name?: string;
  approved_by?: string;
  approved_by_name?: string;
  rejection_reason?: string;
  created_at: string;
  updated_at?: string;
}

interface Employee {
  uid: string;
  name: string;
  email: string;
  role: string;
  department: string;
}

interface ShiftFormData {
  employee_id: string;
  shift_type: 'morning' | 'afternoon' | 'evening' | 'night' | 'rotating';
  shift_date: string;
  start_time: string;
  end_time: string;
  notes: string;
}

export default function ShiftsPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [myShifts, setMyShifts] = useState<Shift[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Shift[]>([]);
  const [reportees, setReportees] = useState<Employee[]>([]);

  // filters for all shifts
  const [filterStartDate, setFilterStartDate] = useState<string>('');
  const [filterEndDate, setFilterEndDate] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'approved' | 'pending' | 'rejected'>('all');

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showBulkDialog, setShowBulkDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [editingShift, setEditingShift] = useState<Shift | null>(null);
  const [viewingShift, setViewingShift] = useState<Shift | null>(null);

  // Form data
  const [formData, setFormData] = useState<ShiftFormData>({
    employee_id: '',
    shift_type: 'morning',
    shift_date: new Date().toISOString().split('T')[0],
    start_time: '09:00',
    end_time: '17:00',
    notes: '',
  });

  // Bulk allocation data
  const [bulkFormData, setBulkFormData] = useState({
    employee_id: '',
    shift_type: 'morning' as 'morning' | 'afternoon' | 'evening' | 'night' | 'rotating',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(new Date().setMonth(new Date().getMonth() + 1)).toISOString().split('T')[0],
    start_time: '09:00',
    end_time: '17:00',
    notes: '',
    weekoff_days: [] as number[], // 0=Sunday, 1=Monday, ..., 6=Saturday
  });

  // Permissions
  const role = userData?.role;
  const isLead = role === 'lead';
  const isManager = role === 'manager';
  const isDirector = role === 'director';
  const isHR = role === 'hr';
  const isSuperAdmin = role === 'super_admin';

  const canCreateShift = isLead || isManager || isDirector || isHR || isSuperAdmin;
  const canApprove = isManager || isDirector || isSuperAdmin;

  useEffect(() => {
    if (user) {
      fetchShifts();
      if (canCreateShift) {
        fetchReportees();
      }
      if (canApprove) {
        fetchPendingApprovals();
      }
    }
  }, [user]);

  const fetchReportees = async () => {
    try {
      const token = await user?.getIdToken();
      if (!token || !userData?.uid) return;

      // For managers/directors/superadmins: load everyone (minus self)
      if (isManager || isDirector || isSuperAdmin) {
        const response = await fetch(`${API_BASE_URL}/users?limit=500`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          const users: Employee[] = data.users || data;
          setReportees(users.filter((u) => u.uid !== userData.uid));
        }
        return;
      }

      // For leads/HR: load full downstream reporting tree only
      const fetchReporteesFor = async (uid: string) => {
        try {
          const res = await fetch(`${API_BASE_URL}/users/${uid}/reportees`, {
            headers: { 'Authorization': `Bearer ${token}` },
          });
          if (!res.ok) return [];
          return await res.json();
        } catch (err) {
          console.error(`Error fetching reportees for ${uid}:`, err);
          return [];
        }
      };

      const all: Employee[] = [];
      const visited = new Set<string>();
      const queue: string[] = [userData.uid];

      while (queue.length > 0) {
        const current = queue.shift();
        if (!current || visited.has(current)) continue;
        visited.add(current);

        const children: Employee[] = await fetchReporteesFor(current);
        children.forEach((emp) => {
          if (!visited.has(emp.uid)) {
            all.push(emp);
            queue.push(emp.uid);
          }
        });
      }

      setReportees(all);
    } catch (error) {
      console.error('Error fetching reportees:', error);
    }
  };

  const fetchShifts = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/shifts`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        const shiftsList = data.shifts || [];

        if (userData?.role === 'employee') {
          setMyShifts(shiftsList);
        } else {
          setShifts(shiftsList);
        }
      }
    } catch (error) {
      console.error('Error fetching shifts:', error);
      toast.error('Failed to fetch shifts');
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/shifts/pending-approvals`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setPendingApprovals(data.shifts || []);
      }
    } catch (error) {
      console.error('Error fetching pending approvals:', error);
    }
  };

  const handleCreateShift = async () => {
    if (!formData.employee_id || !formData.shift_date || !formData.start_time || !formData.end_time) {
      toast.error('Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/shifts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create shift');
      }

      toast.success('Shift created successfully! Pending approval.');
      setShowCreateDialog(false);
      resetForm();
      fetchShifts();
      if (canApprove) {
        fetchPendingApprovals();
      }
    } catch (error) {
      console.error('Create shift error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create shift');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkCreateShifts = async () => {
    if (!bulkFormData.employee_id || !bulkFormData.start_date || !bulkFormData.end_date) {
      toast.error('Please fill in all required fields');
      return;
    }

    const startDate = new Date(bulkFormData.start_date);
    const endDate = new Date(bulkFormData.end_date);

    if (startDate > endDate) {
      toast.error('End date must be after start date');
      return;
    }

    // Calculate number of days
    const daysDiff = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff > 31) {
      toast.error('Cannot allocate shifts for more than 31 days at once');
      return;
    }

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const shiftsToCreate = [];

      // Generate shifts for each day in the range
      const currentDate = new Date(startDate);
      while (currentDate <= endDate) {
        const dayOfWeek = currentDate.getDay();

        // Skip if this day is marked as a weekoff
        if (bulkFormData.weekoff_days.includes(dayOfWeek)) {
          currentDate.setDate(currentDate.getDate() + 1);
          continue;
        }

        shiftsToCreate.push({
          employee_id: bulkFormData.employee_id,
          shift_type: bulkFormData.shift_type,
          shift_date: currentDate.toISOString().split('T')[0],
          start_time: bulkFormData.start_time,
          end_time: bulkFormData.end_time,
          notes: bulkFormData.notes,
        });

        currentDate.setDate(currentDate.getDate() + 1);
      }

      // Create all shifts
      let successCount = 0;
      let failCount = 0;

      for (const shiftData of shiftsToCreate) {
        try {
          const response = await fetch(`${API_BASE_URL}/shifts`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(shiftData),
          });

          if (response.ok) {
            successCount++;
          } else {
            failCount++;
          }
        } catch (error) {
          failCount++;
        }
      }

      if (successCount > 0) {
        toast.success(`Successfully created ${successCount} shift(s)${failCount > 0 ? `, ${failCount} failed` : ''}. Pending approval.`);
      } else {
        toast.error('Failed to create shifts');
      }

      setShowBulkDialog(false);
      resetBulkForm();
      fetchShifts();
      if (canApprove) {
        fetchPendingApprovals();
      }
    } catch (error) {
      console.error('Bulk create shifts error:', error);
      toast.error('Failed to create bulk shifts');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateShift = async () => {
    if (!editingShift) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/shifts/${editingShift.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update shift');
      }

      toast.success('Shift updated successfully!');
      setShowEditDialog(false);
      setEditingShift(null);
      resetForm();
      fetchShifts();
    } catch (error) {
      console.error('Update shift error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update shift');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveShift = async (shiftId: string) => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/shifts/${shiftId}/approve`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve shift');
      }

      toast.success('Shift approved successfully!');
      fetchPendingApprovals();
      fetchShifts();
    } catch (error) {
      console.error('Approve shift error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to approve shift');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectShift = async (shiftId: string, reason: string) => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/shifts/${shiftId}/reject`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ rejection_reason: reason }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reject shift');
      }

      toast.success('Shift rejected.');
      fetchPendingApprovals();
      fetchShifts();
    } catch (error) {
      console.error('Reject shift error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reject shift');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteShift = async (shiftId: string) => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/shifts/${shiftId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete shift');
      }

      toast.success('Shift deleted successfully!');
      fetchShifts();
    } catch (error) {
      console.error('Delete shift error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete shift');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      employee_id: '',
      shift_type: 'morning',
      shift_date: new Date().toISOString().split('T')[0],
      start_time: '09:00',
      end_time: '17:00',
      notes: '',
    });
  };

  const resetBulkForm = () => {
    setBulkFormData({
      employee_id: '',
      shift_type: 'morning',
      start_date: new Date().toISOString().split('T')[0],
      end_date: new Date(new Date().setMonth(new Date().getMonth() + 1)).toISOString().split('T')[0],
      start_time: '09:00',
      end_time: '17:00',
      notes: '',
      weekoff_days: [],
    });
  };

  const openEditDialog = (shift: Shift) => {
    setEditingShift(shift);
    setFormData({
      employee_id: shift.employee_id,
      shift_type: shift.shift_type,
      shift_date: shift.shift_date,
      start_time: shift.start_time,
      end_time: shift.end_time,
      notes: shift.notes || '',
    });
    setShowEditDialog(true);
  };

  const openViewDialog = (shift: Shift) => {
    setViewingShift(shift);
    setShowViewDialog(true);
  };

  const getShiftTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      morning: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      afternoon: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      evening: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      night: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
      rotating: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
    };

    return <Badge className={colors[type] || ''}>{type.charAt(0).toUpperCase() + type.slice(1)}</Badge>;
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      approved: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    };

    return <Badge className={colors[status] || ''}>{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Shift Management</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage and allocate employee shifts
          </p>
        </div>
        {canCreateShift && (
          <div className="flex gap-2">
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Shift
            </Button>
            <Button onClick={() => setShowBulkDialog(true)} variant="outline">
              <Calendar className="h-4 w-4 mr-2" />
              Bulk Allocate
            </Button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue={userData?.role === 'employee' ? 'my-shifts' : 'all-shifts'} onValueChange={(value) => {
        if (value === 'pending' && canApprove) {
          fetchPendingApprovals();
        } else if (value === 'all-shifts') {
          fetchShifts();
        } else if (value === 'my-shifts') {
          fetchShifts();
        }
      }} className="space-y-4">
        <TabsList>
          {userData?.role === 'employee' ? (
            <TabsTrigger value="my-shifts">My Shifts</TabsTrigger>
          ) : (
            <>
              <TabsTrigger value="all-shifts">All Shifts ({shifts.length})</TabsTrigger>
              {canApprove && (
                <TabsTrigger value="pending">Pending Approvals ({pendingApprovals.length})</TabsTrigger>
              )}
            </>
          )}
        </TabsList>

        {/* All Shifts Tab */}
        {userData?.role !== 'employee' && (
          <TabsContent value="all-shifts" className="space-y-4">
            <Card>
              <CardContent>
                <div className="flex flex-wrap gap-4 mb-4">
                  <div>
                    <Label htmlFor="start-date" className="text-sm">Start Date</Label>
                    <Input
                      id="start-date"
                      type="date"
                      value={filterStartDate}
                      onChange={(e) => setFilterStartDate(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="end-date" className="text-sm">End Date</Label>
                    <Input
                      id="end-date"
                      type="date"
                      value={filterEndDate}
                      onChange={(e) => setFilterEndDate(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="status-filter" className="text-sm">Status</Label>
                    <Select
                      value={filterStatus}
                      onValueChange={(v) => setFilterStatus(v as any)}
                    >
                      <SelectTrigger id="status-filter" className="w-40">
                        <SelectValue placeholder="All" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="approved">Approved</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="rejected">Rejected</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {shifts.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created By</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {shifts
                        .filter((shift) => {
                          if (filterStatus !== 'all' && shift.status !== filterStatus) {
                            return false;
                          }
                          if (filterStartDate && shift.shift_date < filterStartDate) {
                            return false;
                          }
                          if (filterEndDate && shift.shift_date > filterEndDate) {
                            return false;
                          }
                          return true;
                        })
                        .map((shift) => (
                          <TableRow key={shift.id}>
                            <TableCell>
                              <div>
                                <div className="font-medium">{shift.employee_name}</div>
                                <div className="text-sm text-gray-500">{shift.employee_email}</div>
                              </div>
                            </TableCell>
                            <TableCell>
                              {new Date(shift.shift_date).toLocaleDateString()}
                            </TableCell>
                            <TableCell>{getShiftTypeBadge(shift.shift_type)}</TableCell>
                            <TableCell>
                              <div className="text-sm">
                                {shift.start_time} - {shift.end_time}
                              </div>
                            </TableCell>
                            <TableCell>{getStatusBadge(shift.status)}</TableCell>
                            <TableCell>
                              <div className="text-sm">{shift.created_by_name || 'Unknown'}</div>
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => openViewDialog(shift)}
                                  aria-label="View shift"
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                                {shift.created_by === userData?.uid && (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => openEditDialog(shift)}
                                      aria-label="Edit shift"
                                    >
                                      <Edit className="h-4 w-4" />
                                    </Button>
                                    {shift.status === 'pending' && (
                                      <AlertDialog>
                                        <AlertDialogTrigger asChild>
                                          <Button size="sm" variant="outline" className="text-red-600" aria-label="Delete shift">
                                            <Trash2 className="h-4 w-4" />
                                          </Button>
                                        </AlertDialogTrigger>
                                        <AlertDialogContent>
                                          <AlertDialogHeader>
                                            <AlertDialogTitle>Delete Shift</AlertDialogTitle>
                                            <AlertDialogDescription>
                                              Are you sure you want to delete this shift allocation?
                                            </AlertDialogDescription>
                                          </AlertDialogHeader>
                                          <AlertDialogFooter>
                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                            <AlertDialogAction
                                              className="bg-red-600 hover:bg-red-700"
                                              onClick={() => handleDeleteShift(shift.id)}
                                            >
                                              Delete
                                            </AlertDialogAction>
                                          </AlertDialogFooter>
                                        </AlertDialogContent>
                                      </AlertDialog>
                                    )}
                                  </>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12">
                    <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">No shifts created yet</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* My Shifts Tab */}
        {userData?.role === 'employee' && (
          <TabsContent value="my-shifts" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>My Shifts</CardTitle>
                <CardDescription>View your assigned shifts</CardDescription>
              </CardHeader>
              <CardContent>
                {myShifts.length > 0 ? (
                  <div className="space-y-4">
                    {myShifts.map((shift) => (
                      <Card key={shift.id} className="border">
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <div className="flex gap-2 items-center mb-2">
                                <Calendar className="h-4 w-4 text-gray-500" />
                                <span className="font-semibold">
                                  {new Date(shift.shift_date).toLocaleDateString('en-US', {
                                    weekday: 'long',
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric'
                                  })}
                                </span>
                              </div>
                              <div className="flex gap-2 items-center text-sm text-gray-600 dark:text-gray-400">
                                <Clock className="h-4 w-4" />
                                <span>{shift.start_time} - {shift.end_time}</span>
                              </div>
                            </div>
                            <div className="text-right space-y-2">
                              {getShiftTypeBadge(shift.shift_type)}
                              {getStatusBadge(shift.status)}
                            </div>
                          </div>

                          {shift.notes && (
                            <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800 rounded">
                              <p className="text-sm text-gray-700 dark:text-gray-300">{shift.notes}</p>
                            </div>
                          )}

                          {shift.status === 'rejected' && shift.rejection_reason && (
                            <div className="mt-4 p-3 bg-red-50 dark:bg-red-950 rounded">
                              <p className="text-sm font-medium text-red-700 dark:text-red-300">Rejection Reason:</p>
                              <p className="text-sm text-red-600 dark:text-red-400 mt-1">{shift.rejection_reason}</p>
                            </div>
                          )}

                          <Separator className="my-4" />

                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            Assigned by: {shift.created_by_name || 'Unknown'}
                            {shift.approved_by_name && ` • ${shift.status === 'approved' ? 'Approved' : 'Rejected'} by: ${shift.approved_by_name}`}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">No shifts assigned yet</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Pending Approvals Tab */}
        {canApprove && (
          <TabsContent value="pending" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending Shift Approvals</CardTitle>
                <CardDescription>Review and approve shift allocations</CardDescription>
              </CardHeader>
              <CardContent>
                {pendingApprovals.length > 0 ? (
                  <div className="space-y-4">
                    {pendingApprovals.map((shift) => (
                      <Card key={shift.id} className="border border-yellow-200 dark:border-yellow-800">
                        <CardContent className="pt-6">
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-semibold text-lg">{shift.employee_name}</h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{shift.employee_email}</p>
                                <div className="mt-2 flex gap-2">
                                  {getShiftTypeBadge(shift.shift_type)}
                                </div>
                              </div>
                              {getStatusBadge(shift.status)}
                            </div>

                            <Separator />

                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Date:</span>
                                <p className="font-medium">{new Date(shift.shift_date).toLocaleDateString()}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Time:</span>
                                <p className="font-medium">{shift.start_time} - {shift.end_time}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Created By:</span>
                                <p className="font-medium">{shift.created_by_name || 'Unknown'}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Created:</span>
                                <p className="font-medium">{new Date(shift.created_at).toLocaleDateString()}</p>
                              </div>
                            </div>

                            {shift.notes && (
                              <div className="text-sm">
                                <span className="text-gray-500 dark:text-gray-400">Notes:</span>
                                <p className="mt-1 text-gray-700 dark:text-gray-300">{shift.notes}</p>
                              </div>
                            )}

                            <div className="flex gap-2 pt-2">
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button className="flex-1 bg-green-600 hover:bg-green-700" disabled={loading}>
                                    <CheckCircle className="h-4 w-4 mr-2" />
                                    Approve
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Approve Shift</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      Approve this shift allocation for {shift.employee_name} on {new Date(shift.shift_date).toLocaleDateString()}?
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      className="bg-green-600 hover:bg-green-700"
                                      onClick={() => handleApproveShift(shift.id)}
                                    >
                                      Approve Shift
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>

                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="outline" className="flex-1 border-red-500 text-red-600 hover:bg-red-50 dark:hover:bg-red-950" disabled={loading}>
                                    <XCircle className="h-4 w-4 mr-2" />
                                    Reject
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Reject Shift</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      Please provide a reason for rejecting this shift allocation.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <div className="py-4">
                                    <Label htmlFor={`rejection-reason-${shift.id}`}>Rejection Reason *</Label>
                                    <Input
                                      id={`rejection-reason-${shift.id}`}
                                      placeholder="Enter reason for rejection..."
                                      className="mt-2"
                                    />
                                  </div>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      className="bg-red-600 hover:bg-red-700"
                                      onClick={() => {
                                        const reason = (document.getElementById(`rejection-reason-${shift.id}`) as HTMLInputElement)?.value;
                                        if (reason?.trim()) {
                                          handleRejectShift(shift.id, reason);
                                        } else {
                                          toast.error('Please provide a rejection reason');
                                        }
                                      }}
                                    >
                                      Reject Shift
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">No pending shift approvals</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Create Shift Dialog */}
      <Sheet open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Create New Shift</SheetTitle>
              <SheetDescription className="mt-1">
                Allocate a shift to an employee. It will require manager/director approval.
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="employee">Employee *</Label>
              <Select value={formData.employee_id} onValueChange={(value) => setFormData({ ...formData, employee_id: value })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select employee" />
                </SelectTrigger>
                <SelectContent>
                  {reportees.map((employee) => (
                    <SelectItem key={employee.uid} value={employee.uid}>
                      {employee.name} - {employee.department}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="shift_type">Shift Type *</Label>
                <Select value={formData.shift_type} onValueChange={(value: any) => setFormData({ ...formData, shift_type: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="morning">Morning</SelectItem>
                    <SelectItem value="afternoon">Afternoon</SelectItem>
                    <SelectItem value="evening">Evening</SelectItem>
                    <SelectItem value="night">Night</SelectItem>
                    <SelectItem value="rotating">Rotating</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="shift_date">Date *</Label>
                <Input
                  id="shift_date"
                  type="date"
                  value={formData.shift_date}
                  onChange={(e) => setFormData({ ...formData, shift_date: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_time">Start Time *</Label>
                <Input
                  id="start_time"
                  type="time"
                  value={formData.start_time}
                  onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="end_time">End Time *</Label>
                <Input
                  id="end_time"
                  type="time"
                  value={formData.end_time}
                  onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Input
                id="notes"
                placeholder="Additional notes or instructions..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              />
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); resetForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleCreateShift} disabled={loading}>
              {loading ? 'Creating...' : 'Create Shift'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Bulk Allocate Shifts Dialog */}
      <Sheet open={showBulkDialog} onOpenChange={setShowBulkDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Bulk Allocate Shifts</SheetTitle>
              <SheetDescription className="mt-1">
                Allocate shifts for an employee across multiple days. Maximum 31 days at a time.
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="bulk-employee">Employee *</Label>
              <Select value={bulkFormData.employee_id} onValueChange={(value) => setBulkFormData({ ...bulkFormData, employee_id: value })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select employee" />
                </SelectTrigger>
                <SelectContent>
                  {reportees.map((employee) => (
                    <SelectItem key={employee.uid} value={employee.uid}>
                      {employee.name} - {employee.department}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="bulk-shift_type">Shift Type *</Label>
              <Select value={bulkFormData.shift_type} onValueChange={(value: any) => setBulkFormData({ ...bulkFormData, shift_type: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="morning">Morning</SelectItem>
                  <SelectItem value="afternoon">Afternoon</SelectItem>
                  <SelectItem value="evening">Evening</SelectItem>
                  <SelectItem value="night">Night</SelectItem>
                  <SelectItem value="rotating">Rotating</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Weekoff Days (Optional)</Label>
              <p className="text-xs text-gray-500 mb-2">
                Select days to exclude from shift allocation.
              </p>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Sun', value: 0 },
                  { label: 'Mon', value: 1 },
                  { label: 'Tue', value: 2 },
                  { label: 'Wed', value: 3 },
                  { label: 'Thu', value: 4 },
                  { label: 'Fri', value: 5 },
                  { label: 'Sat', value: 6 },
                ].map((day) => (
                  <label
                    key={day.value}
                    className={cn(
                      "flex items-center justify-center p-2 rounded-md border cursor-pointer transition-colors",
                      bulkFormData.weekoff_days.includes(day.value)
                        ? "bg-blue-100 border-blue-500 text-blue-700"
                        : "bg-white border-gray-300 hover:border-gray-400"
                    )}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={bulkFormData.weekoff_days.includes(day.value)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setBulkFormData({ ...bulkFormData, weekoff_days: [...bulkFormData.weekoff_days, day.value].sort() });
                        } else {
                          setBulkFormData({ ...bulkFormData, weekoff_days: bulkFormData.weekoff_days.filter((d) => d !== day.value) });
                        }
                      }}
                    />
                    <span className="text-sm font-medium">{day.label}</span>
                  </label>
                ))}
              </div>
              <div className="flex gap-2 mt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setBulkFormData({ ...bulkFormData, weekoff_days: [0, 6] })}>
                  Weekend Only
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => setBulkFormData({ ...bulkFormData, weekoff_days: [] })}>
                  Clear All
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bulk-start_date">Start Date *</Label>
                <Input
                  id="bulk-start_date"
                  type="date"
                  value={bulkFormData.start_date}
                  onChange={(e) => setBulkFormData({ ...bulkFormData, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bulk-end_date">End Date *</Label>
                <Input
                  id="bulk-end_date"
                  type="date"
                  value={bulkFormData.end_date}
                  onChange={(e) => setBulkFormData({ ...bulkFormData, end_date: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bulk-start_time">Start Time *</Label>
                <Input
                  id="bulk-start_time"
                  type="time"
                  value={bulkFormData.start_time}
                  onChange={(e) => setBulkFormData({ ...bulkFormData, start_time: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bulk-end_time">End Time *</Label>
                <Input
                  id="bulk-end_time"
                  type="time"
                  value={bulkFormData.end_time}
                  onChange={(e) => setBulkFormData({ ...bulkFormData, end_time: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="bulk-notes">Notes</Label>
              <Input
                id="bulk-notes"
                placeholder="Additional notes or instructions..."
                value={bulkFormData.notes}
                onChange={(e) => setBulkFormData({ ...bulkFormData, notes: e.target.value })}
              />
            </div>

            {bulkFormData.start_date && bulkFormData.end_date && (
              <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
                <p className="text-sm text-blue-800">
                  Shifts from <strong>{bulkFormData.start_date}</strong> to <strong>{bulkFormData.end_date}</strong>
                  {bulkFormData.weekoff_days.length > 0 && (
                    <span> (excluding {bulkFormData.weekoff_days.map((d) => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d]).join(', ')})</span>
                  )}.
                </p>
              </div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowBulkDialog(false); resetBulkForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleBulkCreateShifts} disabled={loading}>
              {loading ? 'Creating...' : 'Allocate Shifts'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Shift Dialog */}
      <Sheet open={showViewDialog} onOpenChange={(open) => { setShowViewDialog(open); if (!open) setViewingShift(null); }}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Shift Details</SheetTitle>
              <SheetDescription className="mt-1">
                View shift information and status.
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            {viewingShift ? (
              <>
                <div className="space-y-1">
                  <Label>Employee</Label>
                  <div className="text-sm text-gray-700 dark:text-gray-300">
                    {viewingShift.employee_name || 'Unknown'}
                    {viewingShift.employee_email ? ` (${viewingShift.employee_email})` : ''}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label>Date</Label>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      {new Date(viewingShift.shift_date).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label>Time</Label>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      {viewingShift.start_time} - {viewingShift.end_time}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label>Shift Type</Label>
                    <div>{getShiftTypeBadge(viewingShift.shift_type)}</div>
                  </div>
                  <div className="space-y-1">
                    <Label>Status</Label>
                    <div>{getStatusBadge(viewingShift.status)}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label>Created By</Label>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      {viewingShift.created_by_name || 'Unknown'}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label>Approved/Rejected By</Label>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      {viewingShift.approved_by_name || '—'}
                    </div>
                  </div>
                </div>

                {viewingShift.notes && (
                  <div className="space-y-1">
                    <Label>Notes</Label>
                    <div className="text-sm text-gray-700 dark:text-gray-300">{viewingShift.notes}</div>
                  </div>
                )}

                {viewingShift.status === 'rejected' && viewingShift.rejection_reason && (
                  <div className="space-y-1">
                    <Label>Rejection Reason</Label>
                    <div className="text-sm text-red-700 dark:text-red-300">{viewingShift.rejection_reason}</div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-gray-600 dark:text-gray-400">No shift selected.</div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowViewDialog(false); setViewingShift(null); }}>
              Close
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Edit Shift Dialog */}
      <Sheet open={showEditDialog} onOpenChange={setShowEditDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Edit Shift</SheetTitle>
              <SheetDescription className="mt-1">
                Update shift details. Editing an approved shift will require re-approval.
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="edit-shift_type">Shift Type *</Label>
              <Select value={formData.shift_type} onValueChange={(value: any) => setFormData({ ...formData, shift_type: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="morning">Morning</SelectItem>
                  <SelectItem value="afternoon">Afternoon</SelectItem>
                  <SelectItem value="evening">Evening</SelectItem>
                  <SelectItem value="night">Night</SelectItem>
                  <SelectItem value="rotating">Rotating</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-shift_date">Date *</Label>
              <Input
                id="edit-shift_date"
                type="date"
                value={formData.shift_date}
                onChange={(e) => setFormData({ ...formData, shift_date: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-start_time">Start Time *</Label>
                <Input
                  id="edit-start_time"
                  type="time"
                  value={formData.start_time}
                  onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-end_time">End Time *</Label>
                <Input
                  id="edit-end_time"
                  type="time"
                  value={formData.end_time}
                  onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-notes">Notes</Label>
              <Input
                id="edit-notes"
                placeholder="Additional notes or instructions..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              />
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowEditDialog(false); setEditingShift(null); resetForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleUpdateShift} disabled={loading}>
              {loading ? 'Updating...' : 'Update Shift'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

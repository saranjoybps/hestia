'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { 
  CalendarDays, 
  Plus, 
  Check, 
  X,
  Clock,
  FileText,
  TrendingUp,
  BarChart3,
  Download,
  Filter,
  Eye
} from 'lucide-react';
import { format, differenceInDays } from 'date-fns';

interface LeaveRequest {
  id: string;
  userId: string;
  userName: string;
  userEmail: string;
  leaveType: 'casual' | 'sick' | 'annual' | 'unpaid' | 'maternity' | 'paternity' | 'comp-off';
  startDate: string;
  endDate: string;
  totalDays: number;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  approvedBy?: string;
  approverName?: string;
  rejectionReason?: string;
  appliedDate: string;
  approvalDate?: string;
  department?: string;
  designation?: string;
}

interface LeaveBalance {
  userId: string;
  casual: number;
  sick: number;
  annual: number;
  compOff: number;
  totalUsed: number;
  totalAvailable: number;
}

interface LeaveStats {
  totalRequests: number;
  pendingApprovals: number;
  approvedLeaves: number;
  rejectedLeaves: number;
  byType: Record<string, number>;
  byDepartment: Record<string, number>;
}

export default function LeavesPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<LeaveRequest[]>([]);
  const [leaveBalance, setLeaveBalance] = useState<LeaveBalance | null>(null);
  const [leaveStats, setLeaveStats] = useState<LeaveStats | null>(null);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    leaveType: 'casual' as LeaveRequest['leaveType'],
    startDate: '',
    endDate: '',
    reason: '',
  });
  const [viewingLeave, setViewingLeave] = useState<LeaveRequest | null>(null);
  const [processingLeave, setProcessingLeave] = useState<LeaveRequest | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');

  // Permissions
  const isLead = userData?.role === 'lead';
  const isManager = userData?.role === 'manager' || userData?.role === 'director';
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const canApprove = isLead || isManager || isHR;

  useEffect(() => {
    if (user) {
      fetchLeaveRequests();
      fetchLeaveBalance();
      if (canApprove) {
        fetchPendingApprovals();
      }
      if (isHR) {
        fetchLeaveStats();
      }
    }
  }, [user, statusFilter, typeFilter]);

  const fetchLeaveRequests = async () => {
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        user_id: userData?.uid || '',
        ...(statusFilter !== 'all' && { status: statusFilter }),
        ...(typeFilter !== 'all' && { leave_type: typeFilter }),
      });

      const response = await fetch(`http://localhost:8000/api/leaves?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setLeaveRequests(data);
      }
    } catch (error) {
      console.error('Error fetching leave requests:', error);
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/leaves/pending-approvals`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setPendingApprovals(data);
      }
    } catch (error) {
      console.error('Error fetching pending approvals:', error);
    }
  };

  const fetchLeaveBalance = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/leaves/balance/${userData?.uid}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setLeaveBalance(data);
      }
    } catch (error) {
      console.error('Error fetching leave balance:', error);
    }
  };

  const fetchLeaveStats = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/leaves/stats`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setLeaveStats(data);
      }
    } catch (error) {
      console.error('Error fetching leave stats:', error);
    }
  };

  const handleCreateLeave = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const startDate = new Date(formData.startDate);
      const endDate = new Date(formData.endDate);
      const totalDays = differenceInDays(endDate, startDate) + 1;

      if (totalDays <= 0) {
        toast.error('End date must be after start date');
        return;
      }

      const response = await fetch('http://localhost:8000/api/leaves', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          userId: userData?.uid,
          leaveType: formData.leaveType,
          startDate: formData.startDate,
          endDate: formData.endDate,
          totalDays,
          reason: formData.reason,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create leave request');
      }

      toast.success('Leave request submitted successfully!');
      setShowCreateDialog(false);
      resetForm();
      fetchLeaveRequests();
      fetchLeaveBalance();
    } catch (error) {
      console.error('Create leave error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create leave request');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveLeave = async () => {
    if (!processingLeave) return;
    
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/leaves/${processingLeave.id}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            approvedBy: userData?.uid,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve leave');
      }

      toast.success('Leave request approved successfully!');
      setShowApproveDialog(false);
      setProcessingLeave(null);
      fetchLeaveRequests();
      fetchPendingApprovals();
      if (isHR) fetchLeaveStats();
    } catch (error) {
      console.error('Approve leave error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to approve leave');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectLeave = async () => {
    if (!processingLeave) return;
    
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/leaves/${processingLeave.id}/reject`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            rejectedBy: userData?.uid,
            rejectionReason,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reject leave');
      }

      toast.success('Leave request rejected');
      setShowRejectDialog(false);
      setProcessingLeave(null);
      setRejectionReason('');
      fetchLeaveRequests();
      fetchPendingApprovals();
      if (isHR) fetchLeaveStats();
    } catch (error) {
      console.error('Reject leave error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reject leave');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      leaveType: 'casual',
      startDate: '',
      endDate: '',
      reason: '',
    });
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <Check className="h-4 w-4" />;
      case 'rejected':
        return <X className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getLeaveTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      casual: 'Casual Leave',
      sick: 'Sick Leave',
      annual: 'Annual Leave',
      unpaid: 'Unpaid Leave',
      maternity: 'Maternity Leave',
      paternity: 'Paternity Leave',
      'comp-off': 'Compensatory Off',
    };
    return labels[type] || type;
  };

  const exportReport = () => {
    const csvContent = [
      ['Employee', 'Leave Type', 'Start Date', 'End Date', 'Days', 'Status', 'Applied Date', 'Reason'],
      ...leaveRequests.map(leave => [
        leave.userName,
        getLeaveTypeLabel(leave.leaveType),
        leave.startDate,
        leave.endDate,
        leave.totalDays,
        leave.status,
        format(new Date(leave.appliedDate), 'MMM dd, yyyy'),
        leave.reason
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leave_report_${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    toast.success('Report downloaded successfully!');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Leave Management</h1>
          <p className="text-gray-600 mt-1">Manage leave requests and track leave balance</p>
        </div>
        <div className="flex gap-3">
          {isHR && (
            <Button variant="outline" onClick={exportReport}>
              <Download className="h-4 w-4 mr-2" />
              Export Report
            </Button>
          )}
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Request Leave
          </Button>
        </div>
      </div>

      {/* Leave Balance Card */}
      {leaveBalance && (
        <Card>
          <CardHeader>
            <CardTitle>Your Leave Balance</CardTitle>
            <CardDescription>Available leave days for current year</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-sm text-gray-600">Casual Leave</p>
                <p className="text-3xl font-bold text-blue-600">{leaveBalance.casual}</p>
                <p className="text-xs text-gray-500 mt-1">days remaining</p>
              </div>
              <div className="p-4 bg-green-50 rounded-lg">
                <p className="text-sm text-gray-600">Sick Leave</p>
                <p className="text-3xl font-bold text-green-600">{leaveBalance.sick}</p>
                <p className="text-xs text-gray-500 mt-1">days remaining</p>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg">
                <p className="text-sm text-gray-600">Annual Leave</p>
                <p className="text-3xl font-bold text-purple-600">{leaveBalance.annual}</p>
                <p className="text-xs text-gray-500 mt-1">days remaining</p>
              </div>
              <div className="p-4 bg-orange-50 rounded-lg">
                <p className="text-sm text-gray-600">Comp Off</p>
                <p className="text-3xl font-bold text-orange-600">{leaveBalance.compOff}</p>
                <p className="text-xs text-gray-500 mt-1">days remaining</p>
              </div>
            </div>
            <Separator className="my-4" />
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Total Available</span>
              <span className="font-bold text-lg">{leaveBalance.totalAvailable} days</span>
            </div>
            <div className="flex justify-between text-sm mt-2">
              <span className="text-gray-600">Total Used</span>
              <span className="font-bold text-lg text-red-600">{leaveBalance.totalUsed} days</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="my-leaves" className="space-y-4">
        <TabsList>
          <TabsTrigger value="my-leaves">My Leaves ({leaveRequests.length})</TabsTrigger>
          {canApprove && (
            <TabsTrigger value="approvals">
              Pending Approvals ({pendingApprovals.length})
            </TabsTrigger>
          )}
          {isHR && <TabsTrigger value="reports">Reports & Analytics</TabsTrigger>}
        </TabsList>

        {/* My Leaves Tab */}
        <TabsContent value="my-leaves" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>My Leave Requests</CardTitle>
                  <CardDescription>View and track your leave applications</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Filters */}
              <div className="flex gap-4">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                  </SelectContent>
                </Select>

                <Select value={typeFilter} onValueChange={setTypeFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="casual">Casual Leave</SelectItem>
                    <SelectItem value="sick">Sick Leave</SelectItem>
                    <SelectItem value="annual">Annual Leave</SelectItem>
                    <SelectItem value="comp-off">Comp Off</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Table */}
              {leaveRequests.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Leave Type</TableHead>
                        <TableHead>Start Date</TableHead>
                        <TableHead>End Date</TableHead>
                        <TableHead>Days</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Applied On</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {leaveRequests.map((leave) => (
                        <TableRow key={leave.id}>
                          <TableCell className="font-medium">
                            {getLeaveTypeLabel(leave.leaveType)}
                          </TableCell>
                          <TableCell>{format(new Date(leave.startDate), 'MMM dd, yyyy')}</TableCell>
                          <TableCell>{format(new Date(leave.endDate), 'MMM dd, yyyy')}</TableCell>
                          <TableCell>{leave.totalDays} day{leave.totalDays > 1 ? 's' : ''}</TableCell>
                          <TableCell>
                            <Badge className={getStatusBadge(leave.status)}>
                              <span className="flex items-center gap-1">
                                {getStatusIcon(leave.status)}
                                {leave.status}
                              </span>
                            </Badge>
                          </TableCell>
                          <TableCell>{format(new Date(leave.appliedDate), 'MMM dd, yyyy')}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setViewingLeave(leave);
                                setShowViewDialog(true);
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <CalendarDays className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No leave requests found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pending Approvals Tab */}
        {canApprove && (
          <TabsContent value="approvals" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending Approvals</CardTitle>
                <CardDescription>Review and approve leave requests from your team</CardDescription>
              </CardHeader>
              <CardContent>
                {pendingApprovals.length > 0 ? (
                  <div className="space-y-4">
                    {pendingApprovals.map((leave) => (
                      <Card key={leave.id}>
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <h3 className="font-semibold text-lg">{leave.userName}</h3>
                              <p className="text-sm text-gray-600">{leave.userEmail}</p>
                              <p className="text-sm text-gray-500">{leave.department} • {leave.designation}</p>
                            </div>
                            <Badge className={getStatusBadge(leave.status)}>
                              {leave.status}
                            </Badge>
                          </div>

                          <div className="grid grid-cols-2 gap-4 mb-4">
                            <div>
                              <p className="text-sm text-gray-600">Leave Type</p>
                              <p className="font-medium">{getLeaveTypeLabel(leave.leaveType)}</p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600">Duration</p>
                              <p className="font-medium">{leave.totalDays} day{leave.totalDays > 1 ? 's' : ''}</p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600">Start Date</p>
                              <p className="font-medium">{format(new Date(leave.startDate), 'MMM dd, yyyy')}</p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600">End Date</p>
                              <p className="font-medium">{format(new Date(leave.endDate), 'MMM dd, yyyy')}</p>
                            </div>
                          </div>

                          <div className="mb-4">
                            <p className="text-sm text-gray-600 mb-1">Reason</p>
                            <p className="text-gray-800">{leave.reason}</p>
                          </div>

                          <Separator className="my-4" />

                          <div className="flex gap-3">
                            <Button
                              variant="outline"
                              className="flex-1 border-green-200 hover:bg-green-50"
                              onClick={() => {
                                setProcessingLeave(leave);
                                setShowApproveDialog(true);
                              }}
                            >
                              <Check className="h-4 w-4 mr-2 text-green-600" />
                              Approve
                            </Button>
                            <Button
                              variant="outline"
                              className="flex-1 border-red-200 hover:bg-red-50"
                              onClick={() => {
                                setProcessingLeave(leave);
                                setShowRejectDialog(true);
                              }}
                            >
                              <X className="h-4 w-4 mr-2 text-red-600" />
                              Reject
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No pending approvals</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Reports Tab */}
        {isHR && leaveStats && (
          <TabsContent value="reports" className="space-y-4">
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Total Requests</p>
                      <p className="text-3xl font-bold text-gray-900">{leaveStats.totalRequests}</p>
                    </div>
                    <FileText className="h-8 w-8 text-gray-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Pending</p>
                      <p className="text-3xl font-bold text-yellow-600">{leaveStats.pendingApprovals}</p>
                    </div>
                    <Clock className="h-8 w-8 text-yellow-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Approved</p>
                      <p className="text-3xl font-bold text-green-600">{leaveStats.approvedLeaves}</p>
                    </div>
                    <Check className="h-8 w-8 text-green-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Rejected</p>
                      <p className="text-3xl font-bold text-red-600">{leaveStats.rejectedLeaves}</p>
                    </div>
                    <X className="h-8 w-8 text-red-400" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Leave Type Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Leave Type Distribution
                </CardTitle>
                <CardDescription>Breakdown of leaves by type</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(leaveStats.byType).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <span className="text-sm font-medium">{getLeaveTypeLabel(type)}</span>
                      <div className="flex items-center gap-3">
                        <div className="w-48 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{
                              width: `${(count / leaveStats.totalRequests) * 100}%`
                            }}
                          />
                        </div>
                        <span className="text-sm font-bold w-8">{count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Department Usage */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Usage by Department
                </CardTitle>
                <CardDescription>Leave requests per department</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(leaveStats.byDepartment).map(([dept, count]) => (
                    <div key={dept} className="flex items-center justify-between">
                      <span className="text-sm font-medium">{dept}</span>
                      <div className="flex items-center gap-3">
                        <div className="w-48 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-purple-600 h-2 rounded-full"
                            style={{
                              width: `${(count / leaveStats.totalRequests) * 100}%`
                            }}
                          />
                        </div>
                        <span className="text-sm font-bold w-8">{count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Create Leave Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request Leave</DialogTitle>
            <DialogDescription>
              Submit a new leave request for approval
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="leave-type">Leave Type *</Label>
              <Select 
                value={formData.leaveType} 
                onValueChange={(value: any) => setFormData({ ...formData, leaveType: value })}
              >
                <SelectTrigger id="leave-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="casual">Casual Leave</SelectItem>
                  <SelectItem value="sick">Sick Leave</SelectItem>
                  <SelectItem value="annual">Annual Leave</SelectItem>
                  <SelectItem value="comp-off">Compensatory Off</SelectItem>
                  <SelectItem value="unpaid">Unpaid Leave</SelectItem>
                  <SelectItem value="maternity">Maternity Leave</SelectItem>
                  <SelectItem value="paternity">Paternity Leave</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start-date">Start Date *</Label>
                <Input
                  id="start-date"
                  type="date"
                  value={formData.startDate}
                  onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                  min={format(new Date(), 'yyyy-MM-dd')}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="end-date">End Date *</Label>
                <Input
                  id="end-date"
                  type="date"
                  value={formData.endDate}
                  onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                  min={formData.startDate || format(new Date(), 'yyyy-MM-dd')}
                />
              </div>
            </div>

            {formData.startDate && formData.endDate && (
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-900">
                  Total days: <strong>
                    {differenceInDays(new Date(formData.endDate), new Date(formData.startDate)) + 1}
                  </strong>
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="reason">Reason *</Label>
              <Textarea
                id="reason"
                placeholder="Please provide reason for leave..."
                value={formData.reason}
                onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateLeave} 
              disabled={loading || !formData.startDate || !formData.endDate || !formData.reason}
            >
              {loading ? 'Submitting...' : 'Submit Request'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Leave Dialog */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Leave Request Details</DialogTitle>
          </DialogHeader>
          {viewingLeave && (
            <div className="space-y-4 py-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-lg">{getLeaveTypeLabel(viewingLeave.leaveType)}</h3>
                <Badge className={getStatusBadge(viewingLeave.status)}>
                  {viewingLeave.status}
                </Badge>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Start Date</p>
                  <p className="font-medium">{format(new Date(viewingLeave.startDate), 'MMMM dd, yyyy')}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">End Date</p>
                  <p className="font-medium">{format(new Date(viewingLeave.endDate), 'MMMM dd, yyyy')}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Total Days</p>
                  <p className="font-medium">{viewingLeave.totalDays} day{viewingLeave.totalDays > 1 ? 's' : ''}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Applied On</p>
                  <p className="font-medium">{format(new Date(viewingLeave.appliedDate), 'MMM dd, yyyy')}</p>
                </div>
              </div>

              <div>
                <p className="text-sm text-gray-600 mb-2">Reason</p>
                <p className="text-gray-800 bg-gray-50 p-3 rounded-lg">{viewingLeave.reason}</p>
              </div>

              {viewingLeave.status === 'approved' && viewingLeave.approverName && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-900">
                    Approved by <strong>{viewingLeave.approverName}</strong>
                    {viewingLeave.approvalDate && ` on ${format(new Date(viewingLeave.approvalDate), 'MMM dd, yyyy')}`}
                  </p>
                </div>
              )}

              {viewingLeave.status === 'rejected' && (
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-sm text-red-900 font-medium mb-1">Rejection Reason:</p>
                  <p className="text-sm text-red-800">{viewingLeave.rejectionReason || 'No reason provided'}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Approve Dialog */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Leave Request</DialogTitle>
            <DialogDescription>
              Confirm approval for this leave request
            </DialogDescription>
          </DialogHeader>
          {processingLeave && (
            <div className="py-4">
              <div className="p-4 bg-green-50 rounded-lg space-y-2">
                <p className="font-semibold">{processingLeave.userName}</p>
                <p className="text-sm text-gray-600">
                  {getLeaveTypeLabel(processingLeave.leaveType)} • {processingLeave.totalDays} day{processingLeave.totalDays > 1 ? 's' : ''}
                </p>
                <p className="text-sm text-gray-600">
                  {format(new Date(processingLeave.startDate), 'MMM dd')} - {format(new Date(processingLeave.endDate), 'MMM dd, yyyy')}
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleApproveLeave} disabled={loading} className="bg-green-600 hover:bg-green-700">
              {loading ? 'Approving...' : 'Approve Leave'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Leave Request</DialogTitle>
            <DialogDescription>
              Provide a reason for rejection
            </DialogDescription>
          </DialogHeader>
          {processingLeave && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-red-50 rounded-lg space-y-2">
                <p className="font-semibold">{processingLeave.userName}</p>
                <p className="text-sm text-gray-600">
                  {getLeaveTypeLabel(processingLeave.leaveType)} • {processingLeave.totalDays} day{processingLeave.totalDays > 1 ? 's' : ''}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="rejection-reason">Reason for Rejection *</Label>
                <Textarea
                  id="rejection-reason"
                  placeholder="Please provide a reason..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={4}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowRejectDialog(false);
              setRejectionReason('');
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleRejectLeave} 
              disabled={loading || !rejectionReason}
              className="bg-red-600 hover:bg-red-700"
            >
              {loading ? 'Rejecting...' : 'Reject Leave'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

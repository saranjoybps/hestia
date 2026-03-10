'use client';

import { useAuth } from '@/contexts/AuthContext';
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
  Users,
  UserPlus,
  Edit,
  Trash2,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Mail,
  Phone,
  Calendar,
  Building2,
  Shield,
  Eye,
  TrendingUp,
  Clock
} from 'lucide-react';

interface Employee {
  uid: string;
  email: string;
  name: string;
  role: 'employee' | 'lead' | 'manager' | 'hr' | 'director';
  department: string;
  designation: string;
  phone?: string;
  dateOfJoining?: string;
  status: 'active' | 'inactive';
  managerId?: string;
  managerName?: string;
  reporteesCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

interface EmployeeFormData {
  email: string;
  name: string;
  password?: string;
  role: Employee['role'];
  department: string;
  designation: string;
  phone: string;
  dateOfJoining: string;
  managerId?: string;
}

interface ReporteeStats {
  uid: string;
  name: string;
  email: string;
  designation: string;
  department: string;
  attendancePercentage: number;
  totalWorkHours: number;
  performanceScore: number;
  status: string;
}

interface Department {
  id: string;
  name: string;
  description?: string;
  head_id?: string;
  created_at: string;
}

interface OnboardingRequest {
  id: string;
  email: string;
  name: string;
  phone: string;
  role: 'employee' | 'lead' | 'manager' | 'hr' | 'director';
  department: string;
  designation: string;
  manager_id?: string;
  lead_id?: string;
  notes?: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_by: string;
  requested_by_name?: string;
  requested_at: string;
  reviewed_by?: string;
  reviewed_by_name?: string;
  reviewed_at?: string;
  rejection_reason?: string;
}

export default function EmployeesPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [reportees, setReportees] = useState<ReporteeStats[]>([]);
  const [managers, setManagers] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [pendingRequests, setPendingRequests] = useState<OnboardingRequest[]>([]);
  const [myRequests, setMyRequests] = useState<OnboardingRequest[]>([]);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEmployees, setTotalEmployees] = useState(0);
  const itemsPerPage = 20;

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [roleFilter, setRoleFilter] = useState('all');

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDeactivateDialog, setShowDeactivateDialog] = useState(false);

  // Form data
  const [formData, setFormData] = useState<EmployeeFormData>({
    email: '',
    name: '',
    password: '',
    role: 'employee',
    department: '',
    designation: '',
    phone: '',
    dateOfJoining: new Date().toISOString().split('T')[0],
  });
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [viewingEmployee, setViewingEmployee] = useState<Employee | null>(null);
  const [deactivatingEmployee, setDeactivatingEmployee] = useState<Employee | null>(null);

  // Permissions
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const isDirector = userData?.role === 'director';
  const canCreateEmployee = isHR;
  const canEditAll = isHR;
  const canDeactivate = isDirector;
  const isLead = userData?.role === 'lead';
  const isManager = userData?.role === 'manager' || userData?.role === 'director';
  const canViewReportees = isLead || isManager;

  useEffect(() => {
    if (user) {
      fetchDepartments();
      fetchEmployees();
      if (canViewReportees) {
        fetchReportees();
      }
      if (canCreateEmployee) {
        fetchManagers();
      }
      // Fetch pending requests for HR and directors
      if (isHR) {
        fetchPendingRequests();
      }
    }
  }, [user, currentPage, searchQuery, departmentFilter, statusFilter, roleFilter]);

  const fetchDepartments = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/departments`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setDepartments(data.departments || []);
      }
    } catch (error) {
      console.error('Error fetching departments:', error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: itemsPerPage.toString(),
        ...(searchQuery && { search: searchQuery }),
        ...(departmentFilter !== 'all' && { department: departmentFilter }),
        ...(statusFilter !== 'all' && { status: statusFilter }),
        ...(roleFilter !== 'all' && { role: roleFilter }),
      });

      const response = await fetch(`${API_BASE_URL}/users?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setEmployees(data.users || data);
        if (data.total !== undefined) {
          setTotalEmployees(data.total);
          setTotalPages(Math.ceil(data.total / itemsPerPage));
        } else {
          // Fallback if backend doesn't return total
          setTotalEmployees(data.users?.length || data.length || 0);
        }
      }
    } catch (error) {
      console.error('Error fetching employees:', error);
      toast.error('Failed to fetch employees');
    }
  };

  const fetchReportees = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/users/${userData?.uid}/reportees`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setReportees(data);
      }
    } catch (error) {
      console.error('Error fetching reportees:', error);
    }
  };

  const fetchManagers = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/users?role=manager&role=lead&role=director&page=1&limit=50`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setManagers(data.users || data);
      }
    } catch (error) {
      console.error('Error fetching managers:', error);
    }
  };

  const fetchPendingRequests = async () => {
    try {
      const token = await user?.getIdToken();

      if (isDirector) {
        // Directors see all pending requests
        const params = new URLSearchParams({
          status: 'pending',
        });

        const response = await fetch(`${API_BASE_URL}/onboarding/requests?${params}`, {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
        });

        if (response.ok) {
          const data = await response.json();
          setPendingRequests(data.requests || []);
        }
      } else if (userData?.role === 'hr') {
        // HR sees all their own requests
        const response = await fetch(`${API_BASE_URL}/onboarding/requests`, {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
        });

        if (response.ok) {
          const data = await response.json();
          setMyRequests(data.requests || []);
        }
      }
    } catch (error) {
      console.error('Error fetching pending requests:', error);
    }
  };

  const handleApproveRequest = async (requestId: string) => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/onboarding/requests/${requestId}/approve`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve request');
      }

      toast.success('Onboarding request approved! Employee created successfully.');
      fetchPendingRequests();
      fetchEmployees();
    } catch (error) {
      console.error('Approve request error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to approve request');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectRequest = async (requestId: string, reason: string) => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      const response = await fetch(`${API_BASE_URL}/onboarding/requests/${requestId}/reject`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ rejection_reason: reason }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reject request');
      }

      toast.success('Onboarding request rejected.');
      fetchPendingRequests();
    } catch (error) {
      console.error('Reject request error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reject request');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEmployee = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Check if user is HR - create onboarding request instead of direct registration
      if (userData?.role === 'hr') {
        // Convert camelCase to snake_case for backend
        const requestData = {
          email: formData.email,
          name: formData.name,
          role: formData.role,
          department: formData.department,
          designation: formData.designation,
          phone: formData.phone,
          manager_id: formData.managerId || null,
          notes: `Date of Joining: ${formData.dateOfJoining || 'Not specified'}`,
        };

        const response = await fetch(`${API_BASE_URL}/onboarding/requests`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(requestData),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to create onboarding request');
        }

        toast.success('Onboarding request submitted for director approval.');
        setShowCreateDialog(false);
        resetForm();
        fetchPendingRequests(); // Refresh pending requests
      } else {
        // Directors can still directly create employees
        const requestData = {
          email: formData.email,
          name: formData.name,
          password: formData.password,
          role: formData.role,
          department: formData.department,
          designation: formData.designation,
          phone: formData.phone,
          manager_id: formData.managerId || null,
          lead_id: null,
          status: 'active'
        };

        const response = await fetch(`${API_BASE_URL}/users/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(requestData),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to create employee');
        }

        toast.success('Employee created successfully! Welcome email sent.');
        setShowCreateDialog(false);
        resetForm();
        fetchEmployees();
      }
    } catch (error) {
      console.error('Create employee error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create employee');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateEmployee = async () => {
    if (!editingEmployee) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const updateData = canEditAll
        ? {
          name: formData.name,
          role: formData.role,
          department: formData.department,
          designation: formData.designation,
          phone: formData.phone,
          manager_id: formData.managerId || null,
        }
        : {
          name: formData.name,
          phone: formData.phone,
        };

      const response = await fetch(`${API_BASE_URL}/users/${editingEmployee.uid}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(updateData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update employee');
      }

      toast.success('Employee updated successfully!');
      setShowEditDialog(false);
      setEditingEmployee(null);
      resetForm();
      fetchEmployees();
    } catch (error) {
      console.error('Update employee error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update employee');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivateEmployee = async () => {
    if (!deactivatingEmployee) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/users/${deactivatingEmployee.uid}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to deactivate employee');
      }

      toast.success('Employee deactivated successfully');
      setShowDeactivateDialog(false);
      setDeactivatingEmployee(null);
      fetchEmployees();
    } catch (error) {
      console.error('Deactivate employee error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to deactivate employee');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      email: '',
      name: '',
      password: '',
      role: 'employee',
      department: '',
      designation: '',
      phone: '',
      dateOfJoining: new Date().toISOString().split('T')[0],
    });
  };

  const openEditDialog = (employee: Employee) => {
    setEditingEmployee(employee);
    setFormData({
      email: employee.email,
      name: employee.name,
      role: employee.role,
      department: employee.department,
      designation: employee.designation,
      phone: employee.phone || '',
      dateOfJoining: employee.dateOfJoining || '',
      managerId: employee.managerId,
    });
    setShowEditDialog(true);
  };

  const getRoleBadge = (role: string) => {
    const styles: Record<string, string> = {
      director: 'bg-purple-100 text-purple-800',
      hr: 'bg-blue-100 text-blue-800',
      manager: 'bg-green-100 text-green-800',
      lead: 'bg-yellow-100 text-yellow-800',
      employee: 'bg-gray-100 text-gray-800',
    };
    return styles[role] || styles.employee;
  };

  const getStatusBadge = (status: string) => {
    return status === 'active'
      ? 'bg-green-100 text-green-800'
      : 'bg-red-100 text-red-800';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Employee Management</h1>
          <p className="text-gray-600 mt-1">Manage your team members and organizational structure</p>
        </div>
        {canCreateEmployee && (
          <Button onClick={() => setShowCreateDialog(true)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Add Employee
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Employees</TabsTrigger>
          {canViewReportees && (
            <TabsTrigger value="reportees">My Team ({reportees.length})</TabsTrigger>
          )}
          {userData?.role === 'hr' && (
            <TabsTrigger value="my-requests">My Requests ({myRequests.length})</TabsTrigger>
          )}
          {isDirector && (
            <TabsTrigger value="pending">Pending Requests ({pendingRequests.length})</TabsTrigger>
          )}
        </TabsList>

        {/* All Employees Tab */}
        <TabsContent value="all" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Employee Directory</CardTitle>
                  <CardDescription>
                    {employees.length} employee{employees.length !== 1 ? 's' : ''} found
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Filters */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="md:col-span-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="Search by name or email..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setCurrentPage(1);
                      }}
                      className="pl-10"
                    />
                  </div>
                </div>

                <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="Department" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Departments</SelectItem>
                    {departments.map(dept => (
                      <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Table */}
              {employees.length > 0 ? (
                <div className="space-y-4">
                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Department</TableHead>
                          <TableHead>Designation</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {employees.map((employee) => (
                          <TableRow key={employee.uid}>
                            <TableCell className="font-medium">{employee.name}</TableCell>
                            <TableCell>{employee.email}</TableCell>
                            <TableCell>{employee.department || '-'}</TableCell>
                            <TableCell>{employee.designation || '-'}</TableCell>
                            <TableCell>
                              <Badge className={getRoleBadge(employee.role)}>
                                {employee.role}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={getStatusBadge(employee.status)}>
                                {employee.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setViewingEmployee(employee);
                                    setShowViewDialog(true);
                                  }}
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                                {(canEditAll || employee.uid === userData?.uid) && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openEditDialog(employee)}
                                  >
                                    <Edit className="h-4 w-4" />
                                  </Button>
                                )}
                                {canDeactivate && employee.uid !== userData?.uid && employee.status === 'active' && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                      setDeactivatingEmployee(employee);
                                      setShowDeactivateDialog(true);
                                    }}
                                  >
                                    <Trash2 className="h-4 w-4 text-red-600" />
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between border-t pt-4">
                      <div className="text-sm text-gray-600">
                        <p>Page {currentPage} of {totalPages}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, totalEmployees)} of {totalEmployees} employees
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(1)}
                          disabled={currentPage === 1}
                        >
                          First
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          disabled={currentPage === 1}
                        >
                          <ChevronLeft className="h-4 w-4" />
                          Previous
                        </Button>

                        {/* Page Numbers */}
                        <div className="flex gap-1">
                          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            let pageNum;
                            if (totalPages <= 5) {
                              pageNum = i + 1;
                            } else if (currentPage <= 3) {
                              pageNum = i + 1;
                            } else if (currentPage >= totalPages - 2) {
                              pageNum = totalPages - 4 + i;
                            } else {
                              pageNum = currentPage - 2 + i;
                            }
                            return (
                              <Button
                                key={pageNum}
                                variant={currentPage === pageNum ? "default" : "outline"}
                                size="sm"
                                onClick={() => setCurrentPage(pageNum)}
                                className="w-10"
                              >
                                {pageNum}
                              </Button>
                            );
                          })}
                        </div>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={currentPage === totalPages}
                        >
                          Next
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(totalPages)}
                          disabled={currentPage === totalPages}
                        >
                          Last
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No employees found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Reportees Tab */}
        {canViewReportees && (
          <TabsContent value="reportees" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>My Team</CardTitle>
                <CardDescription>View your direct reportees and their performance</CardDescription>
              </CardHeader>
              <CardContent>
                {reportees.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {reportees.map((reportee) => (
                      <Card key={reportee.uid}>
                        <CardContent className="pt-6">
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-semibold text-lg">{reportee.name}</h3>
                                <p className="text-sm text-gray-600">{reportee.designation}</p>
                                <p className="text-sm text-gray-500">{reportee.department}</p>
                              </div>
                              <Badge className={getStatusBadge(reportee.status)}>
                                {reportee.status}
                              </Badge>
                            </div>

                            <Separator />

                            <div className="space-y-3">
                              <div className="flex items-center gap-2 text-sm">
                                <Mail className="h-4 w-4 text-gray-400" />
                                <span className="text-gray-600">{reportee.email}</span>
                              </div>

                              <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 bg-green-50 rounded-lg">
                                  <div className="flex items-center gap-2 mb-1">
                                    <Clock className="h-4 w-4 text-green-600" />
                                    <span className="text-xs text-gray-600">Attendance</span>
                                  </div>
                                  <p className="text-2xl font-bold text-green-600">
                                    {reportee.attendancePercentage?.toFixed(0) || 0}%
                                  </p>
                                </div>

                                <div className="p-3 bg-blue-50 rounded-lg">
                                  <div className="flex items-center gap-2 mb-1">
                                    <Clock className="h-4 w-4 text-blue-600" />
                                    <span className="text-xs text-gray-600">Work Hours</span>
                                  </div>
                                  <p className="text-2xl font-bold text-blue-600">
                                    {reportee.totalWorkHours?.toFixed(0) || 0}h
                                  </p>
                                </div>

                                <div className="p-3 bg-purple-50 rounded-lg col-span-2">
                                  <div className="flex items-center gap-2 mb-1">
                                    <TrendingUp className="h-4 w-4 text-purple-600" />
                                    <span className="text-xs text-gray-600">Performance Score</span>
                                  </div>
                                  <p className="text-2xl font-bold text-purple-600">
                                    {reportee.performanceScore?.toFixed(1) || 'N/A'}
                                  </p>
                                </div>
                              </div>
                            </div>

                            <Button
                              variant="outline"
                              className="w-full"
                              onClick={() => {
                                const employee = employees.find(e => e.uid === reportee.uid);
                                if (employee) {
                                  setViewingEmployee(employee);
                                  setShowViewDialog(true);
                                }
                              }}
                            >
                              <Eye className="h-4 w-4 mr-2" />
                              View Details
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No reportees found</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* My Requests Tab for HR */}
        {userData?.role === 'hr' && (
          <TabsContent value="my-requests" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>My Onboarding Requests</CardTitle>
                <CardDescription>Track status of your submitted employee onboarding requests</CardDescription>
              </CardHeader>
              <CardContent>
                {myRequests.length > 0 ? (
                  <div className="space-y-4">
                    {myRequests.map((request) => (
                      <Card key={request.id} className={`border ${request.status === 'pending' ? 'border-yellow-200 dark:border-yellow-800' :
                        request.status === 'approved' ? 'border-green-200 dark:border-green-800' :
                          'border-red-200 dark:border-red-800'
                        }`}>
                        <CardContent className="pt-6">
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-semibold text-lg">{request.name}</h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{request.email}</p>
                                <Badge className="mt-2">{request.role}</Badge>
                              </div>
                              <Badge className={
                                request.status === 'pending' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                                  request.status === 'approved' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                                    'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                              }>
                                {request.status.charAt(0).toUpperCase() + request.status.slice(1)}
                              </Badge>
                            </div>

                            <Separator />

                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Department:</span>
                                <p className="font-medium">{request.department}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Designation:</span>
                                <p className="font-medium">{request.designation}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Phone:</span>
                                <p className="font-medium">{request.phone}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Status:</span>
                                <p className="font-medium capitalize">{request.status}</p>
                              </div>
                            </div>

                            {request.notes && (
                              <div className="text-sm">
                                <span className="text-gray-500 dark:text-gray-400">Notes:</span>
                                <p className="mt-1 text-gray-700 dark:text-gray-300">{request.notes}</p>
                              </div>
                            )}

                            {request.status === 'rejected' && request.rejection_reason && (
                              <div className="text-sm p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                                <span className="font-medium text-red-700 dark:text-red-300">Rejection Reason:</span>
                                <p className="mt-1 text-red-600 dark:text-red-400">{request.rejection_reason}</p>
                              </div>
                            )}

                            <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                              <div>Requested on: {new Date(request.requested_at).toLocaleDateString()} at {new Date(request.requested_at).toLocaleTimeString()}</div>
                              {request.reviewed_at && (
                                <div>
                                  {request.status === 'approved' ? 'Approved' : 'Rejected'} by: {request.reviewed_by_name || 'Director'} on {new Date(request.reviewed_at).toLocaleDateString()}
                                </div>
                              )}
                            </div>

                            {request.status === 'pending' && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="outline" className="w-full border-red-500 text-red-600 hover:bg-red-50 dark:hover:bg-red-950" disabled={loading}>
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Delete Request
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Delete Onboarding Request</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      Are you sure you want to delete this onboarding request for {request.name}? This action cannot be undone.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      className="bg-red-600 hover:bg-red-700"
                                      onClick={async () => {
                                        try {
                                          setLoading(true);
                                          const token = await user?.getIdToken();
                                          const response = await fetch(`${API_BASE_URL}/onboarding/requests/${request.id}`, {
                                            method: 'DELETE',
                                            headers: {
                                              'Authorization': `Bearer ${token}`,
                                            },
                                          });

                                          if (response.ok) {
                                            toast.success('Onboarding request deleted');
                                            fetchPendingRequests();
                                          } else {
                                            const error = await response.json();
                                            throw new Error(error.detail || 'Failed to delete request');
                                          }
                                        } catch (error) {
                                          console.error('Delete error:', error);
                                          toast.error(error instanceof Error ? error.message : 'Failed to delete request');
                                        } finally {
                                          setLoading(false);
                                        }
                                      }}
                                    >
                                      Delete
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 dark:text-gray-400">No onboarding requests submitted yet</p>
                    <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">Click "Add Employee" to create a new onboarding request</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Pending Onboarding Requests Tab */}
        {isDirector && (
          <TabsContent value="pending" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending Onboarding Requests</CardTitle>
                <CardDescription>Review and approve employee onboarding requests from HR</CardDescription>
              </CardHeader>
              <CardContent>
                {pendingRequests.length > 0 ? (
                  <div className="space-y-4">
                    {pendingRequests.map((request) => (
                      <Card key={request.id} className="border border-blue-200 dark:border-blue-800">
                        <CardContent className="pt-6">
                          <div className="space-y-4">
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-semibold text-lg">{request.name}</h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{request.email}</p>
                                <Badge className="mt-2">{request.role}</Badge>
                              </div>
                              <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                                Pending
                              </Badge>
                            </div>

                            <Separator />

                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Department:</span>
                                <p className="font-medium">{request.department}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Designation:</span>
                                <p className="font-medium">{request.designation}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Phone:</span>
                                <p className="font-medium">{request.phone}</p>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Requested By:</span>
                                <p className="font-medium">{request.requested_by_name || 'HR'}</p>
                              </div>
                            </div>

                            {request.notes && (
                              <div className="text-sm">
                                <span className="text-gray-500 dark:text-gray-400">Notes:</span>
                                <p className="mt-1 text-gray-700 dark:text-gray-300">{request.notes}</p>
                              </div>
                            )}

                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              Requested on: {new Date(request.requested_at).toLocaleDateString()} at {new Date(request.requested_at).toLocaleTimeString()}
                            </div>

                            <div className="flex gap-2 pt-2">
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button className="flex-1 bg-green-600 hover:bg-green-700" disabled={loading}>
                                    Approve
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Approve Onboarding Request</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      This will create a new employee account for {request.name}. A temporary password will be generated and sent to their email.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      className="bg-green-600 hover:bg-green-700"
                                      onClick={() => handleApproveRequest(request.id)}
                                    >
                                      Approve & Create Employee
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>

                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="outline" className="flex-1 border-red-500 text-red-600 hover:bg-red-50 dark:hover:bg-red-950" disabled={loading}>
                                    Reject
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Reject Onboarding Request</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      Please provide a reason for rejecting this onboarding request.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <div className="py-4">
                                    <Label htmlFor="rejection-reason">Rejection Reason *</Label>
                                    <Input
                                      id="rejection-reason"
                                      placeholder="Enter reason for rejection..."
                                      className="mt-2"
                                    />
                                  </div>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                      className="bg-red-600 hover:bg-red-700"
                                      onClick={() => {
                                        const reason = (document.getElementById('rejection-reason') as HTMLInputElement)?.value;
                                        if (reason?.trim()) {
                                          handleRejectRequest(request.id, reason);
                                        } else {
                                          toast.error('Please provide a rejection reason');
                                        }
                                      }}
                                    >
                                      Reject Request
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
                    <p className="text-gray-600 dark:text-gray-400">No pending onboarding requests</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Create Employee Dialog */}
      <Sheet open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Add New Employee</SheetTitle>
              <SheetDescription className="mt-1">
                {userData?.role === 'hr'
                  ? 'Submit an onboarding request for director approval.'
                  : 'Create a new employee account. A welcome email will be sent automatically.'}
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="create-name">Full Name *</Label>
                <Input
                  id="create-name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-email">Email *</Label>
                <Input
                  id="create-email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="john@company.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-password">Password *</Label>
                <Input
                  id="create-password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Min. 6 characters"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-phone">Phone</Label>
                <Input
                  id="create-phone"
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+1234567890"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-role">Role *</Label>
                <Select value={formData.role} onValueChange={(value: any) => setFormData({ ...formData, role: value })}>
                  <SelectTrigger id="create-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="employee">Employee</SelectItem>
                    <SelectItem value="lead">Lead</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    {isDirector && <SelectItem value="hr">HR</SelectItem>}
                    {isDirector && <SelectItem value="director">Director</SelectItem>}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-department">Department *</Label>
                <Select value={formData.department} onValueChange={(value) => setFormData({ ...formData, department: value })}>
                  <SelectTrigger id="create-department">
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map(dept => (
                      <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-designation">Designation *</Label>
                <Input
                  id="create-designation"
                  value={formData.designation}
                  onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                  placeholder="Software Engineer"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="create-joining-date">Date of Joining *</Label>
                <Input
                  id="create-joining-date"
                  type="date"
                  value={formData.dateOfJoining}
                  onChange={(e) => setFormData({ ...formData, dateOfJoining: e.target.value })}
                />
              </div>

              <div className="space-y-2 col-span-2">
                <Label htmlFor="create-manager">Reporting Manager</Label>
                <Select
                  value={formData.managerId || 'none'}
                  onValueChange={(value) => setFormData({ ...formData, managerId: value === 'none' ? '' : value })}
                >
                  <SelectTrigger id="create-manager">
                    <SelectValue placeholder="Select manager (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {managers.map(manager => (
                      <SelectItem key={manager.uid} value={manager.uid}>
                        {manager.name} - {manager.role}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); resetForm(); }}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateEmployee}
              disabled={loading || !formData.email || !formData.name || !formData.password}
            >
              {loading ? 'Creating...' : userData?.role === 'hr' ? 'Submit Request' : 'Create Employee'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Edit Employee Dialog */}
      <Sheet open={showEditDialog} onOpenChange={setShowEditDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Edit Employee</SheetTitle>
              <SheetDescription className="mt-1">
                Update employee information. Changes will be logged in audit trail.
              </SheetDescription>
            </SheetHeader>
          </div>

          {editingEmployee && (
            <div className="p-6 space-y-5">
              <div className="p-4 bg-gray-50 border border-gray-100 rounded-lg">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Editing</p>
                <p className="font-semibold text-gray-900 mt-1">{editingEmployee.name}</p>
                <p className="text-sm text-gray-500">{editingEmployee.email}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-name">Full Name *</Label>
                  <Input
                    id="edit-name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-phone">Phone</Label>
                  <Input
                    id="edit-phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>

                {canEditAll && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="edit-role">Role</Label>
                      <Select value={formData.role} onValueChange={(value: any) => setFormData({ ...formData, role: value })}>
                        <SelectTrigger id="edit-role">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="employee">Employee</SelectItem>
                          <SelectItem value="lead">Lead</SelectItem>
                          <SelectItem value="manager">Manager</SelectItem>
                          {isDirector && <SelectItem value="hr">HR</SelectItem>}
                          {isDirector && <SelectItem value="director">Director</SelectItem>}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="edit-department">Department</Label>
                      <Select value={formData.department} onValueChange={(value) => setFormData({ ...formData, department: value })}>
                        <SelectTrigger id="edit-department">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {departments.map(dept => (
                            <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2 col-span-2">
                      <Label htmlFor="edit-designation">Designation</Label>
                      <Input
                        id="edit-designation"
                        value={formData.designation}
                        onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                      />
                    </div>

                    <div className="space-y-2 col-span-2">
                      <Label htmlFor="edit-manager">Reporting Manager</Label>
                      <Select
                        value={formData.managerId || 'none'}
                        onValueChange={(value) => setFormData({ ...formData, managerId: value === 'none' ? '' : value })}
                      >
                        <SelectTrigger id="edit-manager">
                          <SelectValue placeholder="Select manager" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
                          {managers.map(manager => (
                            <SelectItem key={manager.uid} value={manager.uid}>
                              {manager.name} - {manager.role}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowEditDialog(false); setEditingEmployee(null); resetForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleUpdateEmployee} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Employee Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Employee Details</SheetTitle>
            </SheetHeader>
          </div>

          {viewingEmployee && (
            <div className="p-6 space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{viewingEmployee.name}</h2>
                  <p className="text-sm text-gray-600 mt-0.5">{viewingEmployee.designation}</p>
                  <p className="text-xs text-gray-500">{viewingEmployee.department}</p>
                </div>
                <div className="flex flex-col gap-2 items-end">
                  <Badge className={getRoleBadge(viewingEmployee.role)}>
                    {viewingEmployee.role}
                  </Badge>
                  <Badge className={getStatusBadge(viewingEmployee.status)}>
                    {viewingEmployee.status}
                  </Badge>
                </div>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                    <Mail className="h-3.5 w-3.5" />
                    Email
                  </div>
                  <p className="text-sm font-medium text-gray-900 break-all">{viewingEmployee.email}</p>
                </div>

                {viewingEmployee.phone && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                      <Phone className="h-3.5 w-3.5" />
                      Phone
                    </div>
                    <p className="text-sm font-medium text-gray-900">{viewingEmployee.phone}</p>
                  </div>
                )}

                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                    <Building2 className="h-3.5 w-3.5" />
                    Department
                  </div>
                  <p className="text-sm font-medium text-gray-900">{viewingEmployee.department || '-'}</p>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                    <Shield className="h-3.5 w-3.5" />
                    Role
                  </div>
                  <p className="text-sm font-medium text-gray-900 capitalize">{viewingEmployee.role}</p>
                </div>

                {viewingEmployee.dateOfJoining && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                      <Calendar className="h-3.5 w-3.5" />
                      Date of Joining
                    </div>
                    <p className="text-sm font-medium text-gray-900">
                      {new Date(viewingEmployee.dateOfJoining).toLocaleDateString('en-US', {
                        year: 'numeric', month: 'short', day: 'numeric'
                      })}
                    </p>
                  </div>
                )}

                {viewingEmployee.managerName && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                      <Users className="h-3.5 w-3.5" />
                      Reporting To
                    </div>
                    <p className="text-sm font-medium text-gray-900">{viewingEmployee.managerName}</p>
                  </div>
                )}

                {viewingEmployee.reporteesCount !== undefined && viewingEmployee.reporteesCount > 0 && (
                  <div className="space-y-1 col-span-2">
                    <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                      <Users className="h-3.5 w-3.5" />
                      Team Size
                    </div>
                    <p className="text-sm font-medium text-gray-900">{viewingEmployee.reporteesCount} direct reportees</p>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end">
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Deactivate Confirmation Dialog */}
      <AlertDialog open={showDeactivateDialog} onOpenChange={setShowDeactivateDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate Employee?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate <strong>{deactivatingEmployee?.name}</strong>?
              This will revoke their access to the system. This action can be reversed by reactivating the employee.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeactivatingEmployee(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivateEmployee}
              className="bg-red-600 hover:bg-red-700"
              disabled={loading}
            >
              {loading ? 'Deactivating...' : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

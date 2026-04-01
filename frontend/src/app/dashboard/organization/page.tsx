'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== 'undefined' ? `${window.location.origin}/api` : 'http://localhost:8000/api');
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Users,
  Building2,
  UserCog,
  Shield,
  Edit,
  Eye,
  AlertCircle,
  ChevronRight,
  Briefcase,
  User,
  Crown,
  Award,
  RefreshCw,
  Trash2,
} from 'lucide-react';

interface User {
  uid: string;
  name: string;
  email: string;
  role: 'employee' | 'lead' | 'manager' | 'hr' | 'director';
  department: string;
  designation: string;
  manager_id?: string;
  managerName?: string;
  reportees?: User[];
}

interface Department {
  id: string;
  name: string;
  description?: string;
  head_id?: string;
  headName?: string;
  employeeCount?: number;
}

interface HierarchyNode {
  user: User;
  reportees: HierarchyNode[];
}

const normalizeUser = (user: any): User => ({
  ...user,
  manager_id: user.manager_id ?? user.managerId ?? user.lead_id ?? user.leadId,
});

export default function OrganizationPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [hierarchy, setHierarchy] = useState<HierarchyNode[]>([]);

  // Dialogs
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [showDepartmentDialog, setShowDepartmentDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDeleteDeptDialog, setShowDeleteDeptDialog] = useState(false);

  // Selected items
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [viewingUser, setViewingUser] = useState<User | null>(null);
  const [editingDepartment, setEditingDepartment] = useState<Department | null>(null);
  const [deletingDepartment, setDeletingDepartment] = useState<Department | null>(null);

  // Form data
  const [userForm, setUserForm] = useState<{
    uid: string;
    role: 'employee' | 'lead' | 'manager' | 'hr' | 'director';
    department: string;
    designation: string;
    manager_id: string;
  }>({
    uid: '',
    role: 'employee',
    department: '',
    designation: '',
    manager_id: '',
  });

  const [deptForm, setDeptForm] = useState({
    name: '',
    description: '',
    head_id: '',
  });

  // Permissions
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const isDirector = userData?.role === 'director';
  const isManager = userData?.role === 'manager';

  useEffect(() => {
    if (user && isHR) {
      fetchData();
    }
  }, [user, isHR]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Fetch users and departments in parallel with pagination
      const [usersRes, deptsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/users?page=1&limit=50`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/departments`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      if (usersRes.ok) {
        const data = await usersRes.json();
        const usersList = (data.users || []).map(normalizeUser);

        // Enrich users with manager/lead names
        const enrichedUsers = usersList.map((u: User) => ({
          ...u,
          managerName: u.manager_id ? usersList.find((m: User) => m.uid === u.manager_id)?.name : undefined,
        }));

        setUsers(enrichedUsers);
        buildHierarchy(enrichedUsers);

        // Update department employee counts with actual user data from frontend
        // (only if departments have already been loaded)
        if (deptsRes.ok) {
          const data = await deptsRes.json();
          const deptsList = data.departments || [];

          // Use backend-provided employeeCount (already calculated correctly)
          // Backend counts ALL users, not just the paginated 50 we fetch here
          setDepartments(deptsList);
        }
      } else if (deptsRes.ok) {
        // If only departments loaded (no users), use backend counts
        const data = await deptsRes.json();
        const deptsList = data.departments || [];
        setDepartments(deptsList);
      }

    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to fetch organization data');
    } finally {
      setLoading(false);
    }
  };

  const buildHierarchy = (usersList: User[]) => {
    // Build hierarchy tree starting from directors/top-level managers
    const topLevel = usersList.filter(u =>
      u.role === 'director' || (u.role === 'manager' && !u.manager_id)
    );

    const buildNode = (user: User): HierarchyNode => {
      const directReports = usersList.filter(u => u.manager_id === user.uid);

      return {
        user,
        reportees: directReports.map(buildNode),
      };
    };

    setHierarchy(topLevel.map(buildNode));
  };

  const handleUpdateUser = async () => {
    console.log('🔵 handleUpdateUser called');
    console.log('selectedUser:', selectedUser);
    console.log('userForm:', userForm);

    if (!selectedUser) {
      console.log('❌ No selected user, returning');
      return;
    }

    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Prepare update data
      const updateData: any = {
        role: userForm.role,
        department: userForm.department,
        designation: userForm.designation,
      };

      // Only include manager_id if it has a value or explicitly set to null
      if (userForm.manager_id && userForm.manager_id !== 'none') {
        updateData.manager_id = userForm.manager_id;
      } else {
        updateData.manager_id = null;
      }

      // Single reporting flow: clear legacy lead linkage on update.
      updateData.lead_id = null;

      console.log('Updating user with data:', updateData);

      const response = await fetch(`${API_BASE_URL}/users/${selectedUser.uid}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(updateData),
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        const error = await response.json();
        console.error('Error response:', error);
        throw new Error(error.detail || 'Failed to update user');
      }

      const result = await response.json();
      console.log('Update result:', result);

      toast.success('User updated successfully!');
      setShowUserDialog(false);
      setSelectedUser(null);
      resetUserForm();
      fetchData();
    } catch (error) {
      console.error('Update user error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update user');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveDepartment = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const url = editingDepartment
        ? `${API_BASE_URL}/departments/${editingDepartment.id}`
        : `${API_BASE_URL}/departments/`;

      const response = await fetch(url, {
        method: editingDepartment ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(deptForm),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save department');
      }

      toast.success(`Department ${editingDepartment ? 'updated' : 'created'} successfully!`);
      setShowDepartmentDialog(false);
      setEditingDepartment(null);
      resetDeptForm();
      fetchData();
    } catch (error) {
      console.error('Save department error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to save department');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDepartment = async () => {
    if (!deletingDepartment) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/departments/${deletingDepartment.id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete department');
      }

      toast.success('Department deleted successfully!');
      setShowDeleteDeptDialog(false);
      setDeletingDepartment(null);
      fetchData();
    } catch (error) {
      console.error('Delete department error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete department');
    } finally {
      setLoading(false);
    }
  };

  const openDeleteDepartment = (dept: Department) => {
    setDeletingDepartment(dept);
    setShowDeleteDeptDialog(true);
  };

  const resetUserForm = () => {
    setUserForm({
      uid: '',
      role: 'employee',
      department: '',
      designation: '',
      manager_id: '',
    });
  };

  const resetDeptForm = () => {
    setDeptForm({
      name: '',
      description: '',
      head_id: '',
    });
  };

  const openEditUser = (user: User) => {
    setSelectedUser(user);
    setUserForm({
      uid: user.uid,
      role: user.role,
      department: user.department || '',
      designation: user.designation || '',
      manager_id: user.manager_id || '',
    });
    setShowUserDialog(true);
  };

  const openEditDepartment = (dept?: Department) => {
    if (dept) {
      setEditingDepartment(dept);
      setDeptForm({
        name: dept.name,
        description: dept.description || '',
        head_id: dept.head_id || '',
      });
    } else {
      setEditingDepartment(null);
      resetDeptForm();
    }
    setShowDepartmentDialog(true);
  };

  const getRoleBadge = (role: string) => {
    const styles: Record<string, { bg: string; icon: any }> = {
      director: { bg: 'bg-purple-100 text-purple-800', icon: Crown },
      hr: { bg: 'bg-blue-100 text-blue-800', icon: Shield },
      manager: { bg: 'bg-green-100 text-green-800', icon: Briefcase },
      lead: { bg: 'bg-yellow-100 text-yellow-800', icon: Award },
      employee: { bg: 'bg-gray-100 text-gray-800', icon: User },
    };

    const style = styles[role] || styles.employee;
    const Icon = style.icon;

    return (
      <Badge className={style.bg}>
        <Icon className="h-3 w-3 mr-1" />
        {role.charAt(0).toUpperCase() + role.slice(1)}
      </Badge>
    );
  };

  const getReportingChain = (user: User): string[] => {
    const chain: string[] = [user.name];
    let current = user;

    while (current.manager_id) {
      const nextId = current.manager_id;
      const next = users.find(u => u.uid === nextId);
      if (!next) break;
      chain.push(next.name);
      current = next;
    }

    return chain;
  };

  const renderHierarchyNode = (node: HierarchyNode, level: number = 0) => {
    return (
      <div key={node.user.uid} className={`${level > 0 ? 'ml-8 mt-2' : 'mt-2'}`}>
        <div className="flex items-center gap-3 p-3 bg-white border rounded-lg hover:shadow-md transition-shadow">
          <Avatar className="h-10 w-10">
            <AvatarFallback>
              {node.user.name.split(' ').map(n => n[0]).join('')}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <p className="font-semibold">{node.user.name}</p>
            <p className="text-sm text-gray-600">{node.user.designation} • {node.user.department}</p>
          </div>
          {getRoleBadge(node.user.role)}
          {node.reportees.length > 0 && (
            <Badge variant="outline" className="text-xs">
              {node.reportees.length} reportee{node.reportees.length > 1 ? 's' : ''}
            </Badge>
          )}
        </div>
        {node.reportees.length > 0 && (
          <div className="border-l-2 border-gray-200 ml-5">
            {node.reportees.map(child => renderHierarchyNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  if (!isHR) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Access Denied</h2>
          <p className="text-gray-600 mt-2">You don't have permission to manage organization structure.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Organization Structure</h1>
          <p className="text-gray-600 mt-1">Manage roles, hierarchy, and departments</p>
        </div>
        <Button onClick={fetchData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Role Hierarchy Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Role Hierarchy & Rules
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Users className="h-4 w-4" />
                Reporting Structure
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <span><strong>Employees</strong> → report to <strong>Leads</strong></span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <span><strong>Leads</strong> → report to <strong>Managers</strong></span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <span><strong>Employees</strong> can also directly report to <strong>Managers</strong> or <strong>Directors</strong></span>
                </div>
              </div>
            </div>

            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Department Rules
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 p-2 bg-blue-50 rounded">
                  <AlertCircle className="h-4 w-4 text-blue-600" />
                  <span><strong>All users except Directors</strong> must belong to a Department</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-purple-50 rounded">
                  <Crown className="h-4 w-4 text-purple-600" />
                  <span><strong>Directors</strong> can be department-independent</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="users" className="space-y-4">
        <TabsList>
          <TabsTrigger value="users">
            <Users className="h-4 w-4 mr-2" />
            Users ({users.length})
          </TabsTrigger>
          <TabsTrigger value="departments">
            <Building2 className="h-4 w-4 mr-2" />
            Departments ({departments.length})
          </TabsTrigger>
          <TabsTrigger value="hierarchy">
            <UserCog className="h-4 w-4 mr-2" />
            Hierarchy View
          </TabsTrigger>
        </TabsList>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>All Users</CardTitle>
              <CardDescription>Manage user roles and reporting structure</CardDescription>
            </CardHeader>
            <CardContent>
              {users.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Department</TableHead>
                        <TableHead>Designation</TableHead>
                        <TableHead>Reports To</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((user) => (
                        <TableRow key={user.uid}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className="text-xs">
                                  {user.name.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="font-medium">{user.name}</p>
                                <p className="text-xs text-gray-500">{user.email}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>{getRoleBadge(user.role)}</TableCell>
                          <TableCell>
                            <span className={user.department ? '' : 'text-gray-400 italic'}>
                              {user.department || 'No department'}
                            </span>
                          </TableCell>
                          <TableCell>{user.designation || '-'}</TableCell>
                          <TableCell>
                            <div className="space-y-1">
                              {user.managerName && (
                                <div className="text-sm">
                                  <span className="text-gray-500">Manager:</span> {user.managerName}
                                </div>
                              )}
                              {!user.managerName && (
                                <span className="text-gray-400 text-sm">None</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex gap-2 justify-end">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setViewingUser(user);
                                  setShowViewDialog(true);
                                }}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openEditUser(user)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No users found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Departments Tab */}
        <TabsContent value="departments" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Departments</CardTitle>
                  <CardDescription>Manage organizational departments</CardDescription>
                </div>
                <Button onClick={() => openEditDepartment()}>
                  <Building2 className="h-4 w-4 mr-2" />
                  Add Department
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {departments.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {departments.map((dept) => (
                    <Card key={dept.id} className="hover:shadow-lg transition-shadow">
                      <CardContent className="pt-6">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <Building2 className="h-5 w-5 text-blue-600" />
                            <h3 className="font-semibold text-lg">{dept.name}</h3>
                          </div>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditDepartment(dept)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            {isDirector && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openDeleteDepartment(dept)}
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </div>

                        {dept.description && (
                          <p className="text-sm text-gray-600 mb-3">{dept.description}</p>
                        )}

                        <Separator className="my-3" />

                        <div className="space-y-2 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-600">Department Head:</span>
                            <span className="font-medium">
                              {dept.headName || 'Not assigned'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-600">Employees:</span>
                            <Badge variant="outline">{dept.employeeCount || 0}</Badge>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600 mb-4">No departments created yet</p>
                  <Button onClick={() => openEditDepartment()}>
                    Create First Department
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Hierarchy Tab */}
        <TabsContent value="hierarchy" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Organization Hierarchy</CardTitle>
              <CardDescription>Visual representation of reporting structure</CardDescription>
            </CardHeader>
            <CardContent>
              {hierarchy.length > 0 ? (
                <div className="space-y-4">
                  {hierarchy.map(node => renderHierarchyNode(node))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <UserCog className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No hierarchy data available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit User Dialog */}
      <Sheet open={showUserDialog} onOpenChange={setShowUserDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Edit User Role & Hierarchy</SheetTitle>
              <SheetDescription className="mt-1">
                Update user role, department, and reporting structure
              </SheetDescription>
            </SheetHeader>
          </div>

          {selectedUser && (
            <div className="p-6 space-y-5">
              <div className="flex items-center gap-3 p-4 bg-gray-50 border border-gray-100 rounded-lg">
                <Avatar className="h-12 w-12">
                  <AvatarFallback>{selectedUser.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-semibold text-gray-900">{selectedUser.name}</p>
                  <p className="text-sm text-gray-500">{selectedUser.email}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="role">Role *</Label>
                  <Select value={userForm.role} onValueChange={(value: any) => setUserForm({ ...userForm, role: value })}>
                    <SelectTrigger id="role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="employee">Employee</SelectItem>
                      <SelectItem value="lead">Lead</SelectItem>
                      <SelectItem value="manager">Manager</SelectItem>
                      <SelectItem value="hr">HR</SelectItem>
                      <SelectItem value="director">Director</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="department">Department {userForm.role !== 'director' && '*'}</Label>
                  <Select
                    value={userForm.department}
                    onValueChange={(value) => setUserForm({ ...userForm, department: value })}
                    disabled={userForm.role === 'director'}
                  >
                    <SelectTrigger id="department">
                      <SelectValue placeholder={userForm.role === 'director' ? 'Optional for Directors' : 'Select department'} />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="designation">Designation</Label>
                <Input id="designation" value={userForm.designation}
                  onChange={(e) => setUserForm({ ...userForm, designation: e.target.value })}
                  placeholder="e.g., Senior Developer, Team Lead" />
              </div>

              <Separator />

              <div className="space-y-4">
                <h4 className="font-semibold text-gray-900">Reporting Structure</h4>

	                <div className="space-y-2">
	                  <Label htmlFor="manager">Reports to Manager</Label>
	                  <Select
	                    value={userForm.manager_id || 'none'}
	                    onValueChange={(value) => setUserForm({ ...userForm, manager_id: value === 'none' ? '' : value })}
	                  >
	                    <SelectTrigger id="manager"><SelectValue placeholder="Select manager (optional)" /></SelectTrigger>
	                    <SelectContent>
	                      <SelectItem value="none">None</SelectItem>
		                      {users
		                        .filter(u =>
		                          u.uid !== selectedUser.uid &&
		                          (
		                            u.role === 'lead' ||
		                            u.role === 'manager' ||
		                            u.role === 'director' ||
		                            u.uid === userForm.manager_id
		                          )
		                        )
		                        .map((u) => (
		                          <SelectItem key={u.uid} value={u.uid}>{u.name} ({u.designation})</SelectItem>
		                        ))}
		                    </SelectContent>
		                  </Select>
	                </div>

                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    <strong>Note:</strong> Employees can report to a Lead, Manager, or Director.
                    Leads must report to a Manager. All users except Directors must belong to a department.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowUserDialog(false); setSelectedUser(null); resetUserForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleUpdateUser} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View User Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">User Details</SheetTitle>
            </SheetHeader>
          </div>

          {viewingUser && (
            <div className="p-6 space-y-5">
              <div className="flex items-center gap-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                <Avatar className="h-16 w-16">
                  <AvatarFallback className="text-xl">
                    {viewingUser.name.split(' ').map(n => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <h3 className="text-xl font-bold">{viewingUser.name}</h3>
                  <p className="text-gray-600">{viewingUser.email}</p>
                </div>
                {getRoleBadge(viewingUser.role)}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Department</p>
                  <p className="font-semibold">{viewingUser.department || 'Not assigned'}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Designation</p>
                  <p className="font-semibold">{viewingUser.designation || 'Not assigned'}</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Reporting Chain</p>
                <div className="flex items-center gap-2 flex-wrap mt-1">
                  {getReportingChain(viewingUser).map((name, index, arr) => (
                    <div key={index} className="flex items-center gap-2">
                      <Badge variant={index === 0 ? 'default' : 'outline'}>{name}</Badge>
                      {index < arr.length - 1 && <ChevronRight className="h-4 w-4 text-gray-400" />}
                    </div>
                  ))}
                </div>
              </div>

              {viewingUser.reportees && viewingUser.reportees.length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">
                      Direct Reports ({viewingUser.reportees.length})
                    </p>
                    <div className="space-y-2 mt-1">
                      {viewingUser.reportees.map((reportee) => (
                        <div key={reportee.uid} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="text-xs">
                              {reportee.name.split(' ').map(n => n[0]).join('')}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1">
                            <p className="font-medium text-sm">{reportee.name}</p>
                            <p className="text-xs text-gray-500">{reportee.designation}</p>
                          </div>
                          {getRoleBadge(reportee.role)}
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end">
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Department Dialog */}
      <Sheet open={showDepartmentDialog} onOpenChange={setShowDepartmentDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">{editingDepartment ? 'Edit Department' : 'Add Department'}</SheetTitle>
              <SheetDescription className="mt-1">
                {editingDepartment ? 'Update department information' : 'Create a new department'}
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="dept-name">Department Name *</Label>
              <Input id="dept-name" value={deptForm.name}
                onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
                placeholder="e.g., Engineering, Marketing" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dept-desc">Description</Label>
              <Input id="dept-desc" value={deptForm.description}
                onChange={(e) => setDeptForm({ ...deptForm, description: e.target.value })}
                placeholder="Brief description of the department" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dept-head">Department Head</Label>
              <Select
                value={deptForm.head_id || 'none'}
                onValueChange={(value) => setDeptForm({ ...deptForm, head_id: value === 'none' ? '' : value })}
              >
                <SelectTrigger id="dept-head">
                  <SelectValue placeholder="Select department head (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {users
                    .filter(u => ['manager', 'director', 'hr', 'lead'].includes(u.role))
                    .map((u) => (
                      <SelectItem key={u.uid} value={u.uid}>{u.name} ({u.role})</SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowDepartmentDialog(false); setEditingDepartment(null); resetDeptForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleSaveDepartment} disabled={loading || !deptForm.name}>
              {loading ? 'Saving...' : editingDepartment ? 'Update' : 'Create'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
      {/* Delete Department Confirmation Dialog */}
      <Sheet open={showDeleteDeptDialog} onOpenChange={setShowDeleteDeptDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Delete Department</SheetTitle>
              <SheetDescription className="mt-1">
                Are you sure you want to delete this department?
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex gap-3">
                <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-yellow-800">Warning</p>
                  <p className="text-sm text-yellow-700 mt-1">
                    You are about to delete <strong>{deletingDepartment?.name}</strong>.
                  </p>
                  <p className="text-sm text-yellow-700 mt-1">
                    This department has <strong>{deletingDepartment?.employeeCount || 0}</strong> employee(s).
                    {(deletingDepartment?.employeeCount || 0) > 0 && (
                      <span className="block mt-1 font-medium">
                        You must reassign all employees before deleting this department.
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowDeleteDeptDialog(false); setDeletingDepartment(null); }} disabled={loading}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteDepartment} disabled={loading}>
              {loading ? 'Deleting...' : 'Delete Department'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

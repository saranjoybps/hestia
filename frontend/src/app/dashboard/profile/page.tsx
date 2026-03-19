'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { User, Shield } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function ProfilePage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [profileData, setProfileData] = useState({
    name: '',
    email: '',
    phone: '',
    department: '',
    designation: '',
    dateOfJoining: '',
  });
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [reportingManagerName, setReportingManagerName] = useState<string>('-');

  const normalizeDateInput = (value?: string) => {
    if (!value) return '';
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString().split('T')[0];
    }
    const match = value.match(/^(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : '';
  };

  const getUserDateOfJoining = () => {
    const raw = (userData as any)?.dateOfJoining ?? (userData as any)?.date_of_joining;
    return typeof raw === 'string' ? raw : raw?.toString?.();
  };

  const formatDateDisplay = (value?: string) => {
    if (!value) return 'N/A';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return 'N/A';
    return parsed.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  useEffect(() => {
    if (userData) {
      setProfileData({
        name: userData.name || '',
        email: userData.email || '',
        phone: userData.phone || '',
        department: userData.department || '',
        designation: userData.designation || '',
        dateOfJoining: normalizeDateInput(getUserDateOfJoining()),
      });
    }
  }, [userData]);

  useEffect(() => {
    let isActive = true;

    const loadReportingManager = async () => {
      const reportingManagerId =
        userData?.manager_id ||
        userData?.lead_id ||
        userData?.managerId ||
        userData?.leadId;

      if (!reportingManagerId) {
        if (isActive) setReportingManagerName('-');
        return;
      }

      try {
        const token = await user?.getIdToken();
        if (!token) {
          if (isActive) setReportingManagerName('-');
          return;
        }

        const response = await fetch(`${API_BASE_URL}/users/${reportingManagerId}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!response.ok) {
          if (isActive) setReportingManagerName('-');
          return;
        }

        const managerData = await response.json();
        const managerName = managerData?.name || managerData?.email;
        if (isActive) setReportingManagerName(managerName || '-');
      } catch {
        if (isActive) setReportingManagerName('-');
      }
    };

    loadReportingManager();
    return () => { isActive = false; };
  }, [userData, user]);

  const getInitials = (name: string) => {
    return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const getRoleBadgeColor = (role: string) => {
    const colors: Record<string, string> = {
      director: 'bg-purple-100 text-purple-800',
      hr: 'bg-blue-100 text-blue-800',
      manager: 'bg-green-100 text-green-800',
      lead: 'bg-yellow-100 text-yellow-800',
      employee: 'bg-gray-100 text-gray-800',
    };
    return colors[role] || colors.employee;
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const payload: any = {};
      if (profileData.name) payload.name = profileData.name;
      if (profileData.phone) payload.phone = profileData.phone;
      if (profileData.dateOfJoining) payload.dateOfJoining = profileData.dateOfJoining;
      if (userData?.role === 'hr' || userData?.role === 'director') {
        if (profileData.department) payload.department = profileData.department;
        if (profileData.designation) payload.designation = profileData.designation;
      }
      const response = await fetch(`http://localhost:8000/api/users/${userData?.uid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update profile');
      }
      toast.success('Profile updated successfully!');
      window.location.reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    if (passwordData.newPassword.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      const { getAuth, updatePassword, reauthenticateWithCredential, EmailAuthProvider } = await import('firebase/auth');
      const auth = getAuth();
      if (!auth.currentUser || !user) throw new Error('No authenticated user');
      const credential = EmailAuthProvider.credential(user.email || '', passwordData.currentPassword);
      await reauthenticateWithCredential(auth.currentUser, credential);
      await updatePassword(auth.currentUser, passwordData.newPassword);
      toast.success('Password changed successfully!');
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (error: any) {
      if (error.code === 'auth/wrong-password') toast.error('Current password is incorrect');
      else if (error.code === 'auth/weak-password') toast.error('New password is too weak');
      else toast.error(error.message || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  if (!userData) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Loading profile...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
        <p className="text-gray-600 mt-1">Manage your personal information and account security</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-3">
          <Tabs defaultValue="general" className="space-y-4">
            <TabsList>
              <TabsTrigger value="general">General Information</TabsTrigger>
              <TabsTrigger value="security">Security</TabsTrigger>
            </TabsList>

            {/* General Tab */}
            <TabsContent value="general">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <User className="h-5 w-5 text-blue-600" />
                    Personal Information
                  </CardTitle>
                  <CardDescription>Update your personal details here</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleProfileUpdate} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Full Name</Label>
                        <Input
                          id="name"
                          value={profileData.name}
                          onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="email">Email Address</Label>
                        <Input
                          id="email"
                          type="email"
                          value={profileData.email}
                          disabled
                          className="bg-gray-50 text-gray-500"
                        />
                        <p className="text-xs text-gray-500">Email cannot be changed</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="phone">Phone Number</Label>
                        <Input
                          id="phone"
                          type="tel"
                          value={profileData.phone}
                          onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="department">Department</Label>
                        <Input
                          id="department"
                          value={profileData.department}
                          onChange={(e) => setProfileData({ ...profileData, department: e.target.value })}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="designation">Designation</Label>
                        <Input
                          id="designation"
                          value={profileData.designation}
                          onChange={(e) => setProfileData({ ...profileData, designation: e.target.value })}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="dateOfJoining">Date of Joining</Label>
                        <Input
                          id="dateOfJoining"
                          type="date"
                          value={profileData.dateOfJoining}
                          onChange={(e) => setProfileData({ ...profileData, dateOfJoining: e.target.value })}
                        />
                      </div>
                    </div>

                    <Separator />

                    <div className="flex justify-end gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          if (userData) {
                            setProfileData({
                              name: userData.name || '',
                              email: userData.email || '',
                              phone: userData.phone || '',
                              department: userData.department || '',
                              designation: userData.designation || '',
                              dateOfJoining: normalizeDateInput(getUserDateOfJoining()),
                            });
                          }
                        }}
                      >
                        Reset
                      </Button>
                      <Button type="submit" disabled={loading}>
                        {loading ? 'Saving...' : 'Save Changes'}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Security Tab */}
            <TabsContent value="security">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-red-600" />
                    Change Password
                  </CardTitle>
                  <CardDescription>Update your password to keep your account secure</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handlePasswordChange} className="space-y-4">
                    <div className="space-y-4 max-w-md">
                      <div className="space-y-2">
                        <Label htmlFor="currentPassword">Current Password</Label>
                        <Input
                          id="currentPassword"
                          type="password"
                          value={passwordData.currentPassword}
                          onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="newPassword">New Password</Label>
                        <Input
                          id="newPassword"
                          type="password"
                          value={passwordData.newPassword}
                          onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                          required
                          minLength={6}
                        />
                        <p className="text-xs text-gray-500">Must be at least 6 characters</p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="confirmPassword">Confirm New Password</Label>
                        <Input
                          id="confirmPassword"
                          type="password"
                          value={passwordData.confirmPassword}
                          onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                          required
                          minLength={6}
                        />
                      </div>
                    </div>

                    <Separator />

                    <div className="flex justify-end gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' })}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" disabled={loading}>
                        {loading ? 'Changing...' : 'Change Password'}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Profile Sidebar */}
        <div className="lg:col-span-1">
          <Card className="sticky top-4">
            <CardContent className="pt-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <Avatar className="h-20 w-20">
                  <AvatarFallback className="bg-gray-100 text-gray-700 text-xl font-semibold">
                    {getInitials(userData.name || 'User')}
                  </AvatarFallback>
                </Avatar>

                <div>
                  <h2 className="text-base font-bold text-gray-900">{userData.name}</h2>
                  <p className="text-sm text-gray-500 mt-0.5">{userData.designation || 'No designation'}</p>
                </div>

                <Badge className={getRoleBadgeColor(userData.role || 'employee')}>
                  {userData.role?.charAt(0).toUpperCase() + userData.role?.slice(1)}
                </Badge>

                <Separator />

                <div className="w-full space-y-3 text-sm">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Department</p>
                    <p className="text-gray-900 mt-1">{userData.department || 'N/A'}</p>
                  </div>

                  <Separator />

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Reporting Manager</p>
                    <p className="text-gray-900 mt-1">{reportingManagerName || '-'}</p>
                  </div>

                  <Separator />

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Email</p>
                    <p className="text-gray-900 mt-1 break-all text-xs">{userData.email}</p>
                  </div>

                  <Separator />

                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Joined</p>
                    <p className="text-gray-900 mt-1">{formatDateDisplay(getUserDateOfJoining())}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

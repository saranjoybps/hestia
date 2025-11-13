'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Calendar, FileText, TrendingUp, Loader2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { format } from 'date-fns';

interface DashboardStats {
  totalEmployees: number;
  presentToday: number;
  attendancePercentage: number;
  pendingLeaves: number;
  totalDepartments: number;
}

interface Announcement {
  id: string;
  title: string;
  description: string;
  createdAt: string;
  createdByName: string;
  priority: string;
  status: string;
}

export default function DashboardPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    totalEmployees: 0,
    presentToday: 0,
    attendancePercentage: 0,
    pendingLeaves: 0,
    totalDepartments: 0,
  });
  const [recentAnnouncements, setRecentAnnouncements] = useState<Announcement[]>([]);

  useEffect(() => {
    if (user) {
      fetchDashboardData();
    }
  }, [user]);

  const fetchDashboardData = async () => {
    try {
      const token = await user?.getIdToken();
      
      // Fetch all data in parallel
      const [usersRes, attendanceRes, leavesRes, announcementsRes, departmentsRes] = await Promise.all([
        fetch('http://localhost:8000/api/users?page=1&limit=1000', {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`http://localhost:8000/api/attendance?start_date=${format(new Date(), 'yyyy-MM-dd')}&end_date=${format(new Date(), 'yyyy-MM-dd')}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch('http://localhost:8000/api/leaves?status=pending', {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch('http://localhost:8000/api/announcements', {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch('http://localhost:8000/api/departments', {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      const usersData = await usersRes.json();
      const attendanceData = await attendanceRes.json();
      const leavesData = await leavesRes.json();
      const announcementsData = await announcementsRes.json();
      const departmentsData = await departmentsRes.json();

      // Calculate stats
      const totalEmployees = usersData.total || usersData.users?.length || 0;
      const todayAttendance = Array.isArray(attendanceData) ? attendanceData : [];
      const presentCount = todayAttendance.filter((a: any) => 
        a.status === 'present' || a.status === 'half-day'
      ).length;
      const attendancePercentage = totalEmployees > 0 
        ? (presentCount / totalEmployees) * 100 
        : 0;

      setStats({
        totalEmployees,
        presentToday: presentCount,
        attendancePercentage,
        pendingLeaves: leavesData.total || leavesData.leaves?.length || 0,
        totalDepartments: departmentsData.departments?.length || 0,
      });

      // Get recent announcements (published only)
      const announcements = announcementsData.announcements || [];
      const publishedAnnouncements = announcements
        .filter((a: Announcement) => a.status === 'published')
        .sort((a: Announcement, b: Announcement) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
        .slice(0, 3);
      setRecentAnnouncements(publishedAnnouncements);

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days > 1 ? 's' : ''} ago`;
  };

  const dashboardCards = [
    {
      title: 'Total Employees',
      value: loading ? '...' : stats.totalEmployees.toString(),
      icon: Users,
      description: 'Active employees',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Present Today',
      value: loading ? '...' : stats.presentToday.toString(),
      icon: Calendar,
      description: loading ? 'Loading...' : `${stats.attendancePercentage.toFixed(1)}% attendance`,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Pending Leaves',
      value: loading ? '...' : stats.pendingLeaves.toString(),
      icon: FileText,
      description: 'Require approval',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
    {
      title: 'Departments',
      value: loading ? '...' : stats.totalDepartments.toString(),
      icon: TrendingUp,
      description: 'Active departments',
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">
          Overview of your HR management system
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {dashboardCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card key={index}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">
                  {stat.title}
                </CardTitle>
                <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                  <Icon className={`h-5 w-5 ${stat.color}`} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                <p className="text-xs text-gray-500 mt-1">{stat.description}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent Announcements</CardTitle>
            <CardDescription>Latest updates from management</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : recentAnnouncements.length > 0 ? (
              <div className="space-y-4">
                {recentAnnouncements.map((announcement) => (
                  <div key={announcement.id} className="flex items-start gap-3">
                    <div className={`h-2 w-2 rounded-full mt-2 ${
                      announcement.priority === 'urgent' ? 'bg-red-500' :
                      announcement.priority === 'high' ? 'bg-orange-500' :
                      announcement.priority === 'medium' ? 'bg-yellow-500' :
                      'bg-blue-500'
                    }`} />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{announcement.title}</p>
                      <p className="text-xs text-gray-500">{getTimeAgo(announcement.createdAt)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p className="text-sm">No recent announcements</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Stats</CardTitle>
            <CardDescription>Overview of key metrics</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <div>
                  <p className="text-sm text-gray-600">Total Employees</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {loading ? '...' : stats.totalEmployees}
                  </p>
                </div>
                <Users className="h-8 w-8 text-blue-600" />
              </div>
              <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                <div>
                  <p className="text-sm text-gray-600">Present Today</p>
                  <p className="text-2xl font-bold text-green-600">
                    {loading ? '...' : `${stats.presentToday} (${stats.attendancePercentage.toFixed(0)}%)`}
                  </p>
                </div>
                <Calendar className="h-8 w-8 text-green-600" />
              </div>
              <div className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                <div>
                  <p className="text-sm text-gray-600">Pending Leave Requests</p>
                  <p className="text-2xl font-bold text-yellow-600">
                    {loading ? '...' : stats.pendingLeaves}
                  </p>
                </div>
                <FileText className="h-8 w-8 text-yellow-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

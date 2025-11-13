'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Calendar, FileText, TrendingUp } from 'lucide-react';

export default function DashboardPage() {
  const { userData } = useAuth();

  const stats = [
    {
      title: 'Total Employees',
      value: '248',
      icon: Users,
      description: '+12 from last month',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      title: 'Present Today',
      value: '234',
      icon: Calendar,
      description: '94.4% attendance',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      title: 'Pending Leaves',
      value: '8',
      icon: FileText,
      description: 'Require approval',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
    {
      title: 'Avg Performance',
      value: '4.2',
      icon: TrendingUp,
      description: 'Out of 5.0',
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
        {stats.map((stat, index) => {
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
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest updates from your team</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="h-2 w-2 bg-green-500 rounded-full mt-2" />
                <div className="flex-1">
                  <p className="text-sm font-medium">John Doe checked in</p>
                  <p className="text-xs text-gray-500">2 minutes ago</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="h-2 w-2 bg-blue-500 rounded-full mt-2" />
                <div className="flex-1">
                  <p className="text-sm font-medium">Leave request approved</p>
                  <p className="text-xs text-gray-500">15 minutes ago</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="h-2 w-2 bg-yellow-500 rounded-full mt-2" />
                <div className="flex-1">
                  <p className="text-sm font-medium">New announcement posted</p>
                  <p className="text-xs text-gray-500">1 hour ago</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upcoming Events</CardTitle>
            <CardDescription>Your schedule for this week</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className="text-xs text-gray-500">Nov</div>
                  <div className="text-lg font-bold">15</div>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">Team Meeting</p>
                  <p className="text-xs text-gray-500">10:00 AM - Conference Room A</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className="text-xs text-gray-500">Nov</div>
                  <div className="text-lg font-bold">18</div>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">Performance Reviews</p>
                  <p className="text-xs text-gray-500">All day</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className="text-xs text-gray-500">Nov</div>
                  <div className="text-lg font-bold">20</div>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">Company Holiday</p>
                  <p className="text-xs text-gray-500">All day - Thanksgiving</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

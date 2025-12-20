'use client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { 
  BarChart3,
  Download,
  FileText,
  Calendar,
  Users,
  TrendingUp,
  Clock,
  UserCheck,
  FileSpreadsheet,
  Filter,
  RefreshCw,
  Award,
  Briefcase,
  CalendarDays,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import { format, startOfMonth, endOfMonth, parseISO } from 'date-fns';

interface AttendanceReport {
  department: string;
  totalEmployees: number;
  presentCount: number;
  absentCount: number;
  leaveCount: number;
  halfDayCount: number;
  attendanceRate: number;
  avgWorkingHours: number;
}

interface LeaveReport {
  department: string;
  totalLeaves: number;
  approvedLeaves: number;
  pendingLeaves: number;
  rejectedLeaves: number;
  casualLeaves: number;
  sickLeaves: number;
  earnedLeaves: number;
  avgLeaveDuration: number;
}

interface PerformanceMetric {
  department: string;
  employeeCount: number;
  avgRating: number;
  positiveReviews: number;
  negativeReviews: number;
  pendingReviews: number;
  topPerformer: string;
}

interface EmployeeMetric {
  name: string;
  department: string;
  designation: string;
  attendanceRate: number;
  leavesUsed: number;
  avgRating: number;
  tasksCompleted: number;
}

interface ExportData {
  type: 'attendance' | 'leave' | 'performance' | 'employee';
  format: 'csv' | 'pdf';
  data: any[];
  filename: string;
}

export default function ReportsPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Report data
  const [attendanceReports, setAttendanceReports] = useState<AttendanceReport[]>([]);
  const [leaveReports, setLeaveReports] = useState<LeaveReport[]>([]);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetric[]>([]);
  const [employeeMetrics, setEmployeeMetrics] = useState<EmployeeMetric[]>([]);

  // Filters
  const [dateRange, setDateRange] = useState({
    startDate: format(startOfMonth(new Date()), 'yyyy-MM-dd'),
    endDate: format(endOfMonth(new Date()), 'yyyy-MM-dd'),
  });
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all');
  const [departments, setDepartments] = useState<string[]>([]);

  // Summary stats
  const [summaryStats, setSummaryStats] = useState({
    totalEmployees: 0,
    avgAttendanceRate: 0,
    totalLeaves: 0,
    avgPerformanceRating: 0,
  });

  // Permissions
  const isDirector = userData?.role === 'director';
  const isManager = userData?.role === 'manager';
  const isHR = userData?.role === 'hr';
  const hasAccess = isDirector || isManager || isHR;

  useEffect(() => {
    if (user && hasAccess) {
      fetchReports();
    }
  }, [user, dateRange, selectedDepartment]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        startDate: dateRange.startDate,
        endDate: dateRange.endDate,
        ...(selectedDepartment !== 'all' && { department: selectedDepartment }),
      });

      // Fetch all reports in parallel
      const [attendanceRes, leaveRes, performanceRes, employeeRes] = await Promise.all([
        fetch(`${API_BASE_URL}/reports/attendance?${params}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/reports/leaves?${params}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/reports/performance?${params}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${API_BASE_URL}/reports/employees?${params}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      if (attendanceRes.ok) {
        const data = await attendanceRes.json();
        setAttendanceReports(data.byDepartment || []);
        setSummaryStats(prev => ({ 
          ...prev, 
          totalEmployees: data.summary?.totalEmployees || 0,
          avgAttendanceRate: data.summary?.avgAttendanceRate || 0,
        }));
        
        // Extract departments
        const depts = [...new Set(data.byDepartment?.map((d: any) => d.department) || [])];
        setDepartments(depts as string[]);
      }

      if (leaveRes.ok) {
        const data = await leaveRes.json();
        setLeaveReports(data.byDepartment || []);
        setSummaryStats(prev => ({ 
          ...prev, 
          totalLeaves: data.summary?.totalLeaves || 0,
        }));
      }

      if (performanceRes.ok) {
        const data = await performanceRes.json();
        setPerformanceMetrics(data.byDepartment || []);
        setSummaryStats(prev => ({ 
          ...prev, 
          avgPerformanceRating: data.summary?.avgRating || 0,
        }));
      }

      if (employeeRes.ok) {
        const data = await employeeRes.json();
        setEmployeeMetrics(data.employees || []);
      }

    } catch (error) {
      console.error('Error fetching reports:', error);
      toast.error('Failed to fetch reports');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (type: 'attendance' | 'leave' | 'performance' | 'employee', format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        startDate: dateRange.startDate,
        endDate: dateRange.endDate,
        ...(selectedDepartment !== 'all' && { department: selectedDepartment }),
        format,
      });

      const response = await fetch(
        `${API_BASE_URL}/reports/export/${type}?${params}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (!response.ok) throw new Error('Export failed');

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${type}_report_${format}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success(`${type} report exported successfully!`);
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export report');
    } finally {
      setExporting(false);
    }
  };

  const getStatusColor = (rate: number) => {
    if (rate >= 90) return 'text-green-600';
    if (rate >= 75) return 'text-blue-600';
    if (rate >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getRatingColor = (rating: number) => {
    if (rating >= 4) return 'text-green-600';
    if (rating >= 3) return 'text-blue-600';
    if (rating >= 2) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (!hasAccess) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Access Denied</h2>
          <p className="text-gray-600 mt-2">You don't have permission to view reports.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Reports & Analytics</h1>
          <p className="text-gray-600 mt-1">Comprehensive organizational insights and metrics</p>
        </div>
        <Button onClick={fetchReports} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start-date">Start Date</Label>
              <Input
                id="start-date"
                type="date"
                value={dateRange.startDate}
                onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end-date">End Date</Label>
              <Input
                id="end-date"
                type="date"
                value={dateRange.endDate}
                onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="department">Department</Label>
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger id="department">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map((dept) => (
                    <SelectItem key={dept} value={dept}>
                      {dept}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button onClick={fetchReports} className="w-full">
                <Filter className="h-4 w-4 mr-2" />
                Apply Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Employees</p>
                <p className="text-3xl font-bold text-gray-900">{summaryStats.totalEmployees}</p>
              </div>
              <Users className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Avg Attendance</p>
                <p className={`text-3xl font-bold ${getStatusColor(summaryStats.avgAttendanceRate)}`}>
                  {summaryStats.avgAttendanceRate.toFixed(1)}%
                </p>
              </div>
              <UserCheck className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Leaves</p>
                <p className="text-3xl font-bold text-gray-900">{summaryStats.totalLeaves}</p>
              </div>
              <CalendarDays className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Avg Performance</p>
                <p className={`text-3xl font-bold ${getRatingColor(summaryStats.avgPerformanceRating)}`}>
                  {summaryStats.avgPerformanceRating.toFixed(1)}
                </p>
              </div>
              <Award className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="attendance" className="space-y-4">
        <TabsList>
          <TabsTrigger value="attendance">
            <Clock className="h-4 w-4 mr-2" />
            Attendance
          </TabsTrigger>
          <TabsTrigger value="leaves">
            <Calendar className="h-4 w-4 mr-2" />
            Leaves
          </TabsTrigger>
          <TabsTrigger value="performance">
            <TrendingUp className="h-4 w-4 mr-2" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="employees">
            <Users className="h-4 w-4 mr-2" />
            Employees
          </TabsTrigger>
        </TabsList>

        {/* Attendance Report */}
        <TabsContent value="attendance" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Attendance Summary by Department</CardTitle>
                  <CardDescription>
                    Attendance metrics from {format(parseISO(dateRange.startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(dateRange.endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('attendance', 'csv')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('attendance', 'pdf')}
                    disabled={exporting}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    PDF
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {attendanceReports.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Department</TableHead>
                        <TableHead className="text-center">Employees</TableHead>
                        <TableHead className="text-center">Present</TableHead>
                        <TableHead className="text-center">Absent</TableHead>
                        <TableHead className="text-center">On Leave</TableHead>
                        <TableHead className="text-center">Half Day</TableHead>
                        <TableHead className="text-center">Attendance Rate</TableHead>
                        <TableHead className="text-center">Avg Hours</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {attendanceReports.map((report) => (
                        <TableRow key={report.department}>
                          <TableCell className="font-medium">{report.department}</TableCell>
                          <TableCell className="text-center">{report.totalEmployees}</TableCell>
                          <TableCell className="text-center">
                            <span className="inline-flex items-center gap-1">
                              <CheckCircle className="h-4 w-4 text-green-600" />
                              {report.presentCount}
                            </span>
                          </TableCell>
                          <TableCell className="text-center">
                            <span className="inline-flex items-center gap-1">
                              <XCircle className="h-4 w-4 text-red-600" />
                              {report.absentCount}
                            </span>
                          </TableCell>
                          <TableCell className="text-center">{report.leaveCount}</TableCell>
                          <TableCell className="text-center">{report.halfDayCount}</TableCell>
                          <TableCell className="text-center">
                            <span className={`font-bold ${getStatusColor(report.attendanceRate)}`}>
                              {report.attendanceRate.toFixed(1)}%
                            </span>
                          </TableCell>
                          <TableCell className="text-center">
                            {report.avgWorkingHours.toFixed(1)}h
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No attendance data available for the selected period</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Leave Report */}
        <TabsContent value="leaves" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Leave Summary by Department</CardTitle>
                  <CardDescription>
                    Leave statistics from {format(parseISO(dateRange.startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(dateRange.endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('leave', 'csv')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('leave', 'pdf')}
                    disabled={exporting}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    PDF
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {leaveReports.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Department</TableHead>
                        <TableHead className="text-center">Total Leaves</TableHead>
                        <TableHead className="text-center">Approved</TableHead>
                        <TableHead className="text-center">Pending</TableHead>
                        <TableHead className="text-center">Rejected</TableHead>
                        <TableHead className="text-center">Casual</TableHead>
                        <TableHead className="text-center">Sick</TableHead>
                        <TableHead className="text-center">Earned</TableHead>
                        <TableHead className="text-center">Avg Duration</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {leaveReports.map((report) => (
                        <TableRow key={report.department}>
                          <TableCell className="font-medium">{report.department}</TableCell>
                          <TableCell className="text-center font-semibold">{report.totalLeaves}</TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-green-100 text-green-800">
                              {report.approvedLeaves}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-yellow-100 text-yellow-800">
                              {report.pendingLeaves}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-red-100 text-red-800">
                              {report.rejectedLeaves}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">{report.casualLeaves}</TableCell>
                          <TableCell className="text-center">{report.sickLeaves}</TableCell>
                          <TableCell className="text-center">{report.earnedLeaves}</TableCell>
                          <TableCell className="text-center">
                            {report.avgLeaveDuration.toFixed(1)} days
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No leave data available for the selected period</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Report */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Performance Metrics by Department</CardTitle>
                  <CardDescription>
                    Performance reviews from {format(parseISO(dateRange.startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(dateRange.endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('performance', 'csv')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('performance', 'pdf')}
                    disabled={exporting}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    PDF
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {performanceMetrics.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Department</TableHead>
                        <TableHead className="text-center">Employees</TableHead>
                        <TableHead className="text-center">Avg Rating</TableHead>
                        <TableHead className="text-center">Positive Reviews</TableHead>
                        <TableHead className="text-center">Negative Reviews</TableHead>
                        <TableHead className="text-center">Pending</TableHead>
                        <TableHead>Top Performer</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {performanceMetrics.map((metric) => (
                        <TableRow key={metric.department}>
                          <TableCell className="font-medium">{metric.department}</TableCell>
                          <TableCell className="text-center">{metric.employeeCount}</TableCell>
                          <TableCell className="text-center">
                            <span className={`text-xl font-bold ${getRatingColor(metric.avgRating)}`}>
                              {metric.avgRating.toFixed(1)}
                            </span>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-green-100 text-green-800">
                              {metric.positiveReviews}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-red-100 text-red-800">
                              {metric.negativeReviews}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge className="bg-yellow-100 text-yellow-800">
                              {metric.pendingReviews}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Award className="h-4 w-4 text-yellow-500" />
                              <span className="font-medium">{metric.topPerformer || 'N/A'}</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No performance data available for the selected period</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Employee Metrics */}
        <TabsContent value="employees" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Individual Employee Metrics</CardTitle>
                  <CardDescription>
                    Comprehensive employee performance overview
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('employee', 'csv')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('employee', 'pdf')}
                    disabled={exporting}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    PDF
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {employeeMetrics.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Department</TableHead>
                        <TableHead>Designation</TableHead>
                        <TableHead className="text-center">Attendance Rate</TableHead>
                        <TableHead className="text-center">Leaves Used</TableHead>
                        <TableHead className="text-center">Avg Rating</TableHead>
                        <TableHead className="text-center">Tasks Completed</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {employeeMetrics.map((metric, index) => (
                        <TableRow key={index}>
                          <TableCell className="font-medium">{metric.name}</TableCell>
                          <TableCell>{metric.department}</TableCell>
                          <TableCell>{metric.designation}</TableCell>
                          <TableCell className="text-center">
                            <span className={`font-semibold ${getStatusColor(metric.attendanceRate)}`}>
                              {metric.attendanceRate.toFixed(1)}%
                            </span>
                          </TableCell>
                          <TableCell className="text-center">{metric.leavesUsed}</TableCell>
                          <TableCell className="text-center">
                            <span className={`font-semibold ${getRatingColor(metric.avgRating)}`}>
                              {metric.avgRating > 0 ? metric.avgRating.toFixed(1) : 'N/A'}
                            </span>
                          </TableCell>
                          <TableCell className="text-center">{metric.tasksCompleted}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No employee data available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

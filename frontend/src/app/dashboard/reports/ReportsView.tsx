'use client';

import { useRouter, useSearchParams } from 'next/navigation';
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
import { useState } from 'react';
import { toast } from 'sonner';
import {
  BarChart3,
  Calendar,
  Users,
  TrendingUp,
  Clock,
  UserCheck,
  FileSpreadsheet,
  Filter,
  RefreshCw,
  Award,
  CalendarDays,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';

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
  leaveTypeCounts: Record<string, number>;
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

interface ReportsViewProps {
  initialData: {
    attendance: AttendanceReport[];
    leaves: LeaveReport[];
    performance: PerformanceMetric[];
    employees: EmployeeMetric[];
    summary: {
      totalEmployees: number;
      avgAttendanceRate: number;
      totalLeaves: number;
      avgPerformanceRating: number;
    };
    departments: string[];
  };
  startDate: string;
  endDate: string;
  selectedDepartment: string;
}

export function ReportsView({
  initialData,
  startDate,
  endDate,
  selectedDepartment,
}: ReportsViewProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [attendanceReports, setAttendanceReports] = useState<AttendanceReport[]>(initialData.attendance);
  const [leaveReports, setLeaveReports] = useState<LeaveReport[]>(initialData.leaves);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetric[]>(initialData.performance);
  const [employeeMetrics, setEmployeeMetrics] = useState<EmployeeMetric[]>(initialData.employees);
  const [summaryStats, setSummaryStats] = useState(initialData.summary);
  const [departments] = useState<string[]>(initialData.departments);
  const [localDateRange, setLocalDateRange] = useState({ startDate, endDate });
  const [localDepartment, setLocalDepartment] = useState(selectedDepartment);
  const [exporting, setExporting] = useState(false);

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

  const handleApplyFilters = () => {
    if (!localDateRange.startDate || !localDateRange.endDate || localDateRange.endDate < localDateRange.startDate) {
      toast.error('Choose a valid date range');
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set('startDate', localDateRange.startDate);
    params.set('endDate', localDateRange.endDate);
    if (localDepartment !== 'all') params.set('department', localDepartment);
    else params.delete('department');
    router.push(`/dashboard/reports?${params.toString()}`);
  };

  const handleExport = async (type: 'attendance' | 'leave' | 'performance' | 'employee') => {
    setExporting(true);
    try {
      const params = new URLSearchParams({ startDate: localDateRange.startDate, endDate: localDateRange.endDate, format: 'csv' });
      if (localDepartment !== 'all') params.set('department', localDepartment);
      const response = await fetch(`/api/reports/export/${type}?${params}`);
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${type}_report.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`${type} report exported`);
    } catch (e) {
      console.error(e);
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleRefresh = () => {
    router.refresh();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Reports & Analytics</h1>
          <p className="text-gray-600 mt-1">Comprehensive organizational insights and metrics</p>
        </div>
        <Button onClick={handleRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
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
                value={localDateRange.startDate}
                onChange={(e) => setLocalDateRange({ ...localDateRange, startDate: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end-date">End Date</Label>
              <Input
                id="end-date"
                type="date"
                value={localDateRange.endDate}
                onChange={(e) => setLocalDateRange({ ...localDateRange, endDate: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="department">Department</Label>
              <Select value={localDepartment} onValueChange={setLocalDepartment}>
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
              <Button onClick={handleApplyFilters} className="w-full">
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
                    Attendance metrics from {format(parseISO(startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('attendance')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
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
                    Leave statistics from {format(parseISO(startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('leave')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
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
                        <TableHead>Leave types</TableHead>
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
                          <TableCell>
                            <div className="flex flex-wrap gap-1.5">
                              {Object.entries(report.leaveTypeCounts || {}).map(([type, count]) => (
                                <Badge key={type} variant="outline" className="font-normal">{type.replace(/[-_]/g, ' ')}: {count}</Badge>
                              ))}
                            </div>
                          </TableCell>
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
                    Performance reviews from {format(parseISO(startDate), 'MMM dd, yyyy')} to{' '}
                    {format(parseISO(endDate), 'MMM dd, yyyy')}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport('performance')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
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
                    onClick={() => handleExport('employee')}
                    disabled={exporting}
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    CSV
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

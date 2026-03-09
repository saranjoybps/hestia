'use client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Calendar } from '@/components/ui/calendar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Clock,
  Calendar as CalendarIcon,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Download,
  Filter,
  Edit,
  Users,
  TrendingUp,
  FileText,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isToday, isSameDay } from 'date-fns';

// convert between frontend display statuses and API expected values
const toApiStatus = (status: AttendanceRecord['status']): string => {
  switch (status) {
    case 'half-day':
      return 'half_day';
    case 'on-leave':
    case 'week-off':
    case 'comp-off':
      return 'leave';
    default:
      return status;
  }
};

const fromApiStatus = (status: string): AttendanceRecord['status'] => {
  switch (status) {
    case 'half_day':
      return 'half-day';
    case 'leave':
      return 'on-leave'; // default mapping for any leave-type
    default:
      return status as AttendanceRecord['status'];
  }
};

interface AttendanceRecord {
  id: string;
  userId: string;
  userName: string;
  date: string;
  checkIn: string | null;
  checkOut: string | null;
  status: 'present' | 'absent' | 'half-day' | 'on-leave' | 'week-off' | 'comp-off' | 'holiday';
  workHours: number;
  notes: string;
  markedBy?: string;
  correctedBy?: string;
}

interface TeamMember {
  uid: string;
  name: string;
  email: string;
  designation: string;
  department: string;
}

interface AttendanceStats {
  totalDays: number;
  presentDays: number;
  absentDays: number;
  halfDays: number;
  leaves: number;
  attendancePercentage: number;
  totalWorkHours: number;
  avgWorkHours: number;
}

export default function AttendancePage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [attendanceRecords, setAttendanceRecords] = useState<AttendanceRecord[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<string>('me');
  const [teamShifts, setTeamShifts] = useState<Record<string, { shift_type: string; start_time: string; end_time: string; status: string } | null>>({});

  // Dialogs
  const [showMarkAttendanceDialog, setShowMarkAttendanceDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDayDetailsDialog, setShowDayDetailsDialog] = useState(false);

  // Form data
  const [markAttendanceData, setMarkAttendanceData] = useState({
    userId: '',
    date: format(new Date(), 'yyyy-MM-dd'),
    checkIn: '',
    checkOut: '',
    status: 'present' as AttendanceRecord['status'],
    notes: '',
  });
  const [teamAttendanceMap, setTeamAttendanceMap] = useState<Record<string, AttendanceRecord['status']>>({});
  const [editingRecord, setEditingRecord] = useState<AttendanceRecord | null>(null);
  const [selectedDayRecords, setSelectedDayRecords] = useState<AttendanceRecord[]>([]);

  // Filters
  const [filterStartDate, setFilterStartDate] = useState(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
  const [filterEndDate, setFilterEndDate] = useState(format(endOfMonth(new Date()), 'yyyy-MM-dd'));

  const isLead = userData?.role === 'lead';
  const isManager = userData?.role === 'manager' || userData?.role === 'director';
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const canMarkAttendance = isLead || isManager || isHR;
  const canEditAttendance = isManager || isHR;

  // Fetch team members (for leads/managers)
  useEffect(() => {
    if (canMarkAttendance && user) {
      fetchTeamMembers();
    }
  }, [canMarkAttendance, user]);

  // Fetch attendance records
  useEffect(() => {
    if (user) {
      fetchAttendanceRecords();
    }
  }, [user, selectedEmployee, filterStartDate, filterEndDate, teamMembers]);

  const fetchTeamMembers = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/users/${userData?.uid}/reportees`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setTeamMembers(data);
      }
    } catch (error) {
      console.error('Error fetching team members:', error);
    }
  };

  const fetchAttendanceRecords = async () => {
    try {
      const token = await user?.getIdToken();
      const userId = selectedEmployee === 'me' ? userData?.uid : selectedEmployee;

      const response = await fetch(
        `${API_BASE_URL}/attendance?user_id=${userId}&start_date=${filterStartDate}&end_date=${filterEndDate}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data: AttendanceRecord[] = await response.json();

        // ensure each record has a userName
        const selectedEmployeeName =
          selectedEmployee === 'me'
            ? userData?.name || 'Me'
            : teamMembers.find((m) => m.uid === selectedEmployee)?.name || '';

        const normalized = data.map((r) => ({
          ...r,
          status: fromApiStatus(r.status),
          userName: r.userName || selectedEmployeeName,
        }));

        setAttendanceRecords(normalized);
      }
    } catch (error) {
      console.error('Error fetching attendance:', error);
    }
  };

  const fetchTeamShiftsForDate = async (date: string) => {
    try {
      const token = await user?.getIdToken();

      // Fetch shifts per employee individually to bypass role-based filtering
      const shiftsMap: Record<string, any> = {};

      await Promise.all(
        teamMembers.map(async (member) => {
          const response = await fetch(
            `${API_BASE_URL}/shifts?employee_id=${member.uid}&shift_date=${date}`,
            { headers: { 'Authorization': `Bearer ${token}` } }
          );

          if (response.ok) {
            const data = await response.json();
            const shifts = data.shifts || [];

            // Pick the latest non-rejected shift for this employee on this date
            const validShift = shifts.find(
              (s: any) => s.shift_date === date && s.status !== 'rejected'
            );

            if (validShift) {
              shiftsMap[member.uid] = {
                shift_type: validShift.shift_type,
                start_time: validShift.start_time,
                end_time: validShift.end_time,
                status: validShift.status,
              };
            }
          }
        })
      );

      setTeamShifts(shiftsMap);
    } catch (error) {
      console.error('Error fetching team shifts:', error);
    }
  };

  const handleMarkAttendance = async () => {
    // ensure every member has a shift (unless it's a weekend)
    const dateObj = new Date(markAttendanceData.date);
    const invalidMembers = teamMembers.filter(m => {
      const shift = teamShifts[m.uid];
      const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
      return !shift && !isWeekend;
    });

    if (invalidMembers.length > 0) {
      toast.error(
        `Cannot submit: no shift assigned for ${invalidMembers
          .map(m => m.name)
          .join(', ')}`
      );
      return;
    }

    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Mark attendance for all team members
      const promises = Object.entries(teamAttendanceMap).map(async ([userId, status]) => {
        const response = await fetch(`${API_BASE_URL}/attendance`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            user_id: userId,
            date: markAttendanceData.date,
            status: toApiStatus(status),
            marked_by: userData?.uid,
            check_in: status === 'present' || status === 'half-day' ? '09:00' : '',
            check_out: status === 'present' || status === 'half-day' ? '18:00' : '',
            notes: '',
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || `Failed to mark attendance for ${userId}`);
        }

        return response.json();
      });

      await Promise.all(promises);

      toast.success(`Attendance marked successfully for ${Object.keys(teamAttendanceMap).length} team member(s)!`);
      setShowMarkAttendanceDialog(false);
      resetMarkAttendanceForm();
      setTeamAttendanceMap({});
      fetchAttendanceRecords();
    } catch (error) {
      console.error('Mark attendance error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to mark attendance');
    } finally {
      setLoading(false);
    }
  };

  const handleEditAttendance = async () => {
    if (!editingRecord) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/attendance/${editingRecord.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          // include existing values so server validations continue to pass
          checkIn: editingRecord.checkIn,
          checkOut: editingRecord.checkOut,
          status: toApiStatus(editingRecord.status),
          notes: editingRecord.notes,
          correctedBy: userData?.uid,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update attendance');
      }

      toast.success('Attendance updated successfully!');
      setShowEditDialog(false);
      setEditingRecord(null);
      fetchAttendanceRecords();
    } catch (error) {
      console.error('Edit attendance error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update attendance');
    } finally {
      setLoading(false);
    }
  };

  const resetMarkAttendanceForm = () => {
    setMarkAttendanceData({
      userId: '',
      date: format(new Date(), 'yyyy-MM-dd'),
      checkIn: '',
      checkOut: '',
      status: 'present',
      notes: '',
    });
  };

  const handleDayClick = (date: Date) => {
    const dayRecords = attendanceRecords.filter(r =>
      isSameDay(new Date(r.date), date)
    );
    setSelectedDayRecords(dayRecords);
    setShowDayDetailsDialog(true);
  };

  const exportAttendanceReport = () => {
    const csvContent = [
      ['Date', 'Employee', 'Status', 'Notes'],
      ...attendanceRecords.map(r => [
        r.date,
        r.userName || selectedEmployeeName,
        r.status,
        r.notes || '-'
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance_report_${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    toast.success('Report downloaded successfully!');
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      present: 'bg-green-100 text-green-800',
      absent: 'bg-red-100 text-red-800',
      'half-day': 'bg-yellow-100 text-yellow-800',
      'on-leave': 'bg-purple-100 text-purple-800',
      'week-off': 'bg-gray-100 text-gray-800',
      'comp-off': 'bg-indigo-100 text-indigo-800',
      'holiday': 'bg-pink-100 text-pink-800',
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'present':
        return <CheckCircle2 className="h-4 w-4" />;
      case 'absent':
        return <XCircle className="h-4 w-4" />;
      case 'half-day':
        return <AlertCircle className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getCalendarDayColor = (date: Date) => {
    const record = attendanceRecords.find(r => isSameDay(new Date(r.date), date));
    if (!record) return undefined;

    switch (record.status) {
      case 'present':
        // Treat present as green by default. If workHours is defined and explicitly
        // less than 8, use yellow; otherwise assume a full day.
        if (record.workHours != null && record.workHours < 8) {
          return '#eab308'; // Yellow for short days
        }
        return '#22c55e'; // Green for full present days
      case 'half-day':
        return '#eab308'; // Yellow
      case 'absent':
        return '#ef4444'; // Red
      case 'on-leave':
      case 'holiday':
      case 'week-off':
      case 'comp-off':
        return '#3b82f6'; // Blue
      default:
        return undefined;
    }
  };

  const calculateStats = (): AttendanceStats => {
    const totalDays = attendanceRecords.length;
    const presentDays = attendanceRecords.filter(r =>
      r.status === 'present'
    ).length;
    const absentDays = attendanceRecords.filter(r => r.status === 'absent').length;
    const halfDays = attendanceRecords.filter(r => r.status === 'half-day').length;
    const leaves = attendanceRecords.filter(r =>
      r.status === 'on-leave' || r.status === 'week-off' || r.status === 'comp-off'
    ).length;
    const totalWorkHours = attendanceRecords.reduce((sum, r) => sum + (r.workHours || 0), 0);
    const workingDays = totalDays - leaves;
    const attendancePercentage = workingDays > 0
      ? ((presentDays + (halfDays * 0.5)) / workingDays) * 100
      : 0;
    const avgWorkHours = presentDays > 0 ? totalWorkHours / presentDays : 0;

    return {
      totalDays,
      presentDays,
      absentDays,
      halfDays,
      leaves,
      attendancePercentage,
      totalWorkHours,
      avgWorkHours,
    };
  };

  const stats = calculateStats();

  // compute display name for currently selected employee (used when records lack userName)
  const selectedEmployeeName =
    selectedEmployee === 'me'
      ? userData?.name || 'Me'
      : teamMembers.find((m) => m.uid === selectedEmployee)?.name || '';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Attendance Management</h1>
          <p className="text-gray-600 mt-1">Track attendance, work hours, and generate reports</p>
        </div>
        <div className="flex gap-3">
          {canMarkAttendance && (
            <Button onClick={() => {
              // Initialize attendance map with 'present' for all team members
              const initialMap: Record<string, AttendanceRecord['status']> = {};
              teamMembers.forEach(member => {
                initialMap[member.uid] = 'present';
              });
              setTeamAttendanceMap(initialMap);
              // Fetch shifts for the selected date
              fetchTeamShiftsForDate(markAttendanceData.date);
              setShowMarkAttendanceDialog(true);
            }}>
              <Users className="h-4 w-4 mr-2" />
              Mark Team Attendance
            </Button>
          )}
          <Button variant="outline" onClick={exportAttendanceReport}>
            <Download className="h-4 w-4 mr-2" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Employee Selector for Leads/Managers */}
      {canMarkAttendance && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <Label htmlFor="employee-select" className="text-sm font-medium">
                View Attendance For:
              </Label>
              <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
                <SelectTrigger id="employee-select" className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="me">{userData?.name || 'My Attendance'}</SelectItem>
                  <Separator className="my-2" />
                  {teamMembers.map(member => (
                    <SelectItem key={member.uid} value={member.uid}>
                      {member.name} - {member.designation}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Monthly Stats - Only show for own attendance */}
      {selectedEmployee === 'me' && (
        <Card>
          <CardHeader>
            <CardTitle>Monthly Summary</CardTitle>
            <CardDescription>{format(currentMonth, 'MMMM yyyy')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gradient-to-r from-green-50 to-green-100 rounded-lg">
                <div>
                  <p className="text-sm text-gray-600">Attendance Rate</p>
                  <p className="text-3xl font-bold text-green-600">
                    {stats.attendancePercentage.toFixed(1)}%
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-green-600" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-xs text-gray-600">Present</p>
                  <p className="text-2xl font-bold text-green-600">{stats.presentDays}</p>
                </div>
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-xs text-gray-600">Absent</p>
                  <p className="text-2xl font-bold text-red-600">{stats.absentDays}</p>
                </div>
                <div className="p-3 bg-yellow-50 rounded-lg">
                  <p className="text-xs text-gray-600">Half Day</p>
                  <p className="text-2xl font-bold text-yellow-600">{stats.halfDays}</p>
                </div>
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-xs text-gray-600">Leaves</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.leaves}</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Total Work Hours</span>
                  <span className="font-bold">{stats.totalWorkHours.toFixed(1)} hrs</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Avg Hours/Day</span>
                  <span className="font-bold">{stats.avgWorkHours.toFixed(1)} hrs</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="list" className="space-y-4">
        <TabsList>
          <TabsTrigger value="list">Attendance List</TabsTrigger>
          <TabsTrigger value="calendar">Calendar View</TabsTrigger>
        </TabsList>

        {/* List View */}
        <TabsContent value="list" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Attendance Records</CardTitle>
              <CardDescription>View your attendance history</CardDescription>
            </CardHeader>
            <CardContent>
              {attendanceRecords.length > 0 ? (
                <div className="space-y-4">
                  {/* Date Range Filter */}
                  <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <Label htmlFor="start-date" className="text-sm">Start Date</Label>
                      <Input
                        id="start-date"
                        type="date"
                        value={filterStartDate}
                        onChange={(e) => setFilterStartDate(e.target.value)}
                        className="mt-1"
                      />
                    </div>
                    <div className="flex-1">
                      <Label htmlFor="end-date" className="text-sm">End Date</Label>
                      <Input
                        id="end-date"
                        type="date"
                        value={filterEndDate}
                        onChange={(e) => setFilterEndDate(e.target.value)}
                        className="mt-1"
                      />
                    </div>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Employee</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Notes</TableHead>
                        {canEditAttendance && <TableHead>Actions</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {attendanceRecords.map((record) => (
                        <TableRow key={record.id}>
                          <TableCell className="font-medium">
                            {format(new Date(record.date), 'MMM dd, yyyy')}
                          </TableCell>
                          <TableCell>{record.userName || '-'}</TableCell>
                          <TableCell>
                            <Badge className={getStatusBadge(record.status)}>
                              <span className="flex items-center gap-1">
                                {getStatusIcon(record.status)}
                                {record.status.replace('-', ' ')}
                              </span>
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-gray-600">
                            {record.notes || '-'}
                          </TableCell>
                          {canEditAttendance && (
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setEditingRecord(record);
                                  setShowEditDialog(true);
                                }}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <CalendarIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No attendance records found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Calendar View */}
        <TabsContent value="calendar" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Calendar View</CardTitle>
              <CardDescription>Click on any day to view details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Legend */}
                <div className="flex flex-wrap gap-4 p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-green-500"></div>
                    <span className="text-sm">Present (8+ hrs)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-yellow-500"></div>
                    <span className="text-sm">Half Day (&lt;8 hrs)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-red-500"></div>
                    <span className="text-sm">Absent</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-blue-500"></div>
                    <span className="text-sm">Leave/Holiday</span>
                  </div>
                </div>

                {/* Custom Calendar Grid */}
                <div className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">
                      {format(currentMonth, 'MMMM yyyy')}
                    </h3>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentMonth(new Date())}
                      >
                        Today
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Calendar Grid */}
                  <div className="grid grid-cols-7 gap-2">
                    {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                      <div key={day} className="text-center text-sm font-semibold text-gray-600 py-2">
                        {day}
                      </div>
                    ))}
                    {eachDayOfInterval({
                      start: startOfMonth(currentMonth),
                      end: endOfMonth(currentMonth)
                    }).map((date, idx) => {
                      const color = getCalendarDayColor(date);
                      const dayRecord = attendanceRecords.find(r => isSameDay(new Date(r.date), date));

                      return (
                        <button
                          key={idx}
                          onClick={() => handleDayClick(date)}
                          className={`
                            aspect-square p-2 rounded-lg border-2 transition-all
                            ${isSameMonth(date, currentMonth) ? 'opacity-100' : 'opacity-30'}
                            ${isToday(date) ? 'border-blue-500 font-bold' : 'border-transparent'}
                            ${color ? 'cursor-pointer hover:scale-105' : ''}
                          `}
                          style={{
                            backgroundColor: color || undefined,
                            color: color ? 'white' : undefined,
                          }}
                        >
                          <div className="text-sm">{format(date, 'd')}</div>
                          {dayRecord && (
                            <div className="text-xs mt-1">
                              {dayRecord.workHours > 0 ? `${dayRecord.workHours.toFixed(1)}h` : ''}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Monthly Report Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Monthly Report
              </CardTitle>
              <CardDescription>Summary for {format(currentMonth, 'MMMM yyyy')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">Total Days</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalDays}</p>
                </div>
                <div className="p-4 bg-green-50 rounded-lg">
                  <p className="text-sm text-gray-600">Attendance %</p>
                  <p className="text-2xl font-bold text-green-600">{stats.attendancePercentage.toFixed(1)}%</p>
                </div>
                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="text-sm text-gray-600">Total Hours</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.totalWorkHours.toFixed(0)}</p>
                </div>
                <div className="p-4 bg-orange-50 rounded-lg">
                  <p className="text-sm text-gray-600">Avg Hours/Day</p>
                  <p className="text-2xl font-bold text-orange-600">{stats.avgWorkHours.toFixed(1)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Mark Attendance Dialog (for Leads/Managers) */}
      <Dialog open={showMarkAttendanceDialog} onOpenChange={setShowMarkAttendanceDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Mark Team Attendance</DialogTitle>
            <DialogDescription>
              Select attendance status for each team member
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="attendance-date">Date *</Label>
              <Input
                id="attendance-date"
                type="date"
                value={markAttendanceData.date}
                onChange={(e) => {
                  setMarkAttendanceData({ ...markAttendanceData, date: e.target.value });
                  // Fetch shifts for the new date
                  fetchTeamShiftsForDate(e.target.value);
                }}
                className="max-w-xs"
              />
            </div>

            <Separator />

            {teamMembers.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Team Members</p>
                {teamMembers.map((member) => {
                  const shift = teamShifts[member.uid];
                  const selectedDate = new Date(markAttendanceData.date);
                  const dayOfWeek = selectedDate.getDay();
                  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

                  return (
                    <div key={member.uid} className="flex items-center gap-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium text-gray-900 dark:text-gray-100">{member.name}</p>
                          {shift ? (
                            <Badge variant="outline" className="text-xs bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800">
                              <Clock className="h-3 w-3 mr-1" />
                              {shift.shift_type.charAt(0).toUpperCase() + shift.shift_type.slice(1)} ({shift.start_time} - {shift.end_time})
                            </Badge>
                          ) : isWeekend ? (
                            <Badge variant="outline" className="text-xs bg-orange-50 dark:bg-orange-950 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800">
                              <CalendarIcon className="h-3 w-3 mr-1" />
                              Weekend
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs bg-red-50 dark:bg-red-900 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800">
                              <AlertCircle className="h-3 w-3 mr-1" />
                              No Shift Assigned
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">{member.designation} - {member.department}</p>
                      </div>
                      <div className="w-48 flex-shrink-0">
                        <Select
                          value={teamAttendanceMap[member.uid] || 'present'}
                          onValueChange={(value) => {
                            setTeamAttendanceMap({
                              ...teamAttendanceMap,
                              [member.uid]: value as AttendanceRecord['status']
                            });
                          }}
                          disabled={!shift && !isWeekend}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="present">Present</SelectItem>
                            <SelectItem value="half-day">Half Day</SelectItem>
                            <SelectItem value="absent">Absent</SelectItem>
                            <SelectItem value="on-leave">On Leave</SelectItem>
                            <SelectItem value="week-off">Week Off</SelectItem>
                            <SelectItem value="comp-off">Comp Off</SelectItem>
                            <SelectItem value="holiday">Holiday</SelectItem>
                          </SelectContent>
                        </Select>
                        {(!shift && !isWeekend) && (
                          <p className="text-xs text-red-600 mt-1">Cannot mark – no shift</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                <Users className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <p>No team members found</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowMarkAttendanceDialog(false);
              resetMarkAttendanceForm();
            }}>
              Cancel
            </Button>
            <Button onClick={handleMarkAttendance} disabled={loading || teamMembers.length === 0}>
              {loading ? 'Saving...' : 'Mark Attendance'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Attendance Dialog (for Managers/HR) */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Attendance</DialogTitle>
            <DialogDescription>
              Correct attendance record - changes will be logged
            </DialogDescription>
          </DialogHeader>
          {editingRecord && (
            <div className="space-y-4 py-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">Editing attendance for</p>
                <p className="font-semibold">{editingRecord.userName}</p>
                <p className="text-sm text-gray-600">{format(new Date(editingRecord.date), 'MMMM dd, yyyy')}</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-status">Status</Label>
                <Select
                  value={editingRecord.status}
                  onValueChange={(value: any) => setEditingRecord({ ...editingRecord, status: value })}
                >
                  <SelectTrigger id="edit-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="present">Present</SelectItem>
                    <SelectItem value="absent">Absent</SelectItem>
                    <SelectItem value="half-day">Half Day</SelectItem>
                    <SelectItem value="on-leave">On Leave</SelectItem>
                    <SelectItem value="week-off">Week Off</SelectItem>
                    <SelectItem value="comp-off">Comp Off</SelectItem>
                    <SelectItem value="holiday">Holiday</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowEditDialog(false);
              setEditingRecord(null);
            }}>
              Cancel
            </Button>
            <Button onClick={handleEditAttendance} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Day Details Dialog */}
      <Dialog open={showDayDetailsDialog} onOpenChange={setShowDayDetailsDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Day Details</DialogTitle>
            <DialogDescription>
              Attendance records for selected day
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {selectedDayRecords.length > 0 ? (
              selectedDayRecords.map(record => (
                <div key={record.id} className="p-4 border rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">{record.userName}</p>
                    <Badge className={getStatusBadge(record.status)}>
                      {record.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-gray-600">Check In:</span>
                      <span className="ml-2 font-medium">{record.checkIn || '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Check Out:</span>
                      <span className="ml-2 font-medium">{record.checkOut || '-'}</span>
                    </div>
                    <div className="col-span-2">
                      <span className="text-gray-600">Work Hours:</span>
                      <span className="ml-2 font-medium">{record.workHours?.toFixed(2) || '0'} hrs</span>
                    </div>
                    {record.notes && (
                      <div className="col-span-2">
                        <span className="text-gray-600">Notes:</span>
                        <p className="mt-1 text-gray-800">{record.notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-gray-600">
                No attendance records for this day
              </div>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setShowDayDetailsDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

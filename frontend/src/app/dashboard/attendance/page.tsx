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
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet';
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
import { LoadingState } from '@/components/common/LoadingState';
import {
  Clock,
  Calendar as CalendarIcon,
  CheckCircle2,
  XCircle,
  AlertCircle,
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
      return 'on-leave';
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
  created_at?: string;
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
  const [exportingTeam, setExportingTeam] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportRange, setExportRange] = useState<{ start: string; end: string }>({
    start: format(startOfMonth(new Date()), 'yyyy-MM-dd'),
    end: format(endOfMonth(new Date()), 'yyyy-MM-dd'),
  });
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
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [editingRecord, setEditingRecord] = useState<AttendanceRecord | null>(null);
  const [selectedDayRecords, setSelectedDayRecords] = useState<AttendanceRecord[]>([]);

  // Filters
  const [filterStartDate, setFilterStartDate] = useState(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
  const [filterEndDate, setFilterEndDate] = useState(format(endOfMonth(new Date()), 'yyyy-MM-dd'));

  const isLead = userData?.role === 'lead';
  const isManager = userData?.role === 'manager' || userData?.role === 'director';
  const isSuperAdmin = userData?.role === 'super_admin';
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const canMarkAttendance = isLead || isManager || isHR;
  const canEditAttendance = isManager || isHR;
  const canExportTeam = isSuperAdmin || isManager || isHR;

  useEffect(() => {
    if (canMarkAttendance && user) {
      fetchTeamMembers();
    }
  }, [canMarkAttendance, user]);

  useEffect(() => {
    if (user) {
      fetchAttendanceRecords();
    }
  }, [user, selectedEmployee, filterStartDate, filterEndDate, teamMembers]);

  const fetchTeamMembers = async () => {
    // Fetch full reporting tree (all nested reportees) so managers/directors can mark for every subordinate.
    const fetchReportees = async (uid: string, token: string | undefined) => {
      if (!token) return [];
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

    try {
      const token = await user?.getIdToken();
      if (!token || !userData?.uid) return;

      const allMembers: TeamMember[] = [];
      const visited = new Set<string>();
      const seenMembers = new Set<string>([userData.uid]);
      const queue: string[] = [userData.uid];

      while (queue.length > 0) {
        const current = queue.shift();
        if (!current || visited.has(current)) continue;
        visited.add(current);

        const reportees: TeamMember[] = await fetchReportees(current, token);
        reportees.forEach((member) => {
          if (!member.uid || seenMembers.has(member.uid)) {
            return;
          }
          seenMembers.add(member.uid);
          allMembers.push(member);
          queue.push(member.uid);
        });
      }

      setTeamMembers(allMembers);
    } catch (error) {
      console.error('Error fetching team members:', error);
    }
  };

  const fetchAttendanceRecords = async () => {
    setLoading(true);
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
    } finally {
      setLoading(false);
    }
  };

  const fetchTeamShiftsForDate = async (date: string) => {
    try {
      const token = await user?.getIdToken();
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

            const validShift = shifts.find(
              (s: any) => s.shift_date === date && s.status === 'approved'
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
    const dateObj = new Date(markAttendanceData.date);
    const selectedMembers = teamMembers.filter((m) => selectedMemberIds.includes(m.uid));
    const invalidMembers = selectedMembers.filter(m => {
      const shift = teamShifts[m.uid];
      const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
      return !shift && !isWeekend;
    });

    if (selectedMembers.length === 0) {
      toast.error('Please select at least one employee');
      return;
    }

    if (invalidMembers.length > 0) {
      toast.error(
        `Cannot submit: no shift assigned for ${invalidMembers.map(m => m.name).join(', ')}`
      );
      return;
    }

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      // Build submit map from visible team members so default "present"
      // is persisted even when user doesn't manually change each select.
      const effectiveAttendanceMap: Record<string, AttendanceRecord['status']> = {};
      selectedMembers.forEach((member) => {
        const shift = teamShifts[member.uid];
        const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
        if (!shift && !isWeekend) return; // Skip disabled members
        effectiveAttendanceMap[member.uid] = teamAttendanceMap[member.uid] || 'present';
      });

      if (Object.keys(effectiveAttendanceMap).length === 0) {
        toast.error('No eligible team members to mark attendance');
        setLoading(false);
        return;
      }

      const promises = Object.entries(effectiveAttendanceMap).map(async ([userId, status]) => {
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

      toast.success(`Attendance marked successfully for ${Object.keys(effectiveAttendanceMap).length} team member(s)!`);
      setShowMarkAttendanceDialog(false);
      resetMarkAttendanceForm();
      setTeamAttendanceMap({});
      setSelectedMemberIds([]);
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
    setSelectedMemberIds([]);
  };

  const handleDayClick = (date: Date) => {
    const latest = getLatestRecordForDate(date);
    setSelectedDayRecords(latest ? [latest] : []);
    setShowDayDetailsDialog(true);
  };

  const exportTeamAttendanceExcel = async (start: string, end: string) => {
    if (!start || !end) {
      toast.error('Please select start and end dates');
      return;
    }
    setExportingTeam(true);
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        startDate: start,
        endDate: end,
      });
      const response = await fetch(
        `${API_BASE_URL}/reports/attendance/team-export?${params.toString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to export attendance');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attendance_team_${start}_to_${end}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Team attendance exported');
    } catch (error) {
      console.error('Export team attendance error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to export attendance');
    } finally {
      setExportingTeam(false);
    }
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

  const getLatestRecordForDate = (date: Date): AttendanceRecord | undefined => {
    const dayRecords = attendanceRecords.filter(r =>
      isSameDay(new Date(r.date), date)
    );
    if (dayRecords.length === 0) return undefined;

    return dayRecords.reduce((latest, current) => {
      const latestTime = new Date(latest.created_at ?? 0).getTime();
      const currentTime = new Date(current.created_at ?? 0).getTime();
      return currentTime > latestTime ? current : latest;
    });
  };

  const getCalendarDayColor = (date: Date) => {
    const record = getLatestRecordForDate(date);
    if (!record) return undefined;

    switch (record.status) {
      case 'present':
        if (record.workHours != null && record.workHours < 8) {
          return '#eab308';
        }
        return '#22c55e';
      case 'half-day':
        return '#eab308';
      case 'absent':
        return '#ef4444';
      case 'on-leave':
      case 'holiday':
      case 'week-off':
      case 'comp-off':
        return '#3b82f6';
      default:
        return undefined;
    }
  };

  const calculateStats = (): AttendanceStats => {
    const totalDays = attendanceRecords.length;
    const presentDays = attendanceRecords.filter(r => r.status === 'present').length;
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
              const initialMap: Record<string, AttendanceRecord['status']> = {};
              const initialSelected: string[] = [];
              const selectedDate = new Date(markAttendanceData.date);
              const dayOfWeek = selectedDate.getDay();
              const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
              teamMembers.forEach(member => {
                initialMap[member.uid] = 'present';
                const shift = teamShifts[member.uid];
                if (shift || isWeekend) {
                  initialSelected.push(member.uid);
                }
              });
              setTeamAttendanceMap(initialMap);
              setSelectedMemberIds(initialSelected);
              fetchTeamShiftsForDate(markAttendanceData.date);
              setShowMarkAttendanceDialog(true);
            }}>
              <Users className="h-4 w-4 mr-2" />
              Mark Team Attendance
            </Button>
          )}
          {canExportTeam && (
            <Button variant="outline" onClick={() => setShowExportDialog(true)} disabled={exportingTeam}>
              <FileText className="h-4 w-4 mr-2" />
              Export Team (Excel)
            </Button>
          )}
        </div>
      </div>

      {/* Monthly Stats */}
      {selectedEmployee === 'me' && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-6">
              {/* Attendance Rate */}
              <div className="flex items-center gap-3 pr-6 border-r">
                <div className="p-2 bg-green-100 rounded-full">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500">Attendance Rate</p>
                  <p className="text-2xl font-bold text-green-600">{stats.attendancePercentage.toFixed(1)}%</p>
                  <p className="text-xs text-gray-400">{format(currentMonth, 'MMMM yyyy')}</p>
                </div>
              </div>

              {/* Stats Row */}
              <div className="flex flex-1 items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-8 bg-green-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Present</p>
                    <p className="text-xl font-bold text-gray-900">{stats.presentDays}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="w-2 h-8 bg-red-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Absent</p>
                    <p className="text-xl font-bold text-gray-900">{stats.absentDays}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="w-2 h-8 bg-yellow-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Half Day</p>
                    <p className="text-xl font-bold text-gray-900">{stats.halfDays}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="w-2 h-8 bg-blue-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Leaves</p>
                    <p className="text-xl font-bold text-gray-900">{stats.leaves}</p>
                  </div>
                </div>

                <div className="pl-4 border-l flex items-center gap-2">
                  <div className="w-2 h-8 bg-purple-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Total Hours</p>
                    <p className="text-xl font-bold text-gray-900">{stats.totalWorkHours.toFixed(0)}h</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="w-2 h-8 bg-orange-500 rounded-full" />
                  <div>
                    <p className="text-xs text-gray-500">Avg / Day</p>
                    <p className="text-xl font-bold text-gray-900">{stats.avgWorkHours.toFixed(1)}h</p>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}


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
              {loading && attendanceRecords.length === 0 ? (
                <LoadingState label="Loading attendance records" />
              ) : attendanceRecords.length > 0 ? (
                <div className="space-y-4">
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
                      const dayRecord = getLatestRecordForDate(date);

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

      {/* Mark Attendance Sheet */}
      <Sheet open={showMarkAttendanceDialog} onOpenChange={setShowMarkAttendanceDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Mark Team Attendance</SheetTitle>
              <SheetDescription className="mt-1">
                Select attendance status for each team member
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="attendance-date">Date *</Label>
              <Input
                id="attendance-date"
                type="date"
                value={markAttendanceData.date}
                onChange={(e) => {
                  setMarkAttendanceData({ ...markAttendanceData, date: e.target.value });
                  fetchTeamShiftsForDate(e.target.value);
                }}
                className="max-w-xs"
              />
            </div>

            <Separator />

            {teamMembers.length > 0 ? (
              <div className="space-y-4">
                <div className="sticky top-0 bg-white py-2 z-10 flex items-center justify-between">
                  <p className="text-sm font-medium text-gray-700">Team Members</p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const selectedDate = new Date(markAttendanceData.date);
                        const dayOfWeek = selectedDate.getDay();
                        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                        const ids = teamMembers
                          .filter((m) => {
                            const shift = teamShifts[m.uid];
                            return !!shift || isWeekend;
                          })
                          .map((m) => m.uid);
                        setSelectedMemberIds(ids);
                      }}
                    >
                      Select All
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedMemberIds([])}
                    >
                      Clear
                    </Button>
                  </div>
                </div>
                {teamMembers.map((member) => {
                  const shift = teamShifts[member.uid];
                  const selectedDate = new Date(markAttendanceData.date);
                  const dayOfWeek = selectedDate.getDay();
                  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                  const canSelect = !!shift || isWeekend;
                  const isSelected = selectedMemberIds.includes(member.uid);

                  return (
                    <div
                      key={member.uid}
                      className="p-4 bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={!canSelect}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedMemberIds((prev) => [...prev, member.uid]);
                              } else {
                                setSelectedMemberIds((prev) => prev.filter((id) => id !== member.uid));
                              }
                            }}
                            className="mt-1 h-4 w-4 rounded border-gray-300"
                          />
                          <div className="flex flex-col gap-1">
                            <p className="font-semibold text-gray-900 text-sm">{member.name}</p>
                            <p className="text-xs text-gray-500">{member.designation} • {member.department}</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {shift ? (
                            <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200 flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {shift.shift_type.charAt(0).toUpperCase() + shift.shift_type.slice(1)} ({shift.start_time} - {shift.end_time})
                            </Badge>
                          ) : isWeekend ? (
                            <Badge variant="outline" className="text-xs bg-orange-50 text-orange-700 border-orange-200 flex items-center gap-1">
                              <CalendarIcon className="h-3 w-3" />
                              Weekend
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200 flex items-center gap-1">
                              <AlertCircle className="h-3 w-3" />
                              No Shift
                            </Badge>
                          )}
                        </div>
                      </div>

                      <div className="space-y-2 pt-3 mt-3 border-t border-gray-100">
                        <Label htmlFor={`attendance-${member.uid}`} className="text-xs font-semibold">
                          Attendance Status
                        </Label>
                        <Select
                          value={teamAttendanceMap[member.uid] || 'present'}
                          onValueChange={(value) => {
                            setTeamAttendanceMap({
                              ...teamAttendanceMap,
                              [member.uid]: value as AttendanceRecord['status'],
                            });
                          }}
                          disabled={!canSelect || !isSelected}
                        >
                          <SelectTrigger id={`attendance-${member.uid}`}>
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
                        {!canSelect && (
                          <p className="text-xs text-red-600 font-medium">Cannot mark – no shift assigned</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-600">
                <Users className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <p>No team members found</p>
              </div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowMarkAttendanceDialog(false); resetMarkAttendanceForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleMarkAttendance} disabled={loading || teamMembers.length === 0 || selectedMemberIds.length === 0}>
              {loading ? 'Saving...' : 'Mark Attendance'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Edit Attendance Dialog */}
      <Sheet open={showEditDialog} onOpenChange={setShowEditDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Edit Attendance</SheetTitle>
              <SheetDescription className="mt-1">
                Correct attendance record — changes will be logged
              </SheetDescription>
            </SheetHeader>
          </div>

          {editingRecord && (
            <div className="p-6 space-y-5">
              <div className="p-4 bg-gray-50 border border-gray-100 rounded-lg">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Editing attendance for</p>
                <p className="font-semibold text-gray-900 mt-1">{editingRecord.userName}</p>
                <p className="text-sm text-gray-500">{format(new Date(editingRecord.date), 'MMMM dd, yyyy')}</p>
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

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowEditDialog(false); setEditingRecord(null); }}>
              Cancel
            </Button>
            <Button onClick={handleEditAttendance} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Day Details Dialog */}
      <Sheet open={showDayDetailsDialog} onOpenChange={setShowDayDetailsDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Day Details</SheetTitle>
              <SheetDescription className="mt-1">
                Attendance records for the selected day
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-4">
            {selectedDayRecords.length > 0 ? (
              selectedDayRecords.map(record => (
                <div key={record.id} className="p-4 border border-gray-100 rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-gray-900">{record.userName}</p>
                    <Badge className={getStatusBadge(record.status)}>
                      {record.status}
                    </Badge>
                  </div>
                  <Separator />
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="space-y-1">
                      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Check In</p>
                      <p className="font-medium text-gray-900">{record.checkIn || '-'}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Check Out</p>
                      <p className="font-medium text-gray-900">{record.checkOut || '-'}</p>
                    </div>
                    <div className="space-y-1 col-span-2">
                      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Work Hours</p>
                      <p className="font-medium text-gray-900">{record.workHours?.toFixed(2) || '0'} hrs</p>
                    </div>
                    {record.notes && (
                      <div className="space-y-1 col-span-2">
                        <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Notes</p>
                        <p className="text-gray-800 bg-gray-50 p-2 rounded">{record.notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-gray-600">
                <CalendarIcon className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <p>No attendance records for this day</p>
              </div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end">
            <Button onClick={() => setShowDayDetailsDialog(false)}>Close</Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Export Team Dialog */}
      <Sheet open={showExportDialog} onOpenChange={setShowExportDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '480px', maxWidth: '480px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Export Team Attendance</SheetTitle>
              <SheetDescription className="mt-1">
                Choose the date range for the Excel report.
              </SheetDescription>
            </SheetHeader>
          </div>
          <div className="p-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="export-start">From Date</Label>
              <Input
                id="export-start"
                type="date"
                value={exportRange.start}
                onChange={(e) => setExportRange((prev) => ({ ...prev, start: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="export-end">To Date</Label>
              <Input
                id="export-end"
                type="date"
                value={exportRange.end}
                onChange={(e) => setExportRange((prev) => ({ ...prev, end: e.target.value }))}
              />
            </div>
          </div>
          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => setShowExportDialog(false)}>Cancel</Button>
            <Button
              onClick={() => {
                exportTeamAttendanceExcel(exportRange.start, exportRange.end);
                setFilterStartDate(exportRange.start);
                setFilterEndDate(exportRange.end);
                setShowExportDialog(false);
              }}
              disabled={exportingTeam}
            >
              {exportingTeam ? 'Exporting...' : 'Export Excel'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

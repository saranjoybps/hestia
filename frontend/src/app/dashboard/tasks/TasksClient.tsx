'use client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  Plus,
  Calendar as CalendarIcon,
  User,
  Paperclip,
  AlertCircle,
  Clock,
  CheckCircle2,
  Eye,
  Edit,
  Trash2,
  GripVertical
} from 'lucide-react';
import { format, isPast, parseISO } from 'date-fns';

interface Task {
  id: string;
  title: string;
  description: string;
  assigneeId: string;
  assigneeName: string;
  assigneeEmail: string;
  department?: string;
  assigneeRole?: string;
  createdBy: string;
  createdByName: string;
  dueDate?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'todo' | 'in_progress' | 'review' | 'completed';
  attachments: string[];
  createdAt: string;
  updatedAt?: string;
}

interface Employee {
  uid: string;
  name: string;
  email: string;
  role?: string;
  department?: string;
  designation?: string;
}

interface InitialData {
  user: { uid: string; name: string; role: string; department: string };
  tasks: Task[];
  employees: Employee[];
}

export default function TasksPage({ initialData }: { initialData: InitialData }) {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<Task[]>(initialData.tasks);
  const [employees, setEmployees] = useState<Employee[]>(initialData.employees);
  const [draggedTask, setDraggedTask] = useState<Task | null>(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('all');
  const [selectedDepartment, setSelectedDepartment] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [search, setSearch] = useState('');

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    assigneeId: '',
    dueDate: '',
    priority: 'medium' as Task['priority'],
  });

  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [viewingTask, setViewingTask] = useState<Task | null>(null);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);

  // Role and scope are server-rendered with the initial task data.
  const currentUid = initialData.user.uid || userData?.uid || '';
  const role = (initialData.user.role || userData?.role || 'employee').toLowerCase();
  const canCreate = ['lead', 'manager', 'director', 'hr', 'super_admin'].includes(role);
  const canManage = canCreate;
  const departments = [...new Set(tasks.map((task) => task.department).filter((department): department is string => !!department))].sort();
  const employeeChoices = canCreate ? employees : [...new Map(tasks.map((task) => [task.assigneeId, { uid: task.assigneeId, name: task.assigneeName, email: task.assigneeEmail, department: task.department }])).values()];

  // Keep SSR choices for instant rendering, then silently refresh them when a
  // drawer opens so long-lived client-side navigation cannot leave a stale team.
  const refreshAssignees = async () => {
    try {
      const token = await user?.getIdToken();
      if (!token) return;
      const response = await fetch(`${API_BASE_URL}/tasks/assignees`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      });
      if (response.ok) {
        const freshEmployees = await response.json();
        if (Array.isArray(freshEmployees)) setEmployees(freshEmployees);
      }
    } catch {
      // Keep the server-rendered list if the background refresh is unavailable.
    }
  };

  const columns: { id: Task['status']; title: string; icon: any }[] = [
    { id: 'todo', title: 'To Do', icon: AlertCircle },
    { id: 'in_progress', title: 'In Progress', icon: Clock },
    { id: 'review', title: 'Review', icon: Eye },
    { id: 'completed', title: 'Completed', icon: CheckCircle2 },
  ];

  const handleCreateTask = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Get assignee details
      const assignee = employees.find(e => e.uid === formData.assigneeId);
      if (!assignee) {
        throw new Error('Assignee not found');
      }

      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          dueDate: formData.dueDate || null,
          assigneeName: assignee.name,
          assigneeEmail: assignee.email,
          createdBy: initialData.user.uid,
          createdByName: initialData.user.name,
          status: 'todo',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create task');
      }

      toast.success('Task created successfully!');
      const createdTask = await response.json();
      setTasks((current) => [createdTask, ...current]);
      setShowCreateDialog(false);
      resetForm();
    } catch (error) {
      console.error('Create task error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTask = async () => {
    if (!editingTask) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Get assignee details if changed
      let updateData: any = { ...formData };
      updateData.dueDate = formData.dueDate || null;
      if (formData.assigneeId !== editingTask.assigneeId) {
        const assignee = employees.find(e => e.uid === formData.assigneeId);
        if (assignee) {
          updateData.assigneeName = assignee.name;
          updateData.assigneeEmail = assignee.email;
        }
      }

      const response = await fetch(
        `${API_BASE_URL}/tasks/${editingTask.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(updateData),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update task');
      }

      toast.success('Task updated successfully!');
      const updatedTask = await response.json();
      setTasks((current) => current.map((task) => task.id === updatedTask.id ? updatedTask : task));
      setShowEditDialog(false);
      setEditingTask(null);
      resetForm();
    } catch (error) {
      console.error('Update task error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update task');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTask = async () => {
    if (!deletingTask) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/tasks/${deletingTask.id}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete task');
      }

      toast.success('Task deleted successfully!');
      setTasks((current) => current.filter((task) => task.id !== deletingTask.id));
      setShowDeleteDialog(false);
      setDeletingTask(null);
    } catch (error) {
      console.error('Delete task error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete task');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (taskId: string, newStatus: Task['status']) => {
    const previousTasks = tasks;
    setTasks((current) => current.map((task) => task.id === taskId ? { ...task, status: newStatus, updatedAt: new Date().toISOString() } : task));
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/tasks/${taskId}/status`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ status: newStatus }),
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail || 'Failed to update task status');
      }

      const updatedTask: Task = await response.json();
      setTasks((current) => current.map((task) => task.id === taskId ? updatedTask : task));
    } catch (error) {
      setTasks(previousTasks);
      console.error('Status change error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update task status');
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      assigneeId: '',
      dueDate: '',
      priority: 'medium',
    });
  };

  const openEditDialog = (task: Task) => {
    void refreshAssignees();
    setEditingTask(task);
    setFormData({
      title: task.title,
      description: task.description,
      assigneeId: task.assigneeId,
      dueDate: task.dueDate || '',
      priority: task.priority,
    });
    setShowEditDialog(true);
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      low: 'bg-gray-100 text-gray-800 border-gray-300',
      medium: 'bg-blue-100 text-blue-800 border-blue-300',
      high: 'bg-orange-100 text-orange-800 border-orange-300',
      urgent: 'bg-red-100 text-red-800 border-red-300',
    };
    return colors[priority] || colors.medium;
  };

  const getPriorityCardColor = (priority: string) => {
    const colors: Record<string, string> = {
      low: 'border-l-4 border-l-gray-400',
      medium: 'border-l-4 border-l-blue-500',
      high: 'border-l-4 border-l-orange-500',
      urgent: 'border-l-4 border-l-red-500',
    };
    return colors[priority] || colors.medium;
  };

  const isOverdue = (dueDate?: string, status?: Task['status']) => {
    if (!dueDate) return false;
    if (status === 'completed') return false;
    return isPast(parseISO(dueDate)) && new Date(dueDate).toDateString() !== new Date().toDateString();
  };

  const getTasksByStatus = (status: Task['status']) => {
    return tasks.filter((task) => {
      if (task.status !== status) return false;
      if (selectedEmployeeId !== 'all' && task.assigneeId !== selectedEmployeeId) return false;
      if (selectedDepartment !== 'all' && task.department !== selectedDepartment) return false;
      if (priorityFilter !== 'all' && task.priority !== priorityFilter) return false;
      const query = search.trim().toLowerCase();
      if (query && !`${task.title} ${task.description} ${task.assigneeName} ${task.department || ''}`.toLowerCase().includes(query)) return false;
      return true;
    }).sort((a, b) => {
      const aDue = a.dueDate || '9999-12-31';
      const bDue = b.dueDate || '9999-12-31';
      return aDue.localeCompare(bDue) || b.createdAt.localeCompare(a.createdAt);
    });
  };

  const activeTaskCount = tasks.filter((task) => task.status !== 'completed').length;
  const overdueTaskCount = tasks.filter((task) => isOverdue(task.dueDate, task.status)).length;
  const completedTaskCount = tasks.filter((task) => task.status === 'completed').length;

  const handleDragStart = (task: Task) => {
    if (!canManage && task.assigneeId !== currentUid) return;
    setDraggedTask(task);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (status: Task['status']) => {
    if (draggedTask && draggedTask.status !== status) {
      handleStatusChange(draggedTask.id, status);
    }
    setDraggedTask(null);
  };

  const TaskCard = ({ task }: { task: Task }) => {
    const initials = task.assigneeName
      ? task.assigneeName.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()
      : '?';

    return (
      <Card
        className={`${canManage || task.assigneeId === currentUid ? 'cursor-grab active:cursor-grabbing' : ''} hover:shadow-md transition-shadow ${getPriorityCardColor(task.priority)} mb-3 border border-slate-200 rounded-xl`}
        draggable={canManage || task.assigneeId === currentUid}
        onDragStart={() => handleDragStart(task)}
        onDragEnd={() => setDraggedTask(null)}
      >
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex min-w-0 items-start gap-2">
              <Avatar className="h-8 w-8"><AvatarFallback className="text-xs">{initials}</AvatarFallback></Avatar>
              <div className="min-w-0"><p className="line-clamp-2 text-sm font-semibold text-slate-900">{task.title}</p><p className="mt-1 truncate text-xs text-slate-500">{task.assigneeName}{task.department ? ` · ${task.department}` : ''}</p></div>
            </div>
            {(canManage || task.assigneeId === currentUid) && <GripVertical className="h-4 w-4 shrink-0 text-slate-300" />}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={getPriorityColor(task.priority)}>{task.priority}</Badge>
            {task.dueDate ? (
              <span className={`inline-flex items-center gap-1 text-xs ${isOverdue(task.dueDate, task.status) ? 'text-red-700' : 'text-slate-500'}`}><CalendarIcon className="h-3 w-3" />{format(parseISO(task.dueDate), 'MMM d')}</span>
            ) : <span className="text-xs text-slate-400">No due date</span>}
          </div>
          <div className="flex items-center justify-between border-t pt-2">
            <div className="flex min-w-0 items-center gap-2">
              {(canManage || task.assigneeId === currentUid) && <Select value={task.status} onValueChange={(value) => void handleStatusChange(task.id, value as Task['status'])}><SelectTrigger className="h-8 w-32 text-xs" aria-label={`Change status for ${task.title}`}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="todo">To Do</SelectItem><SelectItem value="in_progress">In Progress</SelectItem><SelectItem value="review">Review</SelectItem><SelectItem value="completed">Completed</SelectItem></SelectContent></Select>}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-slate-600 hover:text-slate-900"
                onClick={() => {
                  setViewingTask(task);
                  setShowViewDialog(true);
                }}
              >
                <Eye className="h-4 w-4" />
              </Button>
              {canManage && (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-slate-600 hover:text-slate-900"
                    onClick={() => openEditDialog(task)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  {canCreate && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => {
                        setDeletingTask(task);
                        setShowDeleteDialog(true);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Task Management</h1>
          <p className="text-gray-600 mt-1">Organize and track tasks with Kanban board</p>
        </div>
        {canCreate && <Button onClick={() => { setShowCreateDialog(true); void refreshAssignees(); }}><Plus className="mr-2 h-4 w-4" />Create Task</Button>}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: 'Tasks in scope', value: tasks.length, icon: GripVertical, color: 'text-slate-600 bg-slate-100' },
          { label: 'Active', value: activeTaskCount, icon: Clock, color: 'text-blue-700 bg-blue-50' },
          { label: 'Overdue', value: overdueTaskCount, icon: AlertCircle, color: 'text-red-700 bg-red-50' },
          { label: 'Completed', value: completedTaskCount, icon: CheckCircle2, color: 'text-emerald-700 bg-emerald-50' },
        ].map((metric) => {
          const MetricIcon = metric.icon;
          return <Card key={metric.label} className="rounded-xl border-slate-200 shadow-sm"><CardContent className="flex items-center justify-between p-4"><div><p className="text-sm text-slate-500">{metric.label}</p><p className="mt-1 text-2xl font-semibold text-slate-900">{metric.value}</p></div><span className={`rounded-lg p-2 ${metric.color}`}><MetricIcon className="h-5 w-5" /></span></CardContent></Card>;
        })}
      </div>

      <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-4">
        <Input className="min-w-56 flex-1" placeholder="Search tasks, assignees, departments" value={search} onChange={(event) => setSearch(event.target.value)} />
        <Select value={priorityFilter} onValueChange={setPriorityFilter}><SelectTrigger className="w-40" aria-label="Filter tasks by priority"><SelectValue placeholder="All priorities" /></SelectTrigger><SelectContent><SelectItem value="all">All priorities</SelectItem><SelectItem value="urgent">Urgent</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="low">Low</SelectItem></SelectContent></Select>
        {canCreate && <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}><SelectTrigger className="w-52" aria-label="Filter tasks by employee"><SelectValue placeholder="All employees" /></SelectTrigger><SelectContent><SelectItem value="all">All employees</SelectItem>{employeeChoices.map((employee) => <SelectItem key={employee.uid} value={employee.uid}>{employee.name}{employee.department ? ` · ${employee.department}` : ''}</SelectItem>)}</SelectContent></Select>}
        {canCreate && departments.length > 0 && <Select value={selectedDepartment} onValueChange={setSelectedDepartment}><SelectTrigger className="w-48" aria-label="Filter tasks by department"><SelectValue placeholder="All departments" /></SelectTrigger><SelectContent><SelectItem value="all">All departments</SelectItem>{departments.map((department) => <SelectItem key={department} value={department}>{department}</SelectItem>)}</SelectContent></Select>}
      </div>

      {/* Kanban Board */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {columns.map((column) => {
          const columnTasks = getTasksByStatus(column.id);
          const Icon = column.icon;

          return (
            <div
              key={column.id}
              className="flex flex-col"
            >
              <Card className="flex-1">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      {column.title}
                    </span>
                    <Badge variant="outline" className="ml-2">
                      {columnTasks.length}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent
                  className={`min-h-[400px] max-h-[calc(100vh-300px)] overflow-y-auto transition-colors ${draggedTask ? 'bg-slate-50' : ''}`}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(column.id)}
                >
                  {columnTasks.length > 0 ? (
                    columnTasks.map((task) => (
                      <TaskCard key={task.id} task={task} />
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                      <Icon className="h-12 w-12 mb-2 opacity-50" />
                      <p className="text-sm">No tasks</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          );
        })}
        </div>

      {/* Create/Edit Task Dialog */}
      <Sheet open={showCreateDialog || showEditDialog} onOpenChange={(open) => {
        if (!open) { setShowCreateDialog(false); setShowEditDialog(false); setEditingTask(null); resetForm(); }
      }}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">{editingTask ? 'Edit Task' : 'Create New Task'}</SheetTitle>
              <SheetDescription className="mt-1">
                {editingTask ? 'Update task details' : 'Create a new task and assign it to a team member'}
              </SheetDescription>
            </SheetHeader>
          </div>
          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input id="title" placeholder="Task title..." value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" placeholder="Task description..." value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={4} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="assignee">Assignee *</Label>
                <Select value={formData.assigneeId} onValueChange={(value) => setFormData({ ...formData, assigneeId: value })}>
                  <SelectTrigger id="assignee"><SelectValue placeholder="Select assignee" /></SelectTrigger>
                  <SelectContent>
                    {employees.map((emp) => (
                      <SelectItem key={emp.uid} value={emp.uid}>
                        <div className="flex flex-col">
                          <span>{emp.name}</span>
                          <span className="text-xs text-gray-500">{emp.designation} - {emp.department}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="due-date">Due Date</Label>
                <Input id="due-date" type="date" value={formData.dueDate}
                  onChange={(e) => setFormData({ ...formData, dueDate: e.target.value })}
                  />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="priority">Priority *</Label>
              <Select value={formData.priority} onValueChange={(value: any) => setFormData({ ...formData, priority: value })}>
                <SelectTrigger id="priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low"><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-gray-400" />Low</div></SelectItem>
                  <SelectItem value="medium"><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-blue-500" />Medium</div></SelectItem>
                  <SelectItem value="high"><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-orange-500" />High</div></SelectItem>
                  <SelectItem value="urgent"><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500" />Urgent</div></SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); setShowEditDialog(false); setEditingTask(null); resetForm(); }}>Cancel</Button>
            <Button onClick={editingTask ? handleUpdateTask : handleCreateTask} disabled={loading || !formData.title.trim() || !formData.assigneeId}>
              {editingTask ? 'Update Task' : 'Create Task'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Task Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">{viewingTask?.title}</SheetTitle>
              {viewingTask && (
                <div className="flex gap-2 mt-2">
                  <Badge className={getPriorityColor(viewingTask.priority)}>{viewingTask.priority.toUpperCase()}</Badge>
                  <Badge variant="outline">{viewingTask.status.replace('_', ' ').toUpperCase()}</Badge>
                </div>
              )}
            </SheetHeader>
          </div>
          {viewingTask && (
            <div className="p-6 space-y-5">
              {viewingTask.description && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Description</p>
                  <p className="text-gray-800 whitespace-pre-wrap bg-gray-50 border border-gray-100 p-3 rounded-lg text-sm leading-relaxed">
                    {viewingTask.description}
                  </p>
                </div>
              )}
              <Separator />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Assignee</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs">{viewingTask.assigneeName.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="text-sm font-medium">{viewingTask.assigneeName}</p>
                      <p className="text-xs text-gray-500">{viewingTask.assigneeEmail}</p>
                    </div>
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Created By</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs">{viewingTask.createdByName.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                    </Avatar>
                    <p className="text-sm font-medium">{viewingTask.createdByName}</p>
                  </div>
                </div>
                {viewingTask.dueDate && (
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Due Date</p>
                    <div className={`flex items-center gap-2 mt-1 text-sm ${isOverdue(viewingTask.dueDate, viewingTask.status) ? 'text-red-600 font-semibold' : 'text-gray-700'}`}>
                      <CalendarIcon className="h-4 w-4" />
                      <span>{format(parseISO(viewingTask.dueDate), 'MMMM dd, yyyy')}{isOverdue(viewingTask.dueDate, viewingTask.status) && ' (Overdue)'}</span>
                    </div>
                  </div>
                )}
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Created</p>
                  <p className="text-sm text-gray-700 mt-1">{format(new Date(viewingTask.createdAt), 'MMM dd, yyyy HH:mm')}</p>
                </div>
              </div>
              {viewingTask.attachments.length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Attachments</p>
                    <div className="space-y-2">
                      {viewingTask.attachments.map((attachment, index) => (
                        <a key={index} href={attachment} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800">
                          <Paperclip className="h-3 w-3" />
                          {attachment}
                        </a>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {viewingTask.updatedAt && (
                <p className="text-xs text-gray-400">Last updated: {format(new Date(viewingTask.updatedAt), 'MMM dd, yyyy HH:mm')}</p>
              )}
            </div>
          )}
          <div className="p-6 border-t bg-gray-50 flex justify-end">
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Delete Confirmation Dialog */}
      <Sheet open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Delete Task</SheetTitle>
              <SheetDescription className="mt-1">
                Are you sure you want to delete this task? This action cannot be undone.
              </SheetDescription>
            </SheetHeader>
          </div>
          {deletingTask && (
            <div className="p-6">
              <div className="p-4 bg-red-50 border border-red-100 rounded-lg space-y-1">
                <p className="font-semibold text-gray-900">{deletingTask.title}</p>
                <p className="text-sm text-gray-600">Assigned to {deletingTask.assigneeName}</p>
              </div>
            </div>
          )}
          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowDeleteDialog(false); setDeletingTask(null); }}>Cancel</Button>
            <Button onClick={handleDeleteTask} disabled={loading} className="bg-red-600 hover:bg-red-700">
              Delete Task
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

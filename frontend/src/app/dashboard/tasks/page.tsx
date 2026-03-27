'use client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { useState, useEffect } from 'react';
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

export default function TasksPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [draggedTask, setDraggedTask] = useState<Task | null>(null);

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
    attachments: [] as string[],
  });

  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [viewingTask, setViewingTask] = useState<Task | null>(null);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);

  // Permissions
  const canCreate = ['lead', 'manager', 'director', 'hr', 'super_admin'].includes(userData?.role || '');

  const columns: { id: Task['status']; title: string; icon: any }[] = [
    { id: 'todo', title: 'To Do', icon: AlertCircle },
    { id: 'in_progress', title: 'In Progress', icon: Clock },
    { id: 'review', title: 'Review', icon: Eye },
    { id: 'completed', title: 'Completed', icon: CheckCircle2 },
  ];

  useEffect(() => {
    if (user) {
      fetchTasks();
      if (canCreate) {
        fetchEmployees();
      }
    }
  }, [user, canCreate, userData?.uid]);

  const fetchTasks = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data: Task[] = await response.json();
        setTasks(data);
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const token = await user?.getIdToken();
      if (!token || !userData?.uid) return;

      // Lead can assign only to reporting employees.
      if (userData.role === 'lead') {
        const response = await fetch(`${API_BASE_URL}/users/${userData.uid}/reportees`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          const reportees: Employee[] = Array.isArray(data) ? data : [];
          setEmployees(reportees.filter((emp) => emp.role === 'employee'));
        }
        return;
      }

      const response = await fetch(`${API_BASE_URL}/users/`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setEmployees(data.users || []);
      }
    } catch (error) {
      console.error('Error fetching employees:', error);
    }
  };

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
          assigneeName: assignee.name,
          assigneeEmail: assignee.email,
          createdBy: userData?.uid,
          createdByName: userData?.name,
          status: 'todo',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create task');
      }

      toast.success('Task created successfully!');
      setShowCreateDialog(false);
      resetForm();
      fetchTasks();
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
      setShowEditDialog(false);
      setEditingTask(null);
      resetForm();
      fetchTasks();
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
      setShowDeleteDialog(false);
      setDeletingTask(null);
      fetchTasks();
    } catch (error) {
      console.error('Delete task error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete task');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (taskId: string, newStatus: Task['status']) => {
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
        throw new Error('Failed to update task status');
      }

      fetchTasks();
      toast.success('Task status updated!');
    } catch (error) {
      console.error('Status change error:', error);
      toast.error('Failed to update task status');
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      assigneeId: '',
      dueDate: '',
      priority: 'medium',
      attachments: [],
    });
  };

  const openEditDialog = (task: Task) => {
    setEditingTask(task);
    setFormData({
      title: task.title,
      description: task.description,
      assigneeId: task.assigneeId,
      dueDate: task.dueDate || '',
      priority: task.priority,
      attachments: task.attachments,
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
    if (status !== 'completed') {
      return tasks.filter(task => task.status === status);
    }

    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    return tasks
      .filter((task) => {
        if (task.status !== 'completed') return false;
        const completionTime = new Date(task.updatedAt || task.createdAt);
        return completionTime >= sevenDaysAgo;
      })
      .sort((a, b) => {
        const aTime = new Date(a.updatedAt || a.createdAt).getTime();
        const bTime = new Date(b.updatedAt || b.createdAt).getTime();
        return bTime - aTime;
      });
  };

  const handleDragStart = (task: Task) => {
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
        className={`cursor-move hover:shadow-lg transition-all duration-150 ${getPriorityCardColor(task.priority)} mb-2 border border-slate-200 rounded-xl`}
        draggable
        onDragStart={() => handleDragStart(task)}
      >
        <CardContent className="px-2 py-1 h-[60px] flex flex-col justify-between space-y-1">
          {/* Header: assignee avatar + name, task title as subtitle */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="h-8 w-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center text-xs font-semibold">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-900 truncate">{task.assigneeName}</p>
                <p className="text-xs text-slate-600 truncate">{task.title}</p>
              </div>
            </div>
            <GripVertical className="h-4 w-4 text-slate-300 flex-shrink-0" />
          </div>

          {/* Footer: due date left, actions right */}
          <div className="flex items-center justify-between gap-2">
            {task.dueDate ? (
              <div className={`inline-flex items-center gap-2 text-[11px] px-2 py-1 rounded-full ${isOverdue(task.dueDate, task.status) ? 'bg-red-50 text-red-700' : 'bg-slate-50 text-slate-700'}`}>
                <CalendarIcon className="h-3 w-3" />
                <span>{format(parseISO(task.dueDate), 'MMM dd, yyyy')}</span>
              </div>
            ) : (
              <span className="text-[11px] text-slate-500">No due date</span>
            )}

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
              {(canCreate || task.assigneeId === userData?.uid) && (
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
        {canCreate && (
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Task
          </Button>
        )}
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
                  className="min-h-[400px] max-h-[calc(100vh-300px)] overflow-y-auto"
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
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
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
                          <span className="text-xs text-gray-500">{emp.designation} • {emp.department}</span>
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
                  min={format(new Date(), 'yyyy-MM-dd')} />
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
            <div className="space-y-2">
              <Label htmlFor="attachments">Attachments</Label>
              <Input id="attachments" type="text" placeholder="Add attachment URLs (comma-separated)"
                value={formData.attachments.join(', ')}
                onChange={(e) => setFormData({ ...formData, attachments: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
              <p className="text-xs text-gray-500">Enter attachment URLs separated by commas</p>
            </div>
          </div>
          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); setShowEditDialog(false); setEditingTask(null); resetForm(); }}>Cancel</Button>
            <Button onClick={editingTask ? handleUpdateTask : handleCreateTask} disabled={loading || !formData.title || !formData.assigneeId}>
              {loading ? 'Saving...' : editingTask ? 'Update Task' : 'Create Task'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Task Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
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
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
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
              {loading ? 'Deleting...' : 'Delete Task'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

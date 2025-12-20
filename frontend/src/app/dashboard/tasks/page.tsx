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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
  const canCreate = ['lead', 'manager', 'director', 'hr'].includes(userData?.role || '');

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
  }, [user]);

  const fetchTasks = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setTasks(data);
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const token = await user?.getIdToken();
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

  const isOverdue = (dueDate?: string) => {
    if (!dueDate) return false;
    return isPast(parseISO(dueDate)) && new Date(dueDate).toDateString() !== new Date().toDateString();
  };

  const getTasksByStatus = (status: Task['status']) => {
    return tasks.filter(task => task.status === status);
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

  const TaskCard = ({ task }: { task: Task }) => (
    <Card 
      className={`cursor-move hover:shadow-md transition-shadow ${getPriorityCardColor(task.priority)} mb-3`}
      draggable
      onDragStart={() => handleDragStart(task)}
    >
      <CardContent className="pt-4 pb-3 px-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <h4 className="font-semibold text-sm mb-1 line-clamp-2">{task.title}</h4>
            <Badge className={`${getPriorityColor(task.priority)} text-xs`}>
              {task.priority.toUpperCase()}
            </Badge>
          </div>
          <GripVertical className="h-4 w-4 text-gray-400 flex-shrink-0" />
        </div>

        {task.description && (
          <p className="text-xs text-gray-600 mb-3 line-clamp-2">{task.description}</p>
        )}

        <div className="space-y-2">
          {task.dueDate && (
            <div className={`flex items-center gap-1 text-xs ${isOverdue(task.dueDate) ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>
              <CalendarIcon className="h-3 w-3" />
              {format(parseISO(task.dueDate), 'MMM dd, yyyy')}
              {isOverdue(task.dueDate) && <span className="ml-1">(Overdue)</span>}
            </div>
          )}

          <div className="flex items-center gap-1 text-xs text-gray-600">
            <User className="h-3 w-3" />
            {task.assigneeName}
          </div>

          {task.attachments.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-gray-600">
              <Paperclip className="h-3 w-3" />
              {task.attachments.length} attachment{task.attachments.length > 1 ? 's' : ''}
            </div>
          )}
        </div>

        <Separator className="my-3" />

        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs flex-1"
            onClick={() => {
              setViewingTask(task);
              setShowViewDialog(true);
            }}
          >
            <Eye className="h-3 w-3 mr-1" />
            View
          </Button>
          {(canCreate || task.assigneeId === userData?.uid) && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs flex-1"
                onClick={() => openEditDialog(task)}
              >
                <Edit className="h-3 w-3 mr-1" />
                Edit
              </Button>
              {canCreate && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={() => {
                    setDeletingTask(task);
                    setShowDeleteDialog(true);
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );

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
      <Dialog open={showCreateDialog || showEditDialog} onOpenChange={(open) => {
        if (!open) {
          setShowCreateDialog(false);
          setShowEditDialog(false);
          setEditingTask(null);
          resetForm();
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingTask ? 'Edit Task' : 'Create New Task'}</DialogTitle>
            <DialogDescription>
              {editingTask ? 'Update task details' : 'Create a new task and assign it to a team member'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                placeholder="Task title..."
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Task description..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="assignee">Assignee *</Label>
                <Select 
                  value={formData.assigneeId} 
                  onValueChange={(value) => setFormData({ ...formData, assigneeId: value })}
                >
                  <SelectTrigger id="assignee">
                    <SelectValue placeholder="Select assignee" />
                  </SelectTrigger>
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
                <Input
                  id="due-date"
                  type="date"
                  value={formData.dueDate}
                  onChange={(e) => setFormData({ ...formData, dueDate: e.target.value })}
                  min={format(new Date(), 'yyyy-MM-dd')}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="priority">Priority *</Label>
              <Select 
                value={formData.priority} 
                onValueChange={(value: any) => setFormData({ ...formData, priority: value })}
              >
                <SelectTrigger id="priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-gray-400"></div>
                      Low
                    </div>
                  </SelectItem>
                  <SelectItem value="medium">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                      Medium
                    </div>
                  </SelectItem>
                  <SelectItem value="high">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                      High
                    </div>
                  </SelectItem>
                  <SelectItem value="urgent">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500"></div>
                      Urgent
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="attachments">Attachments</Label>
              <Input
                id="attachments"
                type="text"
                placeholder="Add attachment URLs (comma-separated)"
                value={formData.attachments.join(', ')}
                onChange={(e) => setFormData({ 
                  ...formData, 
                  attachments: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                })}
              />
              <p className="text-xs text-gray-500">Enter attachment URLs separated by commas</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              setShowEditDialog(false);
              setEditingTask(null);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button 
              onClick={editingTask ? handleUpdateTask : handleCreateTask}
              disabled={loading || !formData.title || !formData.assigneeId}
            >
              {loading ? 'Saving...' : editingTask ? 'Update Task' : 'Create Task'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Task Dialog */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {viewingTask?.title}
            </DialogTitle>
          </DialogHeader>
          {viewingTask && (
            <div className="space-y-4 py-4">
              <div className="flex gap-2">
                <Badge className={getPriorityColor(viewingTask.priority)}>
                  {viewingTask.priority.toUpperCase()}
                </Badge>
                <Badge variant="outline">
                  {viewingTask.status.replace('_', ' ').toUpperCase()}
                </Badge>
              </div>

              {viewingTask.description && (
                <>
                  <Separator />
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Description</h4>
                    <p className="text-gray-800 whitespace-pre-wrap">{viewingTask.description}</p>
                  </div>
                </>
              )}

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-semibold text-sm mb-2">Assignee</h4>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs">
                        {viewingTask.assigneeName.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="text-sm font-medium">{viewingTask.assigneeName}</p>
                      <p className="text-xs text-gray-500">{viewingTask.assigneeEmail}</p>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-2">Created By</h4>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="text-xs">
                        {viewingTask.createdByName.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="text-sm font-medium">{viewingTask.createdByName}</p>
                    </div>
                  </div>
                </div>

                {viewingTask.dueDate && (
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Due Date</h4>
                    <div className={`flex items-center gap-2 ${isOverdue(viewingTask.dueDate) ? 'text-red-600' : 'text-gray-700'}`}>
                      <CalendarIcon className="h-4 w-4" />
                      <span className="text-sm">
                        {format(parseISO(viewingTask.dueDate), 'MMMM dd, yyyy')}
                        {isOverdue(viewingTask.dueDate) && ' (Overdue)'}
                      </span>
                    </div>
                  </div>
                )}

                <div>
                  <h4 className="font-semibold text-sm mb-2">Created</h4>
                  <p className="text-sm text-gray-700">
                    {format(new Date(viewingTask.createdAt), 'MMM dd, yyyy HH:mm')}
                  </p>
                </div>
              </div>

              {viewingTask.attachments.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Attachments</h4>
                    <div className="space-y-2">
                      {viewingTask.attachments.map((attachment, index) => (
                        <a
                          key={index}
                          href={attachment}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800"
                        >
                          <Paperclip className="h-3 w-3" />
                          {attachment}
                        </a>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {viewingTask.updatedAt && (
                <div className="text-xs text-gray-500">
                  Last updated: {format(new Date(viewingTask.updatedAt), 'MMM dd, yyyy HH:mm')}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Task</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this task? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deletingTask && (
            <div className="py-4">
              <div className="p-4 bg-red-50 rounded-lg">
                <p className="font-semibold">{deletingTask.title}</p>
                <p className="text-sm text-gray-600 mt-1">
                  Assigned to {deletingTask.assigneeName}
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowDeleteDialog(false);
              setDeletingTask(null);
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleDeleteTask} 
              disabled={loading}
              className="bg-red-600 hover:bg-red-700"
            >
              {loading ? 'Deleting...' : 'Delete Task'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Megaphone,
  Plus,
  Pin,
  AlertCircle,
  Info,
  AlertTriangle,
  Clock,
  Edit,
  Trash2,
  Eye,
  Calendar,
  Users,
  FileText
} from 'lucide-react';
import { format, isPast, parseISO } from 'date-fns';

interface Announcement {
  id: string;
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  targetAudience: string[];
  expiryDate?: string;
  status: 'draft' | 'published';
  isPinned: boolean;
  createdBy: string;
  createdByName: string;
  createdAt: string;
  updatedAt?: string;
  department?: string;
}

export default function AnnouncementsPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [myAnnouncements, setMyAnnouncements] = useState<Announcement[]>([]);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: 'medium' as Announcement['priority'],
    targetAudience: [] as string[],
    expiryDate: '',
    status: 'published' as 'draft' | 'published',
    isPinned: false,
  });

  const [editingAnnouncement, setEditingAnnouncement] = useState<Announcement | null>(null);
  const [viewingAnnouncement, setViewingAnnouncement] = useState<Announcement | null>(null);
  const [deletingAnnouncement, setDeletingAnnouncement] = useState<Announcement | null>(null);

  // Filters
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Permissions
  const isHR = userData?.role === 'hr' || userData?.role === 'director';
  const canCreate = isHR;

  const departments = [
    'All Departments',
    'Engineering',
    'Product',
    'Design',
    'Marketing',
    'Sales',
    'HR',
    'Finance',
    'Operations',
  ];

  const roles = [
    'All Roles',
    'Employee',
    'Lead',
    'Manager',
    'Director',
    'HR',
  ];

  useEffect(() => {
    if (user) {
      fetchAnnouncements();
      if (canCreate) {
        fetchMyAnnouncements();
      }
    }
  }, [user, priorityFilter, statusFilter]);

  const fetchAnnouncements = async () => {
    try {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({
        ...(priorityFilter !== 'all' && { priority: priorityFilter }),
        ...(statusFilter !== 'all' && { status: statusFilter }),
      });

      const response = await fetch(`${API_BASE_URL}/announcements?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        // Sort: pinned first, then by date
        const sorted = data.sort((a: Announcement, b: Announcement) => {
          if (a.isPinned && !b.isPinned) return -1;
          if (!a.isPinned && b.isPinned) return 1;
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        });
        setAnnouncements(sorted);
      }
    } catch (error) {
      console.error('Error fetching announcements:', error);
    }
  };

  const fetchMyAnnouncements = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/announcements/my-announcements`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setMyAnnouncements(data);
      }
    } catch (error) {
      console.error('Error fetching my announcements:', error);
    }
  };

  const handleCreateAnnouncement = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/announcements`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          createdBy: userData?.uid,
          createdByName: userData?.name,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create announcement');
      }

      toast.success('Announcement created successfully!');
      setShowCreateDialog(false);
      resetForm();
      fetchAnnouncements();
      if (canCreate) fetchMyAnnouncements();
    } catch (error) {
      console.error('Create announcement error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create announcement');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateAnnouncement = async () => {
    if (!editingAnnouncement) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/announcements/${editingAnnouncement.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(formData),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update announcement');
      }

      toast.success('Announcement updated successfully!');
      setShowEditDialog(false);
      setEditingAnnouncement(null);
      resetForm();
      fetchAnnouncements();
      if (canCreate) fetchMyAnnouncements();
    } catch (error) {
      console.error('Update announcement error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update announcement');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAnnouncement = async () => {
    if (!deletingAnnouncement) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/announcements/${deletingAnnouncement.id}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete announcement');
      }

      toast.success('Announcement deleted successfully!');
      setShowDeleteDialog(false);
      setDeletingAnnouncement(null);
      fetchAnnouncements();
      if (canCreate) fetchMyAnnouncements();
    } catch (error) {
      console.error('Delete announcement error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete announcement');
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePin = async (announcement: Announcement) => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/announcements/${announcement.id}/pin`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ isPinned: !announcement.isPinned }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to toggle pin');
      }

      toast.success(announcement.isPinned ? 'Announcement unpinned' : 'Announcement pinned');
      fetchAnnouncements();
      if (canCreate) fetchMyAnnouncements();
    } catch (error) {
      console.error('Toggle pin error:', error);
      toast.error('Failed to toggle pin');
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      priority: 'medium',
      targetAudience: [],
      expiryDate: '',
      status: 'published',
      isPinned: false,
    });
  };

  const openEditDialog = (announcement: Announcement) => {
    setEditingAnnouncement(announcement);
    setFormData({
      title: announcement.title,
      description: announcement.description,
      priority: announcement.priority,
      targetAudience: announcement.targetAudience,
      expiryDate: announcement.expiryDate || '',
      status: announcement.status,
      isPinned: announcement.isPinned,
    });
    setShowEditDialog(true);
  };

  const getPriorityBadge = (priority: string) => {
    const styles: Record<string, { className: string; icon: any }> = {
      low: { className: 'bg-gray-100 text-gray-800', icon: Info },
      medium: { className: 'bg-blue-100 text-blue-800', icon: AlertCircle },
      high: { className: 'bg-orange-100 text-orange-800', icon: AlertTriangle },
      urgent: { className: 'bg-red-100 text-red-800', icon: AlertCircle },
    };
    const style = styles[priority] || styles.medium;
    const Icon = style.icon;
    return (
      <Badge className={style.className}>
        <Icon className="h-3 w-3 mr-1" />
        {priority.charAt(0).toUpperCase() + priority.slice(1)}
      </Badge>
    );
  };

  const isExpired = (expiryDate?: string) => {
    if (!expiryDate) return false;
    return isPast(parseISO(expiryDate));
  };

  const handleTargetAudienceChange = (value: string) => {
    const current = formData.targetAudience;
    if (current.includes(value)) {
      setFormData({ ...formData, targetAudience: current.filter(v => v !== value) });
    } else {
      setFormData({ ...formData, targetAudience: [...current, value] });
    }
  };

  const AnnouncementCard = ({ announcement, showActions = false }: { announcement: Announcement; showActions?: boolean }) => (
    <Card className={`${announcement.isPinned ? 'border-blue-500 border-2' : ''} ${isExpired(announcement.expiryDate) ? 'opacity-60' : ''}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {announcement.isPinned && (
                <Pin className="h-4 w-4 text-blue-600 fill-blue-600" />
              )}
              {getPriorityBadge(announcement.priority)}
              <Badge variant="outline" className={announcement.status === 'published' ? 'bg-green-50' : 'bg-gray-50'}>
                {announcement.status}
              </Badge>
              {isExpired(announcement.expiryDate) && (
                <Badge variant="outline" className="bg-red-50 text-red-700">
                  Expired
                </Badge>
              )}
            </div>
            <CardTitle className="text-xl">{announcement.title}</CardTitle>
            <CardDescription className="mt-2">
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3" />
                  {announcement.createdByName}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {format(new Date(announcement.createdAt), 'MMM dd, yyyy')}
                </span>
                {announcement.expiryDate && (
                  <span className="flex items-center gap-1 text-orange-600">
                    <Clock className="h-3 w-3" />
                    Expires: {format(parseISO(announcement.expiryDate), 'MMM dd, yyyy')}
                  </span>
                )}
              </div>
            </CardDescription>
          </div>
          {showActions && canCreate && announcement.createdBy === userData?.uid && (
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleTogglePin(announcement)}
              >
                <Pin className={`h-4 w-4 ${announcement.isPinned ? 'fill-blue-600 text-blue-600' : ''}`} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => openEditDialog(announcement)}
              >
                <Edit className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDeletingAnnouncement(announcement);
                  setShowDeleteDialog(true);
                }}
              >
                <Trash2 className="h-4 w-4 text-red-600" />
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-gray-700 line-clamp-3 mb-4">{announcement.description}</p>
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-1">
            {announcement.targetAudience.slice(0, 3).map((audience, index) => (
              <Badge key={index} variant="outline" className="text-xs">
                {audience}
              </Badge>
            ))}
            {announcement.targetAudience.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{announcement.targetAudience.length - 3} more
              </Badge>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setViewingAnnouncement(announcement);
              setShowViewDialog(true);
            }}
          >
            <Eye className="h-4 w-4 mr-2" />
            View Details
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Announcements</h1>
          <p className="text-gray-600 mt-1">Stay updated with company news and updates</p>
        </div>
        {canCreate && (
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Announcement
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Announcements ({announcements.length})</TabsTrigger>
          {canCreate && (
            <TabsTrigger value="my-announcements">My Announcements ({myAnnouncements.length})</TabsTrigger>
          )}
        </TabsList>

        {/* All Announcements Tab */}
        <TabsContent value="all" className="space-y-4">
          {/* Filters */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex gap-4">
                <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>

                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Announcements Grid */}
          {announcements.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {announcements.map((announcement) => (
                <AnnouncementCard key={announcement.id} announcement={announcement} />
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center">
                  <Megaphone className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No announcements found</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* My Announcements Tab */}
        {canCreate && (
          <TabsContent value="my-announcements" className="space-y-4">
            {myAnnouncements.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {myAnnouncements.map((announcement) => (
                  <AnnouncementCard key={announcement.id} announcement={announcement} showActions={true} />
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center">
                    <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">You haven't created any announcements yet</p>
                    <Button className="mt-4" onClick={() => setShowCreateDialog(true)}>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Your First Announcement
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        )}
      </Tabs>

      {/* Create/Edit Dialog */}
      <Sheet open={showCreateDialog || showEditDialog} onOpenChange={(open) => {
        if (!open) { setShowCreateDialog(false); setShowEditDialog(false); setEditingAnnouncement(null); resetForm(); }
      }}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">{editingAnnouncement ? 'Edit Announcement' : 'Create New Announcement'}</SheetTitle>
              <SheetDescription className="mt-1">
                {editingAnnouncement ? 'Update announcement details' : 'Create a new announcement for your team'}
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input id="title" placeholder="Announcement title..." value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description *</Label>
              <Textarea id="description" placeholder="Write announcement details..." value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={6} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="priority">Priority *</Label>
                <Select value={formData.priority} onValueChange={(value: any) => setFormData({ ...formData, priority: value })}>
                  <SelectTrigger id="priority"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="expiry-date">Expiry Date (Optional)</Label>
                <Input id="expiry-date" type="date" value={formData.expiryDate}
                  onChange={(e) => setFormData({ ...formData, expiryDate: e.target.value })}
                  min={format(new Date(), 'yyyy-MM-dd')} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Target Audience *</Label>
              <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">Departments</p>
                  {departments.map((dept) => (
                    <div key={dept} className="flex items-center space-x-2">
                      <input type="checkbox" id={`dept-${dept}`}
                        checked={formData.targetAudience.includes(dept)}
                        onChange={() => handleTargetAudienceChange(dept)}
                        className="rounded border-gray-300" />
                      <label htmlFor={`dept-${dept}`} className="text-sm">{dept}</label>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">Roles</p>
                  {roles.map((role) => (
                    <div key={role} className="flex items-center space-x-2">
                      <input type="checkbox" id={`role-${role}`}
                        checked={formData.targetAudience.includes(role)}
                        onChange={() => handleTargetAudienceChange(role)}
                        className="rounded border-gray-300" />
                      <label htmlFor={`role-${role}`} className="text-sm">{role}</label>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <Separator />

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="status">Publish Status</Label>
                  <p className="text-sm text-gray-500">Choose whether to publish or save as draft</p>
                </div>
                <Select value={formData.status} onValueChange={(value: any) => setFormData({ ...formData, status: value })}>
                  <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="pinned">Pin Announcement</Label>
                  <p className="text-sm text-gray-500">Pinned announcements appear at the top</p>
                </div>
                <Switch id="pinned" checked={formData.isPinned}
                  onCheckedChange={(checked) => setFormData({ ...formData, isPinned: checked })} />
              </div>
            </div>
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); setShowEditDialog(false); setEditingAnnouncement(null); resetForm(); }}>
              Cancel
            </Button>
            <Button
              onClick={editingAnnouncement ? handleUpdateAnnouncement : handleCreateAnnouncement}
              disabled={loading || !formData.title || !formData.description || formData.targetAudience.length === 0}
            >
              {loading ? 'Saving...' : editingAnnouncement ? 'Update Announcement' : 'Create Announcement'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl flex items-center gap-2">
                {viewingAnnouncement?.isPinned && <Pin className="h-5 w-5 text-blue-600 fill-blue-600" />}
                {viewingAnnouncement?.title}
              </SheetTitle>
              {viewingAnnouncement && (
                <div className="flex gap-2 mt-2">
                  {getPriorityBadge(viewingAnnouncement.priority)}
                  <Badge variant="outline" className={viewingAnnouncement.status === 'published' ? 'bg-green-50' : 'bg-gray-50'}>
                    {viewingAnnouncement.status}
                  </Badge>
                  {isExpired(viewingAnnouncement.expiryDate) && (
                    <Badge variant="outline" className="bg-red-50 text-red-700">Expired</Badge>
                  )}
                </div>
              )}
            </SheetHeader>
          </div>

          {viewingAnnouncement && (
            <div className="p-6 space-y-5">
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  {viewingAnnouncement.createdByName}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  {format(new Date(viewingAnnouncement.createdAt), 'MMMM dd, yyyy')}
                </span>
                {viewingAnnouncement.expiryDate && (
                  <span className="flex items-center gap-1 text-orange-600">
                    <Clock className="h-4 w-4" />
                    Expires: {format(parseISO(viewingAnnouncement.expiryDate), 'MMMM dd, yyyy')}
                  </span>
                )}
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Description</p>
                <p className="text-gray-800 whitespace-pre-wrap bg-gray-50 border border-gray-100 p-3 rounded-lg text-sm leading-relaxed">
                  {viewingAnnouncement.description}
                </p>
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Target Audience</p>
                <div className="flex flex-wrap gap-2">
                  {viewingAnnouncement.targetAudience.map((audience, index) => (
                    <Badge key={index} variant="outline">{audience}</Badge>
                  ))}
                </div>
              </div>

              {viewingAnnouncement.updatedAt && (
                <p className="text-xs text-gray-400">
                  Last updated: {format(new Date(viewingAnnouncement.updatedAt), 'MMM dd, yyyy HH:mm')}
                </p>
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
              <SheetTitle className="text-xl">Delete Announcement</SheetTitle>
              <SheetDescription className="mt-1">
                Are you sure you want to delete this announcement? This action cannot be undone.
              </SheetDescription>
            </SheetHeader>
          </div>

          {deletingAnnouncement && (
            <div className="p-6">
              <div className="p-4 bg-red-50 border border-red-100 rounded-lg space-y-1">
                <p className="font-semibold text-gray-900">{deletingAnnouncement.title}</p>
                <p className="text-sm text-gray-600">
                  Created on {format(new Date(deletingAnnouncement.createdAt), 'MMM dd, yyyy')}
                </p>
              </div>
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowDeleteDialog(false); setDeletingAnnouncement(null); }}>
              Cancel
            </Button>
            <Button onClick={handleDeleteAnnouncement} disabled={loading} className="bg-red-600 hover:bg-red-700">
              {loading ? 'Deleting...' : 'Delete Announcement'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  Plus,
  Star,
  TrendingUp,
  Award,
  BarChart3,
  Check,
  X,
  Eye,
  Calendar,
  Users,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { format } from 'date-fns';

interface PerformanceReview {
  id: string;
  userId: string;
  userName: string;
  userEmail: string;
  reviewerId: string;
  reviewerName: string;
  reviewerRole: string;
  reviewType: 'positive' | 'negative';
  rating: number;
  context: string;
  reviewDate: string;
  status: 'pending' | 'approved' | 'rejected';
  approvedBy?: string;
  approverName?: string;
  approvalDate?: string;
  createdAt: string;
  department?: string;
  designation?: string;
}

interface Employee {
  uid: string;
  name: string;
  email: string;
  department?: string;
  designation?: string;
}

interface PerformanceStats {
  totalReviews: number;
  pendingApprovals: number;
  approvedReviews: number;
  averageRating: number;
  byDepartment: Record<string, { count: number; avgRating: number }>;
  topPerformers: Array<{ userId: string; userName: string; avgRating: number; reviewCount: number }>;
  ratingDistribution: Record<number, number>;
}

interface InitialData {
  user: { uid: string; name: string; role: string };
  reviews: PerformanceReview[];
  pending: PerformanceReview[];
  employees: Employee[];
  stats: PerformanceStats | null;
}

export default function PerformancePage({ initialData }: { initialData: InitialData }) {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [reviews, setReviews] = useState<PerformanceReview[]>(initialData.reviews);
  const [pendingApprovals, setPendingApprovals] = useState<PerformanceReview[]>(initialData.pending);
  const [employees, setEmployees] = useState<Employee[]>(initialData.employees);
  const [stats, setStats] = useState<PerformanceStats | null>(initialData.stats);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    userId: '',
    reviewType: 'positive' as 'positive' | 'negative',
    rating: 3,
    context: '',
    reviewDate: format(new Date(), 'yyyy-MM-dd'),
  });

  const [viewingReview, setViewingReview] = useState<PerformanceReview | null>(null);
  const [processingReview, setProcessingReview] = useState<PerformanceReview | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Permissions
  const role = initialData.user.role || userData?.role;
  const isLead = role === 'lead';
  const isManager = role === 'manager';
  const isHR = role === 'hr' || role === 'director' || role === 'super_admin';
  const canAccess = ['employee', 'lead', 'manager', 'director', 'hr', 'super_admin'].includes(role || '');
  const canCreateReview = ['lead', 'manager', 'hr', 'director', 'super_admin'].includes(role || '');
  const canApprove = role === 'director' || role === 'super_admin';

  const fetchReviews = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/performance`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setReviews(data);
      }
    } catch (error) {
      console.error('Error fetching reviews:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/performance/pending-approvals`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        const approvals = Array.isArray(data) ? data : (data?.reviews || []);
        setPendingApprovals(approvals);
      } else {
        const error = await response.json().catch(() => null);
        const message = error?.detail || 'Failed to load pending approvals';
        toast.error(message);
      }
    } catch (error) {
      console.error('Error fetching pending approvals:', error);
      toast.error('Failed to load pending approvals');
    }
  };

  const fetchEmployees = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/users?page=1&limit=50`, {
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

  const fetchStats = async () => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/performance/stats`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const handleCreateReview = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Get employee details
      const employee = employees.find(e => e.uid === formData.userId);
      if (!employee) {
        throw new Error('Employee not found');
      }

      const response = await fetch(`${API_BASE_URL}/performance`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          userName: employee.name,
          userEmail: employee.email,
          reviewerId: initialData.user.uid,
          reviewerName: initialData.user.name,
          reviewerRole: initialData.user.role,
          department: employee.department,
          designation: employee.designation,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create review');
      }

      toast.success('Performance review submitted successfully!');
      setShowCreateDialog(false);
      resetForm();
      fetchReviews();
      if (canApprove) fetchPendingApprovals();
    } catch (error) {
      console.error('Create review error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create review');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveReview = async () => {
    if (!processingReview) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/performance/${processingReview.id}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            approvedBy: initialData.user.uid,
            approverName: initialData.user.name,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve review');
      }

      toast.success('Review approved successfully!');
      setShowApproveDialog(false);
      setProcessingReview(null);
      fetchReviews();
      fetchPendingApprovals();
      if (isHR) fetchStats();
    } catch (error) {
      console.error('Approve review error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to approve review');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectReview = async () => {
    if (!processingReview) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `${API_BASE_URL}/performance/${processingReview.id}/reject`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            rejectedBy: initialData.user.uid,
            rejectionReason,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reject review');
      }

      toast.success('Review rejected');
      setShowRejectDialog(false);
      setProcessingReview(null);
      setRejectionReason('');
      fetchReviews();
      fetchPendingApprovals();
    } catch (error) {
      console.error('Reject review error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reject review');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      userId: '',
      reviewType: 'positive',
      rating: 3,
      context: '',
      reviewDate: format(new Date(), 'yyyy-MM-dd'),
    });
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const getReviewTypeIcon = (type: string) => {
    return type === 'positive' ? (
      <ThumbsUp className="h-4 w-4 text-green-600" />
    ) : (
      <ThumbsDown className="h-4 w-4 text-red-600" />
    );
  };

  const renderStars = (rating: number, size: 'sm' | 'md' = 'sm') => {
    const starSize = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5';
    return (
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`${starSize} ${star <= rating
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-gray-300'
              }`}
          />
        ))}
      </div>
    );
  };

  if (userData && !canAccess) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <h1 className="text-2xl font-bold text-red-900">Access denied</h1>
          <p className="mt-2 text-sm text-red-800">
            You don’t have permission to view the Performance module.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Performance Management</h1>
          <p className="text-gray-600 mt-1">Track and manage employee performance reviews</p>
        </div>
        {canCreateReview && (
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Review
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="reviews" className="space-y-4">
        <TabsList>
          <TabsTrigger value="reviews">All Reviews ({reviews.length})</TabsTrigger>
          {canApprove && (
            <TabsTrigger value="approvals">
              Pending Approvals ({pendingApprovals.length})
            </TabsTrigger>
          )}
          {isHR && <TabsTrigger value="reports">Reports & Analytics</TabsTrigger>}
        </TabsList>

        {/* All Reviews Tab */}
        <TabsContent value="reviews" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Reviews</CardTitle>
              <CardDescription>Complete history of performance reviews</CardDescription>
            </CardHeader>
            <CardContent>
              {reviews.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Rating</TableHead>
                        <TableHead>Reviewer</TableHead>
                        <TableHead>Review Date</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {reviews.map((review) => (
                        <TableRow key={review.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className="text-xs">
                                  {review.userName.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="font-medium text-sm">{review.userName}</p>
                                <p className="text-xs text-gray-500">{review.designation}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getReviewTypeIcon(review.reviewType)}
                              <span className="capitalize">{review.reviewType}</span>
                            </div>
                          </TableCell>
                          <TableCell>{renderStars(review.rating)}</TableCell>
                          <TableCell>
                            <div>
                              <p className="text-sm font-medium">{review.reviewerName}</p>
                              <p className="text-xs text-gray-500 capitalize">{review.reviewerRole}</p>
                            </div>
                          </TableCell>
                          <TableCell>{format(new Date(review.reviewDate), 'MMM dd, yyyy')}</TableCell>
                          <TableCell>
                            <Badge className={getStatusBadge(review.status)}>
                              {review.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setViewingReview(review);
                                setShowViewDialog(true);
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Award className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No performance reviews found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pending Approvals Tab */}
        {canApprove && (
          <TabsContent value="approvals" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending Approvals</CardTitle>
                <CardDescription>Reviews awaiting director approval</CardDescription>
              </CardHeader>
              <CardContent>
                {pendingApprovals.length > 0 ? (
                  <div className="space-y-4">
                    {pendingApprovals.map((review) => (
                      <Card key={review.id}>
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <Avatar className="h-12 w-12">
                                <AvatarFallback>
                                  {review.userName.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <h3 className="font-semibold text-lg">{review.userName}</h3>
                                <p className="text-sm text-gray-600">{review.designation} • {review.department}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {getReviewTypeIcon(review.reviewType)}
                              <Badge className={review.reviewType === 'positive' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                                {review.reviewType}
                              </Badge>
                            </div>
                          </div>

                          <div className="grid grid-cols-3 gap-4 mb-4">
                            <div>
                              <p className="text-sm text-gray-600">Rating</p>
                              {renderStars(review.rating, 'md')}
                            </div>
                            <div>
                              <p className="text-sm text-gray-600">Reviewer</p>
                              <p className="font-medium">{review.reviewerName}</p>
                              <p className="text-xs text-gray-500 capitalize">{review.reviewerRole}</p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600">Review Date</p>
                              <p className="font-medium">{format(new Date(review.reviewDate), 'MMM dd, yyyy')}</p>
                            </div>
                          </div>

                          <div className="mb-4">
                            <p className="text-sm text-gray-600 mb-2">Context</p>
                            <p className="text-gray-800 bg-gray-50 p-3 rounded-lg">{review.context}</p>
                          </div>

                          <Separator className="my-4" />

                          <div className="flex gap-3">
                            <Button
                              variant="outline"
                              className="flex-1 border-green-200 hover:bg-green-50"
                              onClick={() => {
                                setProcessingReview(review);
                                setShowApproveDialog(true);
                              }}
                            >
                              <Check className="h-4 w-4 mr-2 text-green-600" />
                              Approve
                            </Button>
                            <Button
                              variant="outline"
                              className="flex-1 border-red-200 hover:bg-red-50"
                              onClick={() => {
                                setProcessingReview(review);
                                setShowRejectDialog(true);
                              }}
                            >
                              <X className="h-4 w-4 mr-2 text-red-600" />
                              Reject
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Check className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No pending approvals</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Reports Tab */}
        {isHR && stats && (
          <TabsContent value="reports" className="space-y-4">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Total Reviews</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.totalReviews}</p>
                    </div>
                    <Award className="h-8 w-8 text-gray-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Pending</p>
                      <p className="text-3xl font-bold text-yellow-600">{stats.pendingApprovals}</p>
                    </div>
                    <Calendar className="h-8 w-8 text-yellow-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Approved</p>
                      <p className="text-3xl font-bold text-green-600">{stats.approvedReviews}</p>
                    </div>
                    <Check className="h-8 w-8 text-green-400" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Avg Rating</p>
                      <p className="text-3xl font-bold text-blue-600">{stats.averageRating.toFixed(1)}</p>
                    </div>
                    <Star className="h-8 w-8 text-yellow-400 fill-yellow-400" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Top Performers */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Top Performers
                </CardTitle>
                <CardDescription>Employees with highest average ratings</CardDescription>
              </CardHeader>
              <CardContent>
                {stats.topPerformers.length > 0 ? (
                  <div className="space-y-3">
                    {stats.topPerformers.map((performer, index) => (
                      <div key={performer.userId} className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm">
                            <span className="text-lg font-bold text-blue-600">#{index + 1}</span>
                          </div>
                          <div>
                            <p className="font-semibold text-gray-900">{performer.userName}</p>
                            <p className="text-sm text-gray-600">{performer.reviewCount} review{performer.reviewCount > 1 ? 's' : ''}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          {renderStars(Math.round(performer.avgRating), 'md')}
                          <span className="text-xl font-bold text-gray-900">{performer.avgRating.toFixed(1)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-600 text-center py-8">No performance data available</p>
                )}
              </CardContent>
            </Card>

            {/* Department Ratings */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Average Ratings by Department
                </CardTitle>
                <CardDescription>Performance breakdown across departments</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(stats.byDepartment).map(([dept, data]) => (
                    <div key={dept} className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="font-medium text-sm mb-1">{dept}</p>
                        <div className="flex items-center gap-3">
                          <div className="w-64 bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full"
                              style={{ width: `${(data.avgRating / 5) * 100}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">{data.count} reviews</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <Star className="h-4 w-4 text-yellow-400 fill-yellow-400" />
                        <span className="font-bold text-lg">{data.avgRating.toFixed(1)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Rating Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Rating Distribution
                </CardTitle>
                <CardDescription>Frequency of each rating level</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[5, 4, 3, 2, 1].map((rating) => {
                    const count = stats.ratingDistribution[rating] || 0;
                    const percentage = stats.totalReviews > 0 ? (count / stats.totalReviews) * 100 : 0;
                    return (
                      <div key={rating} className="flex items-center gap-4">
                        <div className="flex items-center gap-1 w-32">
                          {renderStars(rating)}
                          <span className="text-sm font-medium ml-2">({rating})</span>
                        </div>
                        <div className="flex-1">
                          <div className="w-full bg-gray-200 rounded-full h-6 relative">
                            <div
                              className="bg-blue-500 h-6 rounded-full transition-all duration-300"
                              style={{ width: `${percentage}%` }}
                            />
                            <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700">
                              {count} ({percentage.toFixed(0)}%)
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Create Review Dialog */}
      <Sheet open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Add Performance Review</SheetTitle>
              <SheetDescription className="mt-1">
                Submit a performance review for a team member
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="employee">Employee *</Label>
              <Select
                value={formData.userId}
                onValueChange={(value) => setFormData({ ...formData, userId: value })}
              >
                <SelectTrigger id="employee">
                  <SelectValue placeholder="Select employee" />
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

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="review-type">Review Type *</Label>
                <Select
                  value={formData.reviewType}
                  onValueChange={(value: any) => setFormData({ ...formData, reviewType: value })}
                >
                  <SelectTrigger id="review-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="positive">
                      <div className="flex items-center gap-2">
                        <ThumbsUp className="h-4 w-4 text-green-600" />
                        Positive
                      </div>
                    </SelectItem>
                    <SelectItem value="negative">
                      <div className="flex items-center gap-2">
                        <ThumbsDown className="h-4 w-4 text-red-600" />
                        Negative
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="review-date">Review Date *</Label>
                <Input
                  id="review-date"
                  type="date"
                  value={formData.reviewDate}
                  onChange={(e) => setFormData({ ...formData, reviewDate: e.target.value })}
                  max={format(new Date(), 'yyyy-MM-dd')}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="rating">Rating (1-5) *</Label>
              <div className="flex items-center gap-4">
                <Input
                  id="rating"
                  type="range"
                  min="1"
                  max="5"
                  value={formData.rating}
                  onChange={(e) => setFormData({ ...formData, rating: parseInt(e.target.value) })}
                  className="flex-1"
                />
                <div className="flex items-center gap-2">
                  {renderStars(formData.rating, 'md')}
                  <span className="text-lg font-bold w-8">{formData.rating}</span>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="context">Context *</Label>
              <Textarea
                id="context"
                placeholder="Provide detailed context for this review..."
                value={formData.context}
                onChange={(e) => setFormData({ ...formData, context: e.target.value })}
                rows={6}
              />
            </div>

            {isLead && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  <strong>Note:</strong> As a Lead, your reviews will require Director approval before being finalized.
                </p>
              </div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowCreateDialog(false); resetForm(); }}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateReview}
              disabled={loading || !formData.userId || !formData.context}
            >
              {loading ? 'Submitting...' : 'Submit Review'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* View Review Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Performance Review Details</SheetTitle>
            </SheetHeader>
          </div>

          {viewingReview && (
            <div className="p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-12 w-12">
                    <AvatarFallback>
                      {viewingReview.userName.split(' ').map(n => n[0]).join('')}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="font-semibold text-lg">{viewingReview.userName}</h3>
                    <p className="text-sm text-gray-500">{viewingReview.designation} • {viewingReview.department}</p>
                  </div>
                </div>
                <Badge className={getStatusBadge(viewingReview.status)}>
                  {viewingReview.status}
                </Badge>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Review Type</p>
                  <div className="flex items-center gap-2">
                    {getReviewTypeIcon(viewingReview.reviewType)}
                    <span className="capitalize font-medium">{viewingReview.reviewType}</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Rating</p>
                  {renderStars(viewingReview.rating, 'md')}
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Reviewer</p>
                  <p className="font-medium text-sm">{viewingReview.reviewerName}</p>
                  <p className="text-xs text-gray-500 capitalize">{viewingReview.reviewerRole}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Review Date</p>
                  <p className="font-medium text-sm">{format(new Date(viewingReview.reviewDate), 'MMMM dd, yyyy')}</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Context</p>
                <p className="text-gray-800 bg-gray-50 border border-gray-100 p-4 rounded-lg whitespace-pre-wrap text-sm leading-relaxed">
                  {viewingReview.context}
                </p>
              </div>

              {viewingReview.status === 'approved' && viewingReview.approverName && (
                <div className="p-4 bg-green-50 border border-green-100 rounded-lg">
                  <p className="text-sm text-green-900">
                    Approved by <strong>{viewingReview.approverName}</strong>
                    {viewingReview.approvalDate && ` on ${format(new Date(viewingReview.approvalDate), 'MMM dd, yyyy')}`}
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="p-6 border-t bg-gray-50 flex justify-end">
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Approve Dialog */}
      <Sheet open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Approve Performance Review</SheetTitle>
              <SheetDescription className="mt-1">
                Confirm approval for this performance review
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6">
            {processingReview && (
              <div className="p-4 bg-green-50 border border-green-100 rounded-lg space-y-2">
                <p className="font-semibold text-gray-900">{processingReview.userName}</p>
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  {getReviewTypeIcon(processingReview.reviewType)}
                  <span className="capitalize">{processingReview.reviewType} Review</span>
                  <span className="mx-1">•</span>
                  {renderStars(processingReview.rating)}
                </div>
                <p className="text-sm text-gray-500">By {processingReview.reviewerName}</p>
              </div>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleApproveReview} disabled={loading} className="bg-green-600 hover:bg-green-700">
              {loading ? 'Approving...' : 'Approve Review'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Reject Dialog */}
      <Sheet open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-2xl">
          <div className="p-6 border-b">
            <SheetHeader>
              <SheetTitle className="text-xl">Reject Performance Review</SheetTitle>
              <SheetDescription className="mt-1">
                Provide a reason for rejection
              </SheetDescription>
            </SheetHeader>
          </div>

          <div className="p-6 space-y-5">
            {processingReview && (
              <>
                <div className="p-4 bg-red-50 border border-red-100 rounded-lg space-y-2">
                  <p className="font-semibold text-gray-900">{processingReview.userName}</p>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    {getReviewTypeIcon(processingReview.reviewType)}
                    <span className="capitalize">{processingReview.reviewType} Review</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="rejection-reason">Reason for Rejection *</Label>
                  <Textarea
                    id="rejection-reason"
                    placeholder="Please provide a reason..."
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    rows={4}
                  />
                </div>
              </>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button variant="outline" onClick={() => { setShowRejectDialog(false); setRejectionReason(''); }}>
              Cancel
            </Button>
            <Button
              onClick={handleRejectReview}
              disabled={loading || !rejectionReason}
              className="bg-red-600 hover:bg-red-700"
            >
              {loading ? 'Rejecting...' : 'Reject Review'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

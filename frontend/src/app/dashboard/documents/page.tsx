'use client';

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
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { 
  FileText,
  Plus,
  Download,
  Eye,
  Check,
  X,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Calendar,
  User,
  Briefcase,
  Building2,
  RefreshCw,
  Shield,
} from 'lucide-react';
import { format } from 'date-fns';

interface Employee {
  uid: string;
  name: string;
  email: string;
  department: string;
  designation: string;
  created_at?: string;
}

interface LetterRequest {
  id: string;
  employeeId: string;
  employeeName: string;
  employeeEmail: string;
  department: string;
  designation: string;
  letterType: 'exit' | 'experience' | 'both';
  lastWorkingDay: string;
  reasonForExit?: string;
  additionalComments?: string;
  requestedBy: string;
  requestedByName: string;
  requestedOn: string;
  status: 'pending' | 'approved' | 'rejected';
  approvedBy?: string;
  approverName?: string;
  approvedOn?: string;
  rejectedBy?: string;
  rejectionReason?: string;
  rejectedOn?: string;
  pdfUrl?: string;
  employmentPeriod?: string;
  // Google Drive fields
  experience_letter_link?: string;
  experience_file_id?: string;
  exit_letter_link?: string;
  exit_file_id?: string;
  pdfFiles?: Array<{
    type: string;
    filename: string;
    file_id: string;
    web_view_link: string;
    download_link?: string;
  }>;
}

export default function ExitLettersPage() {
  const { userData, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [requests, setRequests] = useState<LetterRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<LetterRequest[]>([]);
  const [issuedLetters, setIssuedLetters] = useState<LetterRequest[]>([]);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  // Selected items
  const [viewingRequest, setViewingRequest] = useState<LetterRequest | null>(null);
  const [processingRequest, setProcessingRequest] = useState<LetterRequest | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Form data
  const [formData, setFormData] = useState({
    employeeId: '',
    letterType: 'experience' as 'exit' | 'experience' | 'both',
    lastWorkingDay: format(new Date(), 'yyyy-MM-dd'),
    reasonForExit: '',
    additionalComments: '',
  });

  // Permissions
  const isHR = userData?.role === 'hr';
  const isDirector = userData?.role === 'director';
  const hasAccess = isHR || isDirector;

  useEffect(() => {
    if (user && hasAccess) {
      fetchData();
    }
  }, [user, hasAccess]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Fetch employees if HR (for creating requests)
      if (isHR) {
        const empRes = await fetch('http://localhost:8000/api/users/', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (empRes.ok) {
          const data = await empRes.json();
          setEmployees(data.users || []);
        }
      }

      // Fetch all requests
      const reqRes = await fetch('http://localhost:8000/api/letters/requests', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (reqRes.ok) {
        const data = await reqRes.json();
        setRequests(data);
      }

      // Fetch pending requests (for Directors)
      if (isDirector) {
        const pendingRes = await fetch('http://localhost:8000/api/letters/pending', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (pendingRes.ok) {
          const data = await pendingRes.json();
          setPendingRequests(data);
        }
      }

      // Fetch issued letters
      const issuedRes = await fetch('http://localhost:8000/api/letters/issued', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (issuedRes.ok) {
        const data = await issuedRes.json();
        setIssuedLetters(data);
      }

    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to fetch letter data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRequest = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const employee = employees.find(e => e.uid === formData.employeeId);
      
      if (!employee) {
        throw new Error('Employee not found');
      }

      const response = await fetch('http://localhost:8000/api/letters/request', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          employeeId: employee.uid,
          employeeName: employee.name,
          employeeEmail: employee.email,
          department: employee.department,
          designation: employee.designation,
          letterType: formData.letterType,
          lastWorkingDay: formData.lastWorkingDay,
          reasonForExit: formData.reasonForExit,
          additionalComments: formData.additionalComments,
          requestedBy: userData?.uid,
          requestedByName: userData?.name,
          joinDate: employee.created_at,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create request');
      }

      toast.success('Letter request submitted for Director\'s approval');
      setShowCreateDialog(false);
      resetForm();
      fetchData();
    } catch (error) {
      console.error('Create request error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to create request');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!processingRequest) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/letters/approve/${processingRequest.id}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            approvedBy: userData?.uid,
            approverName: userData?.name,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve request');
      }

      toast.success('Letter request approved and PDF generated successfully!');
      setShowApproveDialog(false);
      setProcessingRequest(null);
      fetchData();
    } catch (error) {
      console.error('Approve error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to approve request');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!processingRequest || !rejectionReason) return;

    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/letters/reject/${processingRequest.id}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            rejectedBy: userData?.uid,
            rejectionReason,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reject request');
      }

      toast.success('Letter request rejected');
      setShowRejectDialog(false);
      setProcessingRequest(null);
      setRejectionReason('');
      fetchData();
    } catch (error) {
      console.error('Reject error:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reject request');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (letter: LetterRequest) => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(
        `http://localhost:8000/api/letters/download/${letter.id}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (!response.ok) throw new Error('Failed to download PDF');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${letter.letterType}_letter_${letter.employeeName.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success('PDF downloaded successfully!');
    } catch (error) {
      console.error('Download error:', error);
      toast.error('Failed to download PDF');
    }
  };

  const resetForm = () => {
    setFormData({
      employeeId: '',
      letterType: 'experience',
      lastWorkingDay: format(new Date(), 'yyyy-MM-dd'),
      reasonForExit: '',
      additionalComments: '',
    });
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; icon: any }> = {
      pending: { bg: 'bg-yellow-100 text-yellow-800', icon: Clock },
      approved: { bg: 'bg-green-100 text-green-800', icon: CheckCircle },
      rejected: { bg: 'bg-red-100 text-red-800', icon: XCircle },
    };
    
    const style = styles[status] || styles.pending;
    const Icon = style.icon;
    
    return (
      <Badge className={style.bg}>
        <Icon className="h-3 w-3 mr-1" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const getLetterTypeBadge = (type: string) => {
    const styles: Record<string, string> = {
      exit: 'bg-orange-100 text-orange-800',
      experience: 'bg-blue-100 text-blue-800',
      both: 'bg-purple-100 text-purple-800',
    };
    
    return (
      <Badge className={styles[type] || 'bg-gray-100 text-gray-800'}>
        {type === 'both' ? 'Exit & Experience' : type.charAt(0).toUpperCase() + type.slice(1)}
      </Badge>
    );
  };

  if (!hasAccess) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Access Denied</h2>
          <p className="text-gray-600 mt-2">You don't have permission to access Exit & Experience Letters.</p>
          <p className="text-sm text-gray-500 mt-1">This module is restricted to HR and Directors only.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Exit & Experience Letters</h1>
          <p className="text-gray-600 mt-1">Manage employee exit and experience letter requests</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={fetchData} disabled={loading} variant="outline">
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {isHR && (
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              New Request
            </Button>
          )}
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-900">Module Access</h3>
              <p className="text-sm text-blue-800 mt-1">
                <strong>HR:</strong> Create letter requests for employees • <strong>Directors:</strong> Approve/reject requests and generate PDF letters
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue={isHR ? "requests" : "approvals"} className="space-y-4">
        <TabsList>
          {isHR && (
            <TabsTrigger value="requests">
              <FileText className="h-4 w-4 mr-2" />
              My Requests ({requests.length})
            </TabsTrigger>
          )}
          {isDirector && (
            <TabsTrigger value="approvals">
              <Clock className="h-4 w-4 mr-2" />
              Pending Approvals ({pendingRequests.length})
            </TabsTrigger>
          )}
          <TabsTrigger value="issued">
            <CheckCircle className="h-4 w-4 mr-2" />
            Issued Letters ({issuedLetters.length})
          </TabsTrigger>
        </TabsList>

        {/* My Requests Tab (HR) */}
        {isHR && (
          <TabsContent value="requests" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Letter Requests</CardTitle>
                <CardDescription>Track all letter requests you've created</CardDescription>
              </CardHeader>
              <CardContent>
                {requests.length > 0 ? (
                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Employee</TableHead>
                          <TableHead>Letter Type</TableHead>
                          <TableHead>Last Working Day</TableHead>
                          <TableHead>Requested On</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {requests.map((request) => (
                          <TableRow key={request.id}>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Avatar className="h-8 w-8">
                                  <AvatarFallback className="text-xs">
                                    {request.employeeName.split(' ').map(n => n[0]).join('')}
                                  </AvatarFallback>
                                </Avatar>
                                <div>
                                  <p className="font-medium text-sm">{request.employeeName}</p>
                                  <p className="text-xs text-gray-500">{request.designation}</p>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>{getLetterTypeBadge(request.letterType)}</TableCell>
                            <TableCell>{format(new Date(request.lastWorkingDay), 'MMM dd, yyyy')}</TableCell>
                            <TableCell>{format(new Date(request.requestedOn), 'MMM dd, yyyy')}</TableCell>
                            <TableCell>{getStatusBadge(request.status)}</TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setViewingRequest(request);
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
                    <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600 mb-4">No letter requests yet</p>
                    <Button onClick={() => setShowCreateDialog(true)}>
                      <Plus className="h-4 w-4 mr-2" />
                      Create First Request
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Pending Approvals Tab (Director) */}
        {isDirector && (
          <TabsContent value="approvals" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Pending Approvals</CardTitle>
                <CardDescription>Review and approve letter requests</CardDescription>
              </CardHeader>
              <CardContent>
                {pendingRequests.length > 0 ? (
                  <div className="space-y-4">
                    {pendingRequests.map((request) => (
                      <Card key={request.id} className="border-yellow-200">
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <Avatar className="h-12 w-12">
                                <AvatarFallback>
                                  {request.employeeName.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <h3 className="font-semibold text-lg">{request.employeeName}</h3>
                                <p className="text-sm text-gray-600">{request.designation} • {request.department}</p>
                              </div>
                            </div>
                            {getLetterTypeBadge(request.letterType)}
                          </div>

                          <div className="grid grid-cols-3 gap-4 mb-4">
                            <div>
                              <p className="text-sm text-gray-600 mb-1">Last Working Day</p>
                              <p className="font-medium flex items-center gap-1">
                                <Calendar className="h-4 w-4 text-gray-400" />
                                {format(new Date(request.lastWorkingDay), 'MMM dd, yyyy')}
                              </p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600 mb-1">Requested By</p>
                              <p className="font-medium">{request.requestedByName}</p>
                            </div>
                            <div>
                              <p className="text-sm text-gray-600 mb-1">Requested On</p>
                              <p className="font-medium">{format(new Date(request.requestedOn), 'MMM dd, yyyy')}</p>
                            </div>
                          </div>

                          {request.reasonForExit && (
                            <div className="mb-4">
                              <p className="text-sm text-gray-600 mb-1">Reason for Exit</p>
                              <p className="text-gray-800 bg-gray-50 p-3 rounded-lg text-sm">{request.reasonForExit}</p>
                            </div>
                          )}

                          {request.additionalComments && (
                            <div className="mb-4">
                              <p className="text-sm text-gray-600 mb-1">Additional Comments</p>
                              <p className="text-gray-800 bg-gray-50 p-3 rounded-lg text-sm">{request.additionalComments}</p>
                            </div>
                          )}

                          <Separator className="my-4" />

                          <div className="flex gap-3">
                            <Button
                              className="flex-1 bg-green-600 hover:bg-green-700"
                              onClick={() => {
                                setProcessingRequest(request);
                                setShowApproveDialog(true);
                              }}
                            >
                              <Check className="h-4 w-4 mr-2" />
                              Approve & Generate PDF
                            </Button>
                            <Button
                              variant="outline"
                              className="flex-1 border-red-200 hover:bg-red-50"
                              onClick={() => {
                                setProcessingRequest(request);
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
                    <CheckCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No pending approvals</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* Issued Letters Tab */}
        <TabsContent value="issued" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Issued Letters</CardTitle>
              <CardDescription>Download approved letters</CardDescription>
            </CardHeader>
            <CardContent>
              {issuedLetters.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Letter Type</TableHead>
                        <TableHead>Last Working Day</TableHead>
                        <TableHead>Issued Date</TableHead>
                        <TableHead>Approved By</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {issuedLetters.map((letter) => (
                        <TableRow key={letter.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className="text-xs">
                                  {letter.employeeName.split(' ').map(n => n[0]).join('')}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="font-medium text-sm">{letter.employeeName}</p>
                                <p className="text-xs text-gray-500">{letter.department}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>{getLetterTypeBadge(letter.letterType)}</TableCell>
                          <TableCell>{format(new Date(letter.lastWorkingDay), 'MMM dd, yyyy')}</TableCell>
                          <TableCell>{letter.approvedOn ? format(new Date(letter.approvedOn), 'MMM dd, yyyy') : 'N/A'}</TableCell>
                          <TableCell>{letter.approverName || 'N/A'}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex gap-2 justify-end">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setViewingRequest(letter);
                                  setShowViewDialog(true);
                                }}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              {/* Google Drive View Link */}
                              {(letter.experience_letter_link || letter.exit_letter_link) && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => {
                                    const driveLink = letter.experience_letter_link || letter.exit_letter_link;
                                    window.open(driveLink, '_blank');
                                  }}
                                  className="bg-blue-50 hover:bg-blue-100 border-blue-200"
                                >
                                  <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12.545 10.239v3.821h5.445c-.712 2.315-2.647 3.972-5.445 3.972a6.033 6.033 0 110-12.064c1.498 0 2.866.549 3.921 1.453l2.814-2.814A9.969 9.969 0 0012.545 2C7.021 2 2.543 6.477 2.543 12s4.478 10 10.002 10c8.396 0 10.249-7.85 9.426-11.748l-9.426-.013z"/>
                                  </svg>
                                  Drive
                                </Button>
                              )}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDownload(letter)}
                              >
                                <Download className="h-4 w-4 mr-2" />
                                PDF
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No issued letters yet</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Request Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Letter Request</DialogTitle>
            <DialogDescription>
              Submit a letter request for Director's approval
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="employee">Employee *</Label>
              <Select 
                value={formData.employeeId} 
                onValueChange={(value) => setFormData({ ...formData, employeeId: value })}
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
                <Label htmlFor="letter-type">Letter Type *</Label>
                <Select 
                  value={formData.letterType} 
                  onValueChange={(value: any) => setFormData({ ...formData, letterType: value })}
                >
                  <SelectTrigger id="letter-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="exit">Exit Letter</SelectItem>
                    <SelectItem value="experience">Experience Letter</SelectItem>
                    <SelectItem value="both">Both (Exit & Experience)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="last-working-day">Last Working Day *</Label>
                <Input
                  id="last-working-day"
                  type="date"
                  value={formData.lastWorkingDay}
                  onChange={(e) => setFormData({ ...formData, lastWorkingDay: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="reason">Reason for Exit (Optional)</Label>
              <Textarea
                id="reason"
                placeholder="e.g., Career growth, Personal reasons, Better opportunity..."
                value={formData.reasonForExit}
                onChange={(e) => setFormData({ ...formData, reasonForExit: e.target.value })}
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="comments">Additional Comments (Optional)</Label>
              <Textarea
                id="comments"
                placeholder="Any additional information for the Director..."
                value={formData.additionalComments}
                onChange={(e) => setFormData({ ...formData, additionalComments: e.target.value })}
                rows={3}
              />
            </div>

            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">
                <strong>Note:</strong> This request will be sent to the Director for approval. Once approved, the PDF letter will be automatically generated.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateRequest}
              disabled={loading || !formData.employeeId}
            >
              {loading ? 'Submitting...' : 'Submit Request'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Dialog */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Letter Request Details</DialogTitle>
          </DialogHeader>
          {viewingRequest && (
            <div className="space-y-4 py-4">
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Avatar className="h-12 w-12">
                    <AvatarFallback>
                      {viewingRequest.employeeName.split(' ').map(n => n[0]).join('')}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="font-semibold text-lg">{viewingRequest.employeeName}</h3>
                    <p className="text-sm text-gray-600">{viewingRequest.designation} • {viewingRequest.department}</p>
                  </div>
                </div>
                {getStatusBadge(viewingRequest.status)}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Letter Type</p>
                  {getLetterTypeBadge(viewingRequest.letterType)}
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-1">Last Working Day</p>
                  <p className="font-medium">{format(new Date(viewingRequest.lastWorkingDay), 'MMMM dd, yyyy')}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-1">Requested By</p>
                  <p className="font-medium">{viewingRequest.requestedByName}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-1">Requested On</p>
                  <p className="font-medium">{format(new Date(viewingRequest.requestedOn), 'MMMM dd, yyyy')}</p>
                </div>
              </div>

              {viewingRequest.employmentPeriod && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">Employment Period</p>
                  <p className="font-medium">{viewingRequest.employmentPeriod}</p>
                </div>
              )}

              {viewingRequest.reasonForExit && (
                <div>
                  <p className="text-sm text-gray-600 mb-2">Reason for Exit</p>
                  <p className="text-gray-800 bg-gray-50 p-3 rounded-lg">{viewingRequest.reasonForExit}</p>
                </div>
              )}

              {viewingRequest.additionalComments && (
                <div>
                  <p className="text-sm text-gray-600 mb-2">Additional Comments</p>
                  <p className="text-gray-800 bg-gray-50 p-3 rounded-lg">{viewingRequest.additionalComments}</p>
                </div>
              )}

              {viewingRequest.status === 'approved' && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-900">
                    <strong>Approved by:</strong> {viewingRequest.approverName} on{' '}
                    {viewingRequest.approvedOn && format(new Date(viewingRequest.approvedOn), 'MMMM dd, yyyy')}
                  </p>
                </div>
              )}

              {viewingRequest.status === 'rejected' && viewingRequest.rejectionReason && (
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-sm text-red-900 mb-1">
                    <strong>Rejected by:</strong> {viewingRequest.rejectedBy} on{' '}
                    {viewingRequest.rejectedOn && format(new Date(viewingRequest.rejectedOn), 'MMMM dd, yyyy')}
                  </p>
                  <p className="text-sm text-red-800">
                    <strong>Reason:</strong> {viewingRequest.rejectionReason}
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Approve Dialog */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Letter Request</DialogTitle>
            <DialogDescription>
              Generate and approve the letter PDF
            </DialogDescription>
          </DialogHeader>
          {processingRequest && (
            <div className="py-4">
              <div className="p-4 bg-green-50 rounded-lg space-y-2">
                <p className="font-semibold">{processingRequest.employeeName}</p>
                <div className="flex items-center gap-2">
                  {getLetterTypeBadge(processingRequest.letterType)}
                  <span className="text-sm text-gray-600">Last Working: {format(new Date(processingRequest.lastWorkingDay), 'MMM dd, yyyy')}</span>
                </div>
                <p className="text-sm text-gray-600">Requested by: {processingRequest.requestedByName}</p>
              </div>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mt-4">
                <p className="text-sm text-blue-800">
                  This will generate a formal PDF letter with Joyrts letterhead and your digital signature.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove} disabled={loading} className="bg-green-600 hover:bg-green-700">
              {loading ? 'Processing...' : 'Approve & Generate PDF'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Letter Request</DialogTitle>
            <DialogDescription>
              Provide a reason for rejection
            </DialogDescription>
          </DialogHeader>
          {processingRequest && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-red-50 rounded-lg space-y-2">
                <p className="font-semibold">{processingRequest.employeeName}</p>
                {getLetterTypeBadge(processingRequest.letterType)}
              </div>

              <div className="space-y-2">
                <Label htmlFor="rejection-reason">Reason for Rejection *</Label>
                <Textarea
                  id="rejection-reason"
                  placeholder="Please provide a clear reason for rejecting this request..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={4}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowRejectDialog(false);
              setRejectionReason('');
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleReject} 
              disabled={loading || !rejectionReason}
              className="bg-red-600 hover:bg-red-700"
            >
              {loading ? 'Rejecting...' : 'Reject Request'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

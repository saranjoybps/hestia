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
  SheetFooter,
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
  letterType: string;
  templateKey?: string;
  templateVersion?: number;
  documentData?: Record<string, string>;
  referenceNumber?: string;
  generationStatus?: string;
  lastWorkingDay?: string;
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
  // Offer letter specific fields
  annualSalary?: string;
  startDate?: string;
  probationPeriod?: string;
  noticePeriod?: string;
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

interface TemplateVersion {
  id: string;
  version: number;
  title: string;
  body: string;
  signatureTitle: string;
  fields: Array<{ key: string; label: string; type: string; required: boolean }>;
  status: 'draft' | 'published';
}

interface DocumentTemplate {
  id: string;
  templateKey: string;
  name: string;
  category: string;
  isActive: boolean;
  activeVersion: number | null;
  published: TemplateVersion | null;
  draft: TemplateVersion | null;
}

interface DocumentSettings {
  company_name: string;
  company_address: string;
  company_email: string;
  company_phone: string;
  labour_identification_number: string;
  reference_prefix: string;
}

export interface DocumentsPageData {
  user: { uid: string; name: string; role: string };
  employees: Employee[];
  requests: LetterRequest[];
  pendingRequests: LetterRequest[];
  issuedLetters: LetterRequest[];
  templates: DocumentTemplate[];
  settings: DocumentSettings | null;
}

export default function DocumentsClient({ initialData }: { initialData: DocumentsPageData }) {
  const { userData, user, hasRole } = useAuth();
  const [loading, setLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>(initialData.employees);
  const [requests, setRequests] = useState<LetterRequest[]>(initialData.requests);
  const [pendingRequests, setPendingRequests] = useState<LetterRequest[]>(initialData.pendingRequests);
  const [issuedLetters, setIssuedLetters] = useState<LetterRequest[]>(initialData.issuedLetters);
  const [templates, setTemplates] = useState<DocumentTemplate[]>(initialData.templates);
  const [settings, setSettings] = useState<DocumentSettings | null>(initialData.settings);

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showNewTemplateDialog, setShowNewTemplateDialog] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<DocumentTemplate | null>(null);

  // Selected items
  const [viewingRequest, setViewingRequest] = useState<LetterRequest | null>(null);
  const [processingRequest, setProcessingRequest] = useState<LetterRequest | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Form data
  const [formData, setFormData] = useState({
    employeeId: '',
    letterType: 'offer',
    lastWorkingDay: format(new Date(), 'yyyy-MM-dd'),
    reasonForExit: '',
    additionalComments: '',
    // Offer letter specific fields
    annualSalary: '',
    startDate: format(new Date(), 'yyyy-MM-dd'),
    probationPeriod: 'three months',
    noticePeriod: '45 days',
    documentData: {} as Record<string, string>,
  });

  const [settingsForm, setSettingsForm] = useState<DocumentSettings>({
    company_name: initialData.settings?.company_name || 'Hestia',
    company_address: initialData.settings?.company_address || '',
    company_email: initialData.settings?.company_email || '',
    company_phone: initialData.settings?.company_phone || '',
    labour_identification_number: initialData.settings?.labour_identification_number || '',
    reference_prefix: initialData.settings?.reference_prefix || 'HESTIA/HR',
  });
  const [templateForm, setTemplateForm] = useState({ title: '', body: '', signatureTitle: 'Authorized Signatory', fields: [] as TemplateVersion['fields'] });
  const [newTemplateForm, setNewTemplateForm] = useState({ templateKey: '', name: '', category: 'employment', title: '', body: '', signatureTitle: 'Authorized Signatory' });

  // Permissions
  const effectiveRole = userData?.role || initialData.user.role;
  const isHR = hasRole('hr') || effectiveRole === 'hr';
  const isDirector = hasRole('director') || effectiveRole === 'director';
  const isSuperAdmin = hasRole('super_admin') || effectiveRole === 'super_admin';
  const hasAccess = isHR || isDirector;
  const canManageTemplates = isHR || isDirector || isSuperAdmin;
  const selectedTemplate = templates.find((template) => template.templateKey === formData.letterType && template.isActive && template.published);
  const requiredTemplateFields = selectedTemplate?.published?.fields.filter((field) => field.required) || [];
  const missingTemplateFields = requiredTemplateFields.filter((field) => !String(formData.documentData[field.key] || '').trim());

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();

      // Fetch employees if HR or Director (for creating requests)
      if (isHR || isDirector) {
        const empRes = await fetch(`${API_BASE_URL}/users?page=1&limit=500`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (empRes.ok) {
          const data = await empRes.json();
          setEmployees(data.users || []);
        }
      }

      if (hasAccess) {
        const reqRes = await fetch(`${API_BASE_URL}/letters/requests`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
        if (reqRes.ok) setRequests(await reqRes.json());
      }

      if (isDirector) {
        const pendingRes = await fetch(`${API_BASE_URL}/letters/pending`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (pendingRes.ok) {
          const data = await pendingRes.json();
          setPendingRequests(data);
        } else {
          console.error('Pending approvals fetch failed', pendingRes.status, await pendingRes.text());
          toast.error('Failed to load pending approvals');
        }
      }

      if (hasAccess) {
        const issuedRes = await fetch(`${API_BASE_URL}/letters/issued`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
        if (issuedRes.ok) setIssuedLetters(await issuedRes.json());
      }

      if (canManageTemplates) {
        const [templateRes, settingsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/letters/templates`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }),
          fetch(`${API_BASE_URL}/letters/settings`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }),
        ]);
        if (templateRes.ok) setTemplates(await templateRes.json());
        if (settingsRes.ok) {
          const newSettings = await settingsRes.json();
          setSettings(newSettings);
          setSettingsForm(newSettings);
        }
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

      const response = await fetch(`${API_BASE_URL}/letters/request`, {
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
          templateKey: formData.letterType,
          documentData: formData.documentData,
          lastWorkingDay: ['experience', 'relieving'].includes(formData.letterType) ? formData.documentData.lastWorkingDay : undefined,
          reasonForExit: formData.reasonForExit,
          additionalComments: formData.additionalComments,
          requestedBy: userData?.uid,
          requestedByName: userData?.name,
          // Include offer letter fields if applicable
          ...(formData.letterType === 'offer' && {
            annualSalary: formData.annualSalary,
            startDate: formData.startDate,
            probationPeriod: formData.probationPeriod,
            noticePeriod: formData.noticePeriod,
          }),
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create request');
      }

      toast.success(isDirector ? 'Document generated and issued' : 'Document request submitted for Director approval');
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
        `${API_BASE_URL}/letters/approve/${processingRequest.id}`,
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

      toast.success('Document approved and ready to download');
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
        `${API_BASE_URL}/letters/reject/${processingRequest.id}`,
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
        `${API_BASE_URL}/letters/download/${letter.id}`,
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

  const openTemplateEditor = (template: DocumentTemplate) => {
    const version = template.draft || template.published;
    const body = (version?.body || '').replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n');
    setEditingTemplate(template);
    setTemplateForm({
      title: version?.title || template.name.toUpperCase(),
      body,
      signatureTitle: version?.signatureTitle || 'Authorized Signatory',
      fields: version?.fields.map((field) => ({ ...field })) || [],
    });
    setShowTemplateDialog(true);
  };

  const createCustomTemplate = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/templates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(newTemplateForm),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Could not create template');
      }
      const template = await response.json() as DocumentTemplate;
      setTemplates((current) => [...current, template]);
      setShowNewTemplateDialog(false);
      setNewTemplateForm({ templateKey: '', name: '', category: 'employment', title: '', body: '', signatureTitle: 'Authorized Signatory' });
      openTemplateEditor(template);
      toast.success('Template draft created. Add fields and publish when ready.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not create template');
    } finally {
      setLoading(false);
    }
  };

  const saveTemplateDraft = async () => {
    if (!editingTemplate || !templateForm.title.trim() || !templateForm.body.trim()) return;
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/templates/${editingTemplate.id}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: templateForm.title,
          body: templateForm.body,
          signatureTitle: templateForm.signatureTitle,
          fields: templateForm.fields,
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Could not save template draft');
      }
      toast.success('Template draft saved');
      setShowTemplateDialog(false);
      await fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not save template draft');
    } finally {
      setLoading(false);
    }
  };

  const publishTemplateDraft = async () => {
    if (!editingTemplate?.draft) return;
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/templates/${editingTemplate.id}/versions/${editingTemplate.draft.version}/publish`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Could not publish template');
      }
      toast.success('Template published for new documents');
      setShowTemplateDialog(false);
      await fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not publish template');
    } finally {
      setLoading(false);
    }
  };

  const previewTemplate = async (template: DocumentTemplate, version?: number) => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/templates/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ templateKey: template.templateKey, version }),
      });
      if (!response.ok) throw new Error('Could not generate the template preview');
      const url = URL.createObjectURL(await response.blob());
      window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not generate preview');
    }
  };

  const saveDocumentSettings = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/settings`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          companyName: settingsForm.company_name, companyAddress: settingsForm.company_address,
          companyEmail: settingsForm.company_email, companyPhone: settingsForm.company_phone,
          labourIdentificationNumber: settingsForm.labour_identification_number,
          referencePrefix: settingsForm.reference_prefix,
        }),
      });
      if (!response.ok) throw new Error('Could not save company document settings');
      const saved = await response.json();
      setSettings(saved);
      toast.success('Company document settings saved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not save settings');
    } finally {
      setLoading(false);
    }
  };

  const toggleTemplateActive = async (template: DocumentTemplate) => {
    try {
      const token = await user?.getIdToken();
      const response = await fetch(`${API_BASE_URL}/letters/templates/${template.id}/active?active=${!template.isActive}`, {
        method: 'PATCH', headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Could not update template availability');
      await fetchData();
      toast.success(template.isActive ? 'Template disabled for new requests' : 'Template enabled for new requests');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not update template availability');
    }
  };

  const resetForm = () => {
    setFormData({
      employeeId: '',
      letterType: 'offer',
      lastWorkingDay: format(new Date(), 'yyyy-MM-dd'),
      reasonForExit: '',
      additionalComments: '',
      annualSalary: '',
      startDate: format(new Date(), 'yyyy-MM-dd'),
      probationPeriod: 'three months',
      noticePeriod: '45 days',
      documentData: {},
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
      offer: 'bg-green-100 text-green-800',
    };
    
    return (
      <Badge className={styles[type] || 'bg-gray-100 text-gray-800'}>
        {type === 'both' ? 'Exit & Experience' : type.charAt(0).toUpperCase() + type.slice(1)}
      </Badge>
    );
  };

  if (!hasAccess && !canManageTemplates) {
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
          <h1 className="text-3xl font-bold text-gray-900">Documents & Letters</h1>
          <p className="text-gray-600 mt-1">Create, customize, approve, and issue employee documents</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={fetchData} disabled={loading} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          {(isHR || isDirector) && (
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              New Request
            </Button>
          )}
        </div>
      </div>

      {/* Info Card */}
      {hasAccess && <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-900">Module Access</h3>
              <p className="text-sm text-blue-800 mt-1">
                <strong>HR:</strong> Submit requests for Director approval • <strong>Directors:</strong> Review requests and issue employee documents
              </p>
            </div>
          </div>
        </CardContent>
      </Card>}

      {/* Tabs */}
      <Tabs defaultValue={isHR ? "requests" : isDirector ? "approvals" : "templates"} className="space-y-4">
        <TabsList>
          {(isHR || isDirector) && (
            <TabsTrigger value="requests">
              <FileText className="h-4 w-4 mr-2" />
              {isDirector ? 'All Requests' : 'My Requests'} ({requests.length})
            </TabsTrigger>
          )}
          {isDirector && (
            <TabsTrigger value="approvals">
              <Clock className="h-4 w-4 mr-2" />
              Pending Approvals ({pendingRequests.length})
            </TabsTrigger>
          )}
          {hasAccess && <TabsTrigger value="issued">
            <CheckCircle className="h-4 w-4 mr-2" />
            Issued Letters ({issuedLetters.length})
          </TabsTrigger>}
          {canManageTemplates && <TabsTrigger value="templates"><FileText className="h-4 w-4 mr-2" />Templates</TabsTrigger>}
        </TabsList>

        {/* My Requests Tab (HR & Directors) */}
        {(isHR || isDirector) && (
          <TabsContent value="requests" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Letter Requests</CardTitle>
              <CardDescription>{isDirector ? 'Review requests submitted by HR and other authorized users' : 'Track the requests you have submitted'}</CardDescription>
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
                            <TableCell>{request.lastWorkingDay ? format(new Date(request.lastWorkingDay), 'MMM dd, yyyy') : '—'}</TableCell>
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
                                {request.lastWorkingDay ? format(new Date(request.lastWorkingDay), 'MMM dd, yyyy') : '—'}
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
                              Approve & Issue
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
        {hasAccess && <TabsContent value="issued" className="space-y-4">
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
                          <TableCell>{letter.lastWorkingDay ? format(new Date(letter.lastWorkingDay), 'MMM dd, yyyy') : '—'}</TableCell>
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
        </TabsContent>}
        {canManageTemplates && (
          <TabsContent value="templates" className="space-y-4">
            <Card className="rounded-xl border-slate-200">
              <CardHeader>
                <CardTitle>Company document details</CardTitle>
                <CardDescription>These values populate company fields and reference numbers in generated PDFs.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                {[
                  ['company_name', 'Company legal name'], ['company_address', 'Company address'],
                  ['company_email', 'Official email'], ['company_phone', 'Phone'],
                  ['labour_identification_number', 'Labour Identification Number (optional)'], ['reference_prefix', 'Document reference prefix'],
                ].map(([key, label]) => (
                  <div className="space-y-2" key={key}>
                    <Label htmlFor={`settings-${key}`}>{label}</Label>
                    <Input id={`settings-${key}`} value={settingsForm[key as keyof DocumentSettings] || ''}
                      onChange={(event) => setSettingsForm({ ...settingsForm, [key]: event.target.value })} />
                  </div>
                ))}
                <div className="md:col-span-2 flex justify-end"><Button onClick={saveDocumentSettings} disabled={loading}>Save company details</Button></div>
              </CardContent>
            </Card>
            <Card className="rounded-xl border-slate-200">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3"><CardTitle>Template library</CardTitle><Button size="sm" onClick={() => setShowNewTemplateDialog(true)}><Plus className="mr-2 h-4 w-4" />New template</Button></div>
                <CardDescription>Edit a draft, preview it as a PDF, and publish a new version. Issued documents keep their original version.</CardDescription>
              </CardHeader>
              <CardContent>
                {templates.length ? <div className="space-y-3">
                  {templates.map((template) => (
                    <div key={template.id} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2"><p className="font-medium text-slate-900">{template.name}</p><Badge variant="outline">{template.category.replaceAll('_', ' ')}</Badge><Badge className={template.isActive && template.published ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}>{template.isActive && template.published ? `Published v${template.activeVersion}` : 'Inactive'}</Badge>{template.draft && <Badge className="bg-amber-100 text-amber-800">Draft v{template.draft.version}</Badge>}</div>
                        <p className="mt-1 text-xs text-slate-500">Key: {template.templateKey} · {template.published?.fields.length || template.draft?.fields.length || 0} fields</p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button variant="outline" size="sm" onClick={() => void previewTemplate(template, template.draft?.version || template.activeVersion || undefined)}>Preview</Button>
                        <Button variant="outline" size="sm" onClick={() => void toggleTemplateActive(template)}>{template.isActive ? 'Disable' : 'Enable'}</Button>
                        <Button size="sm" onClick={() => openTemplateEditor(template)}>Customize</Button>
                      </div>
                    </div>
                  ))}
                </div> : <p className="py-8 text-center text-sm text-slate-500">Template catalog is unavailable until the document template migration is applied.</p>}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Create Request Dialog */}
      <Sheet open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-xl">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0">
            <SheetTitle>Create Letter Request</SheetTitle>
            <SheetDescription>
              {isDirector ? 'Create and issue an employee document' : 'Submit an employee document request for Director approval'}
            </SheetDescription>
          </SheetHeader>
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

            <div className="space-y-2">
              <Label htmlFor="letter-type">Document template *</Label>
              <Select value={formData.letterType} onValueChange={(value) => setFormData({ ...formData, letterType: value, documentData: {} })}>
                <SelectTrigger id="letter-type"><SelectValue placeholder="Choose a document type" /></SelectTrigger>
                <SelectContent>
                  {templates.filter((template) => template.isActive && template.published).map((template) => (
                    <SelectItem key={template.id} value={template.templateKey}>{template.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedTemplate?.published?.fields.map((field) => (
              <div className="space-y-2" key={field.key}>
                <Label htmlFor={`document-field-${field.key}`}>{field.label}{field.required ? ' *' : ''}</Label>
                {field.type === 'textarea' ? (
                  <Textarea id={`document-field-${field.key}`} rows={3} value={formData.documentData[field.key] || ''}
                    onChange={(event) => setFormData({ ...formData, documentData: { ...formData.documentData, [field.key]: event.target.value } })} />
                ) : (
                  <Input id={`document-field-${field.key}`} type={field.type === 'date' ? 'date' : 'text'}
                    value={formData.documentData[field.key] || ''}
                    onChange={(event) => setFormData({ ...formData, documentData: { ...formData.documentData, [field.key]: event.target.value } })} />
                )}
              </div>
            ))}
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

            <div className={`rounded-lg border p-3 ${isDirector ? 'border-blue-200 bg-blue-50' : 'border-yellow-200 bg-yellow-50'}`}>
              <p className={`text-sm ${isDirector ? 'text-blue-800' : 'text-yellow-800'}`}>
                <strong>Note:</strong> {isDirector
                  ? 'This document will be created and issued immediately.'
                  : 'This request will be sent to the Director for approval. Once approved, the PDF document will be available to download.'}
              </p>
            </div>
          </div>
          <SheetFooter className="sticky bottom-0 mt-4 flex-col-reverse gap-2 border-t bg-background px-0 pb-0 pt-4 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateRequest}
              disabled={loading || !formData.employeeId || !selectedTemplate || missingTemplateFields.length > 0}
            >
              {isDirector ? 'Create & Issue' : 'Submit Request'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* View Dialog */}
      <Sheet open={showViewDialog} onOpenChange={setShowViewDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-xl">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0">
            <SheetTitle>Letter Request Details</SheetTitle>
          </SheetHeader>
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
                  <p className="font-medium">{viewingRequest.lastWorkingDay ? format(new Date(viewingRequest.lastWorkingDay), 'MMMM dd, yyyy') : '—'}</p>
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

              {Object.entries(viewingRequest.documentData || {}).filter(([key, value]) => value && !['employeeName', 'employeeEmail', 'department', 'designation', 'companyName', 'companyAddress', 'companyEmail', 'companyPhone', 'labourIdentificationNumber'].includes(key)).length > 0 && (
                <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2">
                  {Object.entries(viewingRequest.documentData || {}).filter(([key, value]) => value && !['employeeName', 'employeeEmail', 'department', 'designation', 'companyName', 'companyAddress', 'companyEmail', 'companyPhone', 'labourIdentificationNumber'].includes(key)).map(([key, value]) => (
                    <div key={key}><p className="text-sm text-gray-600">{key.replace(/[A-Z]/g, (letter) => ` ${letter}`).replace(/^./, (letter) => letter.toUpperCase())}</p><p className="font-medium">{value}</p></div>
                  ))}
                </div>
              )}

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
          <SheetFooter className="sticky bottom-0 mt-4 border-t bg-background px-0 pb-0 pt-4">
            <Button onClick={() => setShowViewDialog(false)}>Close</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Approve Dialog */}
      <Sheet open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-lg">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0">
            <SheetTitle>Approve and issue document</SheetTitle>
            <SheetDescription>
              Approve this request. Its PDF will be rendered securely when an authorized user downloads it.
            </SheetDescription>
          </SheetHeader>
          {processingRequest && (
            <div className="py-4">
              <div className="p-4 bg-green-50 rounded-lg space-y-2">
                <p className="font-semibold">{processingRequest.employeeName}</p>
                <div className="flex items-center gap-2">
                  {getLetterTypeBadge(processingRequest.letterType)}
                  {processingRequest.lastWorkingDay && <span className="text-sm text-gray-600">Last Working: {format(new Date(processingRequest.lastWorkingDay), 'MMM dd, yyyy')}</span>}
                </div>
                <p className="text-sm text-gray-600">Requested by: {processingRequest.requestedByName}</p>
              </div>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mt-4">
                <p className="text-sm text-blue-800">
                  The approved document will be available to download. No external file storage is needed.
                </p>
              </div>
            </div>
          )}
          <SheetFooter className="sticky bottom-0 mt-4 flex-col-reverse gap-2 border-t bg-background px-0 pb-0 pt-4 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => setShowApproveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove} disabled={loading} className="bg-green-600 hover:bg-green-700">
              Approve & Issue
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Reject Dialog */}
      <Sheet open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-lg">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0">
            <SheetTitle>Reject Letter Request</SheetTitle>
            <SheetDescription>
              Provide a reason for rejection
            </SheetDescription>
          </SheetHeader>
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
          <SheetFooter className="sticky bottom-0 mt-4 flex-col-reverse gap-2 border-t bg-background px-0 pb-0 pt-4 sm:flex-row sm:justify-end">
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
              Reject Request
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-3xl">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0">
            <SheetTitle>Customize {editingTemplate?.name}</SheetTitle>
            <SheetDescription>Save creates an editable draft. Publish it when the preview is ready. Previously issued PDFs keep their original version.</SheetDescription>
          </SheetHeader>
          {editingTemplate && (
            <div className="max-h-[65vh] space-y-4 overflow-y-auto py-2 pr-1">
              <div className="space-y-2">
                <Label htmlFor="template-title">Document heading</Label>
                <Input id="template-title" value={templateForm.title} onChange={(event) => setTemplateForm({ ...templateForm, title: event.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="template-body">Template body</Label>
                <Textarea id="template-body" rows={14} value={templateForm.body} onChange={(event) => setTemplateForm({ ...templateForm, body: event.target.value })} />
                <p className="text-xs text-slate-500">Use {'{{employeeName}}'}, {'{{designation}}'}, {'{{department}}'}, {'{{companyName}}'}, {'{{referenceNumber}}'}, or fields listed below. Blank lines create paragraph spacing.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="template-signature">Signatory title</Label>
                <Input id="template-signature" value={templateForm.signatureTitle} onChange={(event) => setTemplateForm({ ...templateForm, signatureTitle: event.target.value })} />
              </div>
              <div className="space-y-3 rounded-lg border bg-slate-50 p-3">
                <div className="flex items-center justify-between"><p className="text-sm font-medium">Template fields</p><Button type="button" size="sm" variant="outline" onClick={() => setTemplateForm({ ...templateForm, fields: [...templateForm.fields, { key: `field_${templateForm.fields.length + 1}`, label: 'New field', type: 'text', required: false }] })}><Plus className="mr-1 h-3.5 w-3.5" />Add field</Button></div>
                <p className="text-xs text-slate-500">Use each field key as a placeholder in the document body, such as {`{{effectiveDate}}`}.</p>
                {templateForm.fields.map((field, index) => <div key={`${field.key}-${index}`} className="grid gap-2 rounded-md border bg-white p-3 sm:grid-cols-[1fr_1fr_120px_auto_auto] sm:items-center">
                  <Input aria-label="Field label" value={field.label} onChange={(event) => setTemplateForm({ ...templateForm, fields: templateForm.fields.map((item, i) => i === index ? { ...item, label: event.target.value } : item) })} />
                  <Input aria-label="Field key" value={field.key} onChange={(event) => setTemplateForm({ ...templateForm, fields: templateForm.fields.map((item, i) => i === index ? { ...item, key: event.target.value.replace(/[^A-Za-z0-9_]/g, '') } : item) })} />
                  <Select value={field.type} onValueChange={(value) => setTemplateForm({ ...templateForm, fields: templateForm.fields.map((item, i) => i === index ? { ...item, type: value } : item) })}><SelectTrigger aria-label="Field type"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="text">Text</SelectItem><SelectItem value="date">Date</SelectItem><SelectItem value="textarea">Long text</SelectItem></SelectContent></Select>
                  <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={field.required} onChange={(event) => setTemplateForm({ ...templateForm, fields: templateForm.fields.map((item, i) => i === index ? { ...item, required: event.target.checked } : item) })} />Required</label>
                  <Button type="button" size="icon" variant="ghost" aria-label="Remove field" onClick={() => setTemplateForm({ ...templateForm, fields: templateForm.fields.filter((_, i) => i !== index) })}><X className="h-4 w-4" /></Button>
                </div>)}
              </div>
            </div>
          )}
          <SheetFooter className="sticky bottom-0 mt-4 flex-col-reverse gap-2 border-t bg-background px-0 pb-0 pt-4 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => setShowTemplateDialog(false)}>Cancel</Button>
            {editingTemplate && <Button variant="outline" onClick={() => void previewTemplate(editingTemplate, editingTemplate.draft?.version || editingTemplate.activeVersion || undefined)}>Preview PDF</Button>}
            <Button variant="secondary" onClick={saveTemplateDraft} disabled={loading || !templateForm.title.trim() || !templateForm.body.trim()}>Save draft</Button>
            {editingTemplate?.draft && <Button onClick={publishTemplateDraft} disabled={loading}>Publish draft</Button>}
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={showNewTemplateDialog} onOpenChange={setShowNewTemplateDialog}>
        <SheetContent className="w-full gap-0 overflow-y-auto p-6 sm:max-w-2xl">
          <SheetHeader className="mb-5 border-b px-0 pb-5 pt-0"><SheetTitle>Create an English template</SheetTitle><SheetDescription>Create a draft, then add its input fields and review the PDF before publishing.</SheetDescription></SheetHeader>
          <div className="grid gap-4 py-2 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="new-template-name">Template name</Label><Input id="new-template-name" value={newTemplateForm.name} onChange={(event) => setNewTemplateForm({ ...newTemplateForm, name: event.target.value })} placeholder="Remote Work Approval" /></div>
            <div className="space-y-2"><Label htmlFor="new-template-key">Template key</Label><Input id="new-template-key" value={newTemplateForm.templateKey} onChange={(event) => setNewTemplateForm({ ...newTemplateForm, templateKey: event.target.value.toLowerCase().replace(/[^a-z0-9_]+/g, '_') })} placeholder="remote_work_approval" /></div>
            <div className="space-y-2"><Label htmlFor="new-template-category">Category</Label><Select value={newTemplateForm.category} onValueChange={(value) => setNewTemplateForm({ ...newTemplateForm, category: value })}><SelectTrigger id="new-template-category"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="employment">Employment</SelectItem><SelectItem value="separation">Separation</SelectItem><SelectItem value="employee_request">Employee request</SelectItem><SelectItem value="onboarding">Onboarding</SelectItem><SelectItem value="policy">Policy</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent></Select></div>
            <div className="space-y-2"><Label htmlFor="new-template-title">Document heading</Label><Input id="new-template-title" value={newTemplateForm.title} onChange={(event) => setNewTemplateForm({ ...newTemplateForm, title: event.target.value })} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="new-template-body">Document body</Label><Textarea id="new-template-body" rows={9} value={newTemplateForm.body} onChange={(event) => setNewTemplateForm({ ...newTemplateForm, body: event.target.value })} placeholder={'Dear {{employeeName}},\n\nEnter the document text here.'} /></div>
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="new-template-signature">Signatory title</Label><Input id="new-template-signature" value={newTemplateForm.signatureTitle} onChange={(event) => setNewTemplateForm({ ...newTemplateForm, signatureTitle: event.target.value })} /></div>
          </div>
          <SheetFooter className="sticky bottom-0 mt-4 flex-col-reverse gap-2 border-t bg-background px-0 pb-0 pt-4 sm:flex-row sm:justify-end"><Button variant="outline" onClick={() => setShowNewTemplateDialog(false)}>Cancel</Button><Button onClick={createCustomTemplate} disabled={loading || !newTemplateForm.name.trim() || !newTemplateForm.templateKey.trim() || !newTemplateForm.title.trim() || !newTemplateForm.body.trim()}>Create draft</Button></SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

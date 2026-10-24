'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { X } from 'lucide-react';

interface Department {
  id: string;
  name: string;
  description?: string;
  head_id?: string;
  created_at: string;
}

interface Employee {
  uid: string;
  email: string;
  name: string;
  lastName?: string;
  role: string;
  department: string;
  designation: string;
  phone?: string;
  dateOfJoining?: string;
  status: 'active' | 'inactive';
  managerId?: string;
  managerName?: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  employee: Employee | null;
  departments: Department[];
  managers: Employee[];
  userRole: string;
  isDirector: boolean;
  canEditAll: boolean;
  onSubmit: (uid: string, formData: FormData) => void;
  isLoading: boolean;
}

export function EditEmployeeDialog({
  isOpen,
  onClose,
  employee,
  departments,
  managers,
  userRole,
  isDirector,
  canEditAll,
  onSubmit,
  isLoading,
}: Props) {
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    lastName: '',
    role: 'employee' as const,
    department: '',
    designation: '',
    phone: '',
    dateOfJoining: '',
    managerId: '',
  });

  useEffect(() => {
    if (employee) {
      setFormData({
        email: employee.email || '',
        name: employee.name || '',
        lastName: employee.lastName || '',
        role: employee.role as any,
        department: employee.department || '',
        designation: employee.designation || '',
        phone: employee.phone || '',
        dateOfJoining: employee.dateOfJoining ? employee.dateOfJoining.split('T')[0] : '',
        managerId: employee.managerId || '',
      });
    }
  }, [employee]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!employee) return;
    const data = new FormData();
    Object.entries(formData).forEach(([key, value]) => {
      if (value) data.append(key, value);
    });
    onSubmit(employee.uid, data);
  };

  const getFullName = (firstName?: string, lastName?: string) =>
    [firstName, lastName].filter(Boolean).join(' ');

  if (!employee) return null;

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
        <div className="p-6 border-b">
          <SheetHeader>
            <SheetTitle className="text-xl">Edit Employee</SheetTitle>
            <SheetDescription className="mt-1">
              Update employee information. Changes will be logged in audit trail.
            </SheetDescription>
          </SheetHeader>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div className="p-4 bg-gray-50 border border-gray-100 rounded-lg">
            <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Editing</p>
            <p className="font-semibold text-gray-900 mt-1">{getFullName(employee.name, employee.lastName)}</p>
            <p className="text-sm text-gray-500">{employee.email}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Email - always displayed but not editable */}
            <div className="space-y-2">
              <Label htmlFor="edit-email">Email *</Label>
              <Input
                id="edit-email"
                type="email"
                value={formData.email}
                disabled
                className="bg-gray-50 cursor-not-allowed"
              />
              <p className="text-xs text-gray-500">Email cannot be changed after creation</p>
            </div>

            {canEditAll && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="edit-name">First Name *</Label>
                  <Input
                    id="edit-name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    disabled={isLoading}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-last-name">Last Name</Label>
                  <Input
                    id="edit-last-name"
                    value={formData.lastName}
                    onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                    disabled={isLoading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-phone">Phone</Label>
                  <Input
                    id="edit-phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    disabled={isLoading}
                  />
                </div>
              </>
            )}

            {canEditAll && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="edit-role">Role</Label>
                  <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })}>
                    <SelectTrigger id="edit-role">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="employee">Employee</SelectItem>
                      <SelectItem value="lead">Lead</SelectItem>
                      <SelectItem value="manager">Manager</SelectItem>
                      {isDirector && <SelectItem value="hr">HR</SelectItem>}
                      {isDirector && <SelectItem value="director">Director</SelectItem>}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="edit-department">Department</Label>
                  <Select value={formData.department} onValueChange={(value) => setFormData({ ...formData, department: value })}>
                    <SelectTrigger id="edit-department">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.name}>
                          {dept.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2 col-span-2">
                  <Label htmlFor="edit-designation">Designation</Label>
                  <Input
                    id="edit-designation"
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                  />
                </div>

                <div className="space-y-2 col-span-2">
                  <Label htmlFor="edit-manager">Reporting Manager</Label>
                  <Select
                    value={formData.managerId || 'none'}
                    onValueChange={(value) => setFormData({ ...formData, managerId: value === 'none' ? '' : value })}
                  >
                    <SelectTrigger id="edit-manager">
                      <SelectValue placeholder="Select manager" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {managers
                        .filter((m) => m.role === 'lead' || m.role === 'manager' || m.role === 'director' || m.uid === formData.managerId)
                        .map((manager) => (
                          <SelectItem key={manager.uid} value={manager.uid}>
                            {getFullName(manager.name, manager.lastName)} - {manager.role}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2 col-span-2">
                  <Label htmlFor="edit-joining-date">Date of Joining</Label>
                  <Input
                    id="edit-joining-date"
                    type="date"
                    value={formData.dateOfJoining}
                    onChange={(e) => setFormData({ ...formData, dateOfJoining: e.target.value })}
                  />
                </div>
              </>
            )}
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              Save Changes
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}

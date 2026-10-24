'use client';

import { useState } from 'react';
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
import { UserPlus, X } from 'lucide-react';

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
  departments: Department[];
  managers: Employee[];
  userRole: string;
  isDirector: boolean;
  onSubmit: (formData: FormData) => void;
  isLoading: boolean;
}

export function CreateEmployeeDialog({
  isOpen,
  onClose,
  departments,
  managers,
  userRole,
  isDirector,
  onSubmit,
  isLoading,
}: Props) {
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    lastName: '',
    password: '',
    role: 'employee' as string,
    department: '',
    designation: '',
    phone: '',
    dateOfJoining: new Date().toISOString().split('T')[0],
    managerId: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data = new FormData();
    Object.entries(formData).forEach(([key, value]) => {
      if (value) data.append(key, value);
    });
    onSubmit(data);
  };

  const getFullName = (firstName?: string, lastName?: string) =>
    [firstName, lastName].filter(Boolean).join(' ');

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
        <div className="p-6 border-b">
          <SheetHeader>
            <SheetTitle className="text-xl flex items-center gap-2">
              <UserPlus className="h-5 w-5" />
              Add New Employee
            </SheetTitle>
            <SheetDescription className="mt-1">
              {userRole === 'hr'
                ? 'Submit an onboarding request for director approval.'
                : 'Create a new employee account. A welcome email will be sent automatically.'}
            </SheetDescription>
          </SheetHeader>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="create-name">First Name *</Label>
              <Input
                id="create-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="John"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-last-name">Last Name</Label>
              <Input
                id="create-last-name"
                value={formData.lastName}
                onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                placeholder="Doe"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-email">Email *</Label>
              <Input
                id="create-email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="john@company.com"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-password">Password *</Label>
              <Input
                id="create-password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="Min. 6 characters"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-phone">Phone</Label>
              <Input
                id="create-phone"
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+1234567890"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-role">Role *</Label>
              <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })}>
                <SelectTrigger id="create-role">
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
              <Label htmlFor="create-department">Department *</Label>
              <Select value={formData.department} onValueChange={(value) => setFormData({ ...formData, department: value })}>
                <SelectTrigger id="create-department">
                  <SelectValue placeholder="Select department" />
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

            <div className="space-y-2">
              <Label htmlFor="create-designation">Designation *</Label>
              <Input
                id="create-designation"
                value={formData.designation}
                onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                placeholder="Software Engineer"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-joining-date">Date of Joining *</Label>
              <Input
                id="create-joining-date"
                type="date"
                value={formData.dateOfJoining}
                onChange={(e) => setFormData({ ...formData, dateOfJoining: e.target.value })}
                required
              />
            </div>

            <div className="space-y-2 col-span-2">
              <Label htmlFor="create-manager">Reporting Manager</Label>
              <Select
                value={formData.managerId || 'none'}
                onValueChange={(value) => setFormData({ ...formData, managerId: value === 'none' ? '' : value })}
              >
                <SelectTrigger id="create-manager">
                  <SelectValue placeholder="Select manager (optional)" />
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
          </div>

          <div className="p-6 border-t bg-gray-50 flex justify-end gap-3 mt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {userRole === 'hr' ? 'Submit Request' : 'Create Employee'}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}

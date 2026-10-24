'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import {
  Mail, Phone, Building2, Shield, Calendar, Users
} from 'lucide-react';

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
  reporteesCount?: number;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  employee: Employee | null;
}

const roleStyles: Record<string, string> = {
  director: 'bg-purple-100 text-purple-800',
  hr: 'bg-blue-100 text-blue-800',
  manager: 'bg-green-100 text-green-800',
  lead: 'bg-yellow-100 text-yellow-800',
  employee: 'bg-gray-100 text-gray-800',
};

const statusStyles: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-red-100 text-red-800',
};

export function ViewEmployeeDialog({ isOpen, onClose, employee }: Props) {
  if (!employee) return null;

  const getFullName = (firstName?: string, lastName?: string) =>
    [firstName, lastName].filter(Boolean).join(' ');

  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent className="overflow-y-auto p-0" style={{ width: '650px', maxWidth: '650px' }}>
        <div className="p-6 border-b">
          <SheetHeader>
            <SheetTitle className="text-xl">Employee Details</SheetTitle>
          </SheetHeader>
        </div>

        <div className="p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{getFullName(employee.name, employee.lastName)}</h2>
              <p className="text-sm text-gray-600 mt-0.5">{employee.designation}</p>
              <p className="text-xs text-gray-500">{employee.department}</p>
            </div>
            <div className="flex flex-col gap-2 items-end">
              <Badge className={roleStyles[employee.role] || roleStyles.employee}>
                {employee.role}
              </Badge>
              <Badge className={statusStyles[employee.status] || statusStyles.inactive}>
                {employee.status}
              </Badge>
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                <Mail className="h-3.5 w-3.5" />
                Email
              </div>
              <p className="text-sm font-medium text-gray-900 break-all">{employee.email}</p>
            </div>

            {employee.phone && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                  <Phone className="h-3.5 w-3.5" />
                  Phone
                </div>
                <p className="text-sm font-medium text-gray-900">{employee.phone}</p>
              </div>
            )}

            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                <Building2 className="h-3.5 w-3.5" />
                Department
              </div>
              <p className="text-sm font-medium text-gray-900">{employee.department || '-'}</p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                <Shield className="h-3.5 w-3.5" />
                Role
              </div>
              <p className="text-sm font-medium text-gray-900 capitalize">{employee.role}</p>
            </div>

            {employee.dateOfJoining && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                  <Calendar className="h-3.5 w-3.5" />
                  Date of Joining
                </div>
                <p className="text-sm font-medium text-gray-900">
                  {new Date(employee.dateOfJoining).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'short', day: 'numeric'
                  })}
                </p>
              </div>
            )}

            {employee.managerName && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                  <Users className="h-3.5 w-3.5" />
                  Reporting To
                </div>
                <p className="text-sm font-medium text-gray-900">{employee.managerName}</p>
              </div>
            )}

            {employee.reporteesCount !== undefined && employee.reporteesCount > 0 && (
              <div className="space-y-1 col-span-2">
                <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wide font-medium">
                  <Users className="h-3.5 w-3.5" />
                  Team Size
                </div>
                <p className="text-sm font-medium text-gray-900">{employee.reporteesCount} direct reportees</p>
              </div>
            )}
          </div>
        </div>

        <div className="p-6 border-t bg-gray-50 flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
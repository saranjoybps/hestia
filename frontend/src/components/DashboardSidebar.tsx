'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import {
  LayoutDashboard,
  Calendar,
  FileText,
  CheckSquare,
  TrendingUp,
  FolderOpen,
  Megaphone,
  UserCircle,
  BarChart3,
  Building2,
  Clock,
  UserPlus,
  Menu,
  ClipboardList,
} from 'lucide-react';

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
  group?: string;
}

const navItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, group: 'Main' },
  { title: 'My Profile', href: '/profile', icon: UserCircle, group: 'Main' },
  { title: 'Attendance', href: '/attendance', icon: Calendar, group: 'Work' },
  { title: 'Leave Requests', href: '/leaves', icon: FileText, group: 'Work' },
  { title: 'Shifts', href: '/dashboard/shifts', icon: Clock, group: 'Work' },
  { title: 'Tasks', href: '/tasks', icon: CheckSquare, group: 'Work' },
  { title: 'Performance', href: '/performance', icon: TrendingUp, roles: ['director', 'manager', 'lead', 'hr'], group: 'Work' },
  { title: 'Employees', href: '/dashboard/employees', icon: UserPlus, roles: ['manager', 'director', 'hr'], group: 'Manage' },
  { title: 'Documents', href: '/documents', icon: FolderOpen, roles: ['director', 'hr'], group: 'Manage' },
  { title: 'Announcements', href: '/announcements', icon: Megaphone, group: 'Manage' },
  { title: 'Organization', href: '/organization', icon: Building2, roles: ['director', 'hr'], group: 'Manage' },
  { title: 'Reports & Analytics', href: '/reports', icon: BarChart3, roles: ['director', 'manager', 'hr'], group: 'Manage' },
  { title: 'Audit Log', href: '/audit-logs', icon: ClipboardList, roles: ['director', 'super_admin'], group: 'Manage' },
];

const groups = ['Main', 'Work', 'Manage'];

export default function DashboardSidebar() {
  const pathname = usePathname();
  const { userData } = useAuth();
  const [open, setOpen] = useState(false);

  const canAccessItem = (item: NavItem) => {
    if (!item.roles) return true;
    return userData && item.roles.includes(userData.role);
  };

  const isActiveRoute = (item: NavItem) => {
    if (item.href === '/dashboard') return pathname === '/dashboard';
    return pathname === item.href || pathname.startsWith(item.href + '/');
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full bg-white dark:bg-gray-950">
      {/* Logo */}
      <div className="px-6 py-4 border-b dark:border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">J</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white leading-none">JoyHR</h1>
            <p className="text-xs text-gray-400 mt-0.5">HR Management</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map((group) => {
          const items = navItems.filter(item => item.group === group && canAccessItem(item));
          if (items.length === 0) return null;

          return (
            <div key={group}>
              <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest px-3 mb-1.5">
                {group}
              </p>
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const isActive = isActiveRoute(item);

                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
                      >
                        <Icon className="h-4 w-4 flex-shrink-0 text-gray-400 dark:text-gray-500" />
                        <span className="truncate">{item.title}</span>
                        {isActive && (
                          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-white opacity-80" />
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t dark:border-gray-800">
        <p className="text-xs text-gray-400">© 2026 Joyrts · v1.0.2</p>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" className="bg-white dark:bg-gray-900 shadow-sm">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[260px] p-0">
            <VisuallyHidden><SheetTitle>Navigation Menu</SheetTitle></VisuallyHidden>
            <SidebarContent />
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop */}
      <aside className="hidden lg:flex w-[260px] border-r dark:border-gray-800 h-screen sticky top-0 flex-col">
        <SidebarContent />
      </aside>
    </>
  );
}

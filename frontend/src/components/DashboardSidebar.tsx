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
  BarChart3,
  Building2,
  Clock,
  UserPlus,
  Menu,
  ClipboardList,
  BriefcaseBusiness,
  Package,
} from 'lucide-react';

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
  group?: string;
}

const navItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, group: 'Overview' },
  { title: 'Attendance', href: '/attendance', icon: Calendar, group: 'My Work' },
  { title: 'Leave Requests', href: '/leaves', icon: FileText, group: 'My Work' },
  { title: 'Shifts', href: '/dashboard/shifts', icon: Clock, group: 'My Work' },
  { title: 'Tasks', href: '/tasks', icon: CheckSquare, group: 'My Work' },
  { title: 'Performance', href: '/performance', icon: TrendingUp, roles: ['employee', 'lead', 'manager', 'director', 'hr', 'super_admin'], group: 'My Work' },
  { title: 'Employees', href: '/dashboard/employees', icon: UserPlus, roles: ['manager', 'director', 'hr'], group: 'People & Resources' },
  { title: 'Candidates', href: '/dashboard/candidates', icon: BriefcaseBusiness, roles: ['lead', 'manager', 'director', 'hr', 'super_admin'], group: 'People & Resources' },
  { title: 'Assets', href: '/dashboard/assets', icon: Package, roles: ['employee', 'lead', 'manager', 'director', 'hr', 'super_admin'], group: 'People & Resources' },
  { title: 'Organization', href: '/organization', icon: Building2, roles: ['director', 'hr', 'super_admin'], group: 'Company' },
  { title: 'Documents', href: '/documents', icon: FolderOpen, roles: ['director', 'hr', 'super_admin'], group: 'Company' },
  { title: 'Announcements', href: '/announcements', icon: Megaphone, group: 'Company' },
  { title: 'Reports & Analytics', href: '/reports', icon: BarChart3, roles: ['lead', 'manager', 'director', 'hr', 'super_admin'], group: 'Company' },
  { title: 'Audit Log', href: '/audit-logs', icon: ClipboardList, roles: ['director', 'super_admin'], group: 'Company' },
];

const groups = ['Overview', 'My Work', 'People & Resources', 'Company'];

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
      <div className="h-17 px-6 flex items-center border-b dark:border-gray-800">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white leading-none">Hestia</h1>
      </div>

      {/* Nav */}
      <nav className="sidebar-scrollbar-hidden flex-1 overflow-y-auto px-3 py-4 space-y-5">
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
                        className={cn(
                          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white',
                          isActive ? 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-600 dark:text-gray-400'
                        )}
                      >
                        <Icon className="h-4 w-4 flex-shrink-0 text-gray-400 dark:text-gray-500" />
                        <span className="truncate">{item.title}</span>
                        {isActive && (
                          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400" />
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
        <p className="text-xs text-gray-400">Â© 2026 Hestia Â· v1.0.4</p>
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


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
  Users,
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
} from 'lucide-react';

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
}

const navItems: NavItem[] = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    title: 'My Profile',
    href: '/profile',
    icon: UserCircle,
  },
  {
    title: 'Attendance',
    href: '/attendance',
    icon: Calendar,
  },
  {
    title: 'Leave Requests',
    href: '/leaves',
    icon: FileText,
  },
  {
    title: 'Shifts',
    href: '/dashboard/shifts',
    icon: Clock,
  },
  {
    title: 'Tasks',
    href: '/tasks',
    icon: CheckSquare,
  },
  {
    title: 'Performance',
    href: '/performance',
    icon: TrendingUp,
  },
  {
    title: 'Employees',
    href: '/dashboard/employees',
    icon: UserPlus,
    roles: ['manager', 'director', 'hr'],
  },
  {
    title: 'Documents',
    href: '/documents',
    icon: FolderOpen,
    roles: ['director', 'hr'],
  },
  {
    title: 'Announcements',
    href: '/announcements',
    icon: Megaphone,
  },
  {
    title: 'Organization',
    href: '/organization',
    icon: Building2,
    roles: ['director', 'hr'],
  },
  {
    title: 'Reports & Analytics',
    href: '/reports',
    icon: BarChart3,
    roles: ['director', 'manager', 'hr'],
  },
];

export default function DashboardSidebar() {
  const pathname = usePathname();
  const { userData } = useAuth();
  const [open, setOpen] = useState(false);

  const canAccessItem = (item: NavItem) => {
    if (!item.roles) return true;
    return userData && item.roles.includes(userData.role);
  };

  const SidebarContent = () => (
    <>
      <div className="p-6 border-b dark:border-gray-800">
        <h1 className="text-2xl font-bold text-blue-600 dark:text-blue-400">JoyHR</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">HR Management System</p>
      </div>
      
      <nav className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            if (!canAccessItem(item)) return null;
            
            const Icon = item.icon;
            const isActive = pathname === item.href;
            
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {item.title}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      
      <div className="p-4 border-t dark:border-gray-800">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          <p>© 2026 Joyrts</p>
          <p>Version 1.0.1</p>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile Menu Button */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" className="bg-white dark:bg-gray-900">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[280px] p-0 bg-white dark:bg-gray-900">
            <VisuallyHidden>
              <SheetTitle>Navigation Menu</SheetTitle>
            </VisuallyHidden>
            <div className="flex flex-col h-full">
              <SidebarContent />
            </div>
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-[280px] border-r bg-white dark:bg-gray-900 dark:border-gray-800 h-screen sticky top-0 flex-col">
        <SidebarContent />
      </aside>
    </>
  );
}

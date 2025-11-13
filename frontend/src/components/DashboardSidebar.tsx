'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
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
    title: 'Employee Directory',
    href: '/employees',
    icon: Users,
    roles: ['director', 'hr'],
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

  const canAccessItem = (item: NavItem) => {
    if (!item.roles) return true;
    return userData && item.roles.includes(userData.role);
  };

  return (
    <aside className="w-[280px] border-r bg-white h-screen sticky top-0 flex flex-col">
      <div className="p-6 border-b">
        <h1 className="text-2xl font-bold text-blue-600">JoyHR</h1>
        <p className="text-sm text-gray-500 mt-1">HR Management System</p>
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
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-700 hover:bg-gray-100'
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
      
      <div className="p-4 border-t">
        <div className="text-xs text-gray-500">
          <p>© 2025 Joyrts</p>
          <p>Version 1.0.0</p>
        </div>
      </div>
    </aside>
  );
}

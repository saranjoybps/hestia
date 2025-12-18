import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: '/profile',
        destination: '/dashboard/profile',
        permanent: false,
      },
      {
        source: '/settings',
        destination: '/dashboard/settings',
        permanent: false,
      },
      {
        source: '/attendance',
        destination: '/dashboard/attendance',
        permanent: false,
      },
      {
        source: '/employees',
        destination: '/dashboard/employees',
        permanent: false,
      },
      {
        source: '/leaves',
        destination: '/dashboard/leaves',
        permanent: false,
      },
      {
        source: '/announcements',
        destination: '/dashboard/announcements',
        permanent: false,
      },
      {
        source: '/tasks',
        destination: '/dashboard/tasks',
        permanent: false,
      },
      {
        source: '/performance',
        destination: '/dashboard/performance',
        permanent: false,
      },
      {
        source: '/reports',
        destination: '/dashboard/reports',
        permanent: false,
      },
      {
        source: '/organization',
        destination: '/dashboard/organization',
        permanent: false,
      },
      {
        source: '/documents',
        destination: '/dashboard/documents',
        permanent: false,
      },
    ];
  },
};

export default nextConfig;

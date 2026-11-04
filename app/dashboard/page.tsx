'use client';

import dynamic from 'next/dynamic';
import { Spinner } from '@/app/ui/dashboard/redirect';

const DashboardView = dynamic(() => import('./dashboard-view'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <Spinner />
    </div>
  ),
});

export default function DashboardPage() {
  return <DashboardView />;
}

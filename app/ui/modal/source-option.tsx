'use client';

import { Card } from '@/components/ui/card';
import { ReactNode } from 'react';

interface SourceOptionProps {
  name: string;
  icon: ReactNode;
  onClick?: () => void;
}

export default function SourceOption({
  name,
  icon,
  onClick,
}: SourceOptionProps) {
  return (
    <Card
      className="bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      onClick={onClick}
    >
      <div className="flex flex-col items-center gap-2">
        {icon}
        <span className="text-sm">{name}</span>
      </div>
    </Card>
  );
}

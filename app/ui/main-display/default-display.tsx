'use client';

import { Button } from '@/components/ui/button';
import { Upload } from 'lucide-react';
import React from 'react';

export default function DefaultDisplay({
  onUpload,
}: {
  onUpload?: () => void;
}) {
  return (
    <div className="flex h-full w-1/2 flex-col items-center justify-center p-8">
      <div className="mb-6 text-center">
        <h3 className="mb-2 text-2xl font-semibold text-gray-800 dark:text-gray-100">
          Ready to get focused?
        </h3>
        <p className="text-gray-500 dark:text-gray-400">
          Upload your learning materials to start a personalized learning
          experience
        </p>
      </div>
      <Button
        className="w-full bg-blue-600 py-6 text-lg font-medium text-white transition-all hover:bg-blue-700"
        onClick={onUpload}
      >
        <Upload /> Upload Materials
      </Button>
    </div>
  );
}

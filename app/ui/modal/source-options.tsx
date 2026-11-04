'use client';

import { FileText, FileCode, FileType } from 'lucide-react';
import SourceOption from './source-option';

export default function SourceOptions() {
  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      <SourceOption
        name="PDF"
        icon={<FileType className="h-6 w-6 text-red-500" />}
      />
      <SourceOption
        name="Text File"
        icon={<FileText className="h-6 w-6 text-blue-500" />}
      />
      <SourceOption
        name="Markdown"
        icon={<FileCode className="h-6 w-6 text-purple-500" />}
      />
    </div>
  );
}

'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText } from 'lucide-react';

interface TextViewerProps {
  file?: File;
}

export default function TextViewer({ file }: TextViewerProps) {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file) return;

    // Only process text files
    if (!file.name.endsWith('.txt') && file.type !== 'text/plain') {
      setError('Only text files are supported in this viewer');
      return;
    }

    const readFile = async () => {
      setLoading(true);
      setError(null);

      try {
        const text = await file.text();
        setContent(text);
      } catch (err) {
        setError('Failed to read file content');
        console.error('Error reading file:', err);
      } finally {
        setLoading(false);
      }
    };

    readFile();
  }, [file]);

  if (!file) {
    return (
      <div className="flex-1 p-6">
        <Card className="w-full h-full">
          <CardContent className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>Select a text file to view its content</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6">
      <Card className="w-full h-full overflow-hidden">
        <CardHeader className="bg-gray-50 border-b px-4 py-3">
          <CardTitle className="text-md font-medium flex items-center">
            <FileText className="h-4 w-4 mr-2 text-blue-500" />
            {file.name}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-auto h-[calc(100%-3rem)]">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-500">Loading file content...</p>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-red-500">{error}</p>
            </div>
          ) : (
            <pre className="p-4 text-sm whitespace-pre-wrap">{content}</pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

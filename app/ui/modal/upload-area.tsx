'use client';

import { useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Upload, FileText } from 'lucide-react';

interface UploadAreaProps {
  onFilesSelected?: (files: File[]) => void;
  onUploadComplete?: () => void;
}

export default function UploadArea({
  onFilesSelected,
  onUploadComplete,
}: UploadAreaProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle file selection
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      const newFiles = Array.from(event.target.files);
      setFiles([...files, ...newFiles]);

      // Notify parent component
      if (onFilesSelected) {
        onFilesSelected([...files, ...newFiles]);
      }

      // For demo purposes, simulate upload
      handleFileUpload([...files, ...newFiles]);
    }
  };

  // Handle drag events
  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) {
      setIsDragging(true);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles([...files, ...newFiles]);

      // Notify parent component
      if (onFilesSelected) {
        onFilesSelected([...files, ...newFiles]);
      }

      // For demo purposes, simulate upload
      handleFileUpload([...files, ...newFiles]);
    }
  };

  // Handle file upload
  const handleFileUpload = (filesToUpload: File[]) => {
    setUploading(true);
    // In a real application, you would upload these files to a server
    // This is just a simulation for demo purposes
    setTimeout(() => {
      setUploading(false);
      console.log('Files uploaded:', filesToUpload);

      // Call onUploadComplete to close the modal
      if (onUploadComplete) {
        onUploadComplete();
      }
    }, 2000);
  };

  // Handle click on the entire component
  const handleCardClick = () => {
    if (!uploading) {
      fileInputRef.current?.click();
    }
  };

  return (
    <Card
      className={`border border-dashed ${
        isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800'
      } rounded-lg p-12 mb-6 transition-colors ${
        !uploading
          ? 'cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-gray-700/50'
          : ''
      }`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleCardClick}
    >
      <div className="flex flex-col items-center justify-center text-center">
        <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
          <Upload className="h-5 w-5 text-blue-500" />
        </div>
        <h3 className="text-lg font-medium mb-2">Upload sources</h3>
        <p className="text-gray-600 mb-1">
          {uploading ? (
            <span>Uploading files...</span>
          ) : (
            <>
              Drag & drop or{' '}
              <span className="text-blue-500 font-medium">choose file</span> to
              upload
            </>
          )}
        </p>
        <p className="text-gray-500 text-sm">
          Supported: PDF, Text (.txt), Markdown (.md)
        </p>

        {/* Hidden file input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }}
          multiple
          accept=".pdf,.txt,.md"
        />

        {/* Show files being uploaded if any */}
        {files.length > 0 && (
          <div className="mt-4 w-full" onClick={e => e.stopPropagation()}>
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-2"
              >
                <div className="flex items-center">
                  <FileText className="h-4 w-4 mr-2 text-blue-500" />
                  <span className="text-sm">{file.name}</span>
                </div>
                <span className="text-xs text-gray-500">
                  {Math.round(file.size / 1024)} KB
                </span>
              </div>
            ))}
            {uploading && (
              <Progress value={50} className="h-2 w-full mt-2 bg-gray-100" />
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

'use client';

import { useEffect, useState } from 'react';
import ModalHeader from '@/app/ui/modal/modal-header';
import UploadArea from '@/app/ui/modal/upload-area';
import SourceOptions from '@/app/ui/modal/source-options';

interface UploadSourcesModalProps {
  onClose?: () => void;
  handleFileUpload?: (files: File[]) => void;
}

export default function UploadSourcesModal({
  onClose,
  handleFileUpload,
}: UploadSourcesModalProps) {
  const [showTextInput, setShowTextInput] = useState(false);
  const [pastedText, setPastedText] = useState('');

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onClose) onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = 'auto'; };
  }, []);

  const handleFilesSelected = (files: File[]) => {
    if (handleFileUpload) handleFileUpload(files);
  };

  const handleTextSubmit = () => {
    if (!pastedText.trim()) return;
    // Convert pasted text to a File object
    const blob = new Blob([pastedText], { type: 'text/plain' });
    const file = new File([blob], 'pasted-notes.txt', { type: 'text/plain' });
    if (handleFileUpload) handleFileUpload([file]);
    if (onClose) onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 dark:text-gray-100 rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden shadow-2xl">
        <div className="p-7 h-full flex flex-col">
          <ModalHeader title="Add study material" onClose={onClose} />

          <div className="flex-1 overflow-y-auto pr-1 mt-4">
            {/* Tab toggle */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setShowTextInput(false)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  !showTextInput
                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                }`}
              >
                Upload file
              </button>
              <button
                onClick={() => setShowTextInput(true)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  showTextInput
                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                }`}
              >
                Paste text
              </button>
            </div>

            {showTextInput ? (
              <div>
                <textarea
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                  placeholder="Paste your study notes, markdown, or any text here..."
                  className="w-full h-64 p-4 border dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-gray-100"
                />
                <button
                  onClick={handleTextSubmit}
                  disabled={!pastedText.trim()}
                  className="mt-3 w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg font-medium transition"
                >
                  Process text
                </button>
              </div>
            ) : (
              <>
                <UploadArea
                  onFilesSelected={handleFilesSelected}
                  onUploadComplete={onClose}
                />
                <div className="mt-4 mb-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Supported formats</p>
                  <SourceOptions />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

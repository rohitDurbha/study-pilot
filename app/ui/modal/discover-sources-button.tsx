'use client';

import { Button } from '@/components/ui/button';

interface DiscoverSourcesButtonProps {
  onClick?: () => void;
}

export default function DiscoverSourcesButton({
  onClick,
}: DiscoverSourcesButtonProps) {
  return (
    <div className="flex justify-end mb-4">
      <Button
        variant="outline"
        className="bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100 gap-2"
        onClick={onClick}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M15 15L21 21M10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10C17 13.866 13.866 17 10 17Z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Discover sources
      </Button>
    </div>
  );
}

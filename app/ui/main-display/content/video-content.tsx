'use client';

import { useRef } from 'react';

export default function VideoContent() {
  const videoRef = useRef<HTMLVideoElement>(null);

  return (
    <div className="w-full h-full flex items-center justify-center p-4">
      <div
        className="bg-gray-900 rounded-xl shadow-lg overflow-hidden max-h-full"
        style={{ aspectRatio: '9/16' }}
      >
        <video
          ref={videoRef}
          className="w-full h-full object-contain"
          controls
          autoPlay
          loop
        >
          <source src="/brainRot.mp4" type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
    </div>
  );
}

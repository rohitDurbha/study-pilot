'use client';

import { useRef } from 'react';

// The upstream project shipped a 39 MB demo clip in public/brainRot.mp4.
// It was left out of this repository, so the clip is now loaded from a URL
// set in NEXT_PUBLIC_DEMO_VIDEO_URL. When the variable is empty the
// component renders nothing, so callers can mount it unconditionally.
export const DEMO_VIDEO_URL = process.env.NEXT_PUBLIC_DEMO_VIDEO_URL?.trim() || '';

export function hasDemoVideo(): boolean {
  return DEMO_VIDEO_URL.length > 0;
}

export default function VideoContent({ src = DEMO_VIDEO_URL }: { src?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  if (!src) {
    return null;
  }

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
          <source src={src} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
    </div>
  );
}

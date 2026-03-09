'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { VideoUpload } from '@/components';
import { uploadVideo, startAnalysis } from '@/lib/api';

export default function UploadPage() {
  const router = useRouter();
  const [status, setStatus] = useState<string>('');

  const handleUpload = async (file: File) => {
    try {
      setStatus('Uploading...');
      const video = await uploadVideo(file);
      
      setStatus('Starting analysis...');
      const analysis = await startAnalysis(video.id);
      
      router.push(`/analysis/${analysis.id}`);
    } catch (error: any) {
      setStatus('');
      throw error;
    }
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Upload Video</h1>
        <p className="text-slate-500 mt-1">Upload a sales pitch video for AI analysis</p>
      </div>

      <div className="max-w-2xl mx-auto">
        <VideoUpload onUpload={handleUpload} />
        {status && (
          <p className="mt-4 text-center text-sm text-indigo-500 font-medium">{status}</p>
        )}
      </div>
    </div>
  );
}

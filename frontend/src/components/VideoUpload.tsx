'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, Video, Music, Loader2 } from 'lucide-react';

interface VideoUploadProps {
  onUpload: (file: File) => Promise<void>;
}

export function VideoUpload({ onUpload }: VideoUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
    }
  }, []);

  const isAudioFile = (filename: string) => {
    const ext = filename.toLowerCase().split('.').pop();
    return ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac', 'wma'].includes(ext || '');
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/mp4': ['.mp4'],
      'video/quicktime': ['.mov'],
      'video/x-msvideo': ['.avi'],
      'video/x-matroska': ['.mkv'],
      'video/webm': ['.webm'],
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'audio/x-m4a': ['.m4a'],
      'audio/aac': ['.aac'],
      'audio/ogg': ['.ogg'],
      'audio/flac': ['.flac'],
    },
    maxSize: 500 * 1024 * 1024, // 500MB
    multiple: false,
  });

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError(null);

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 300);

    try {
      await onUpload(file);
      setProgress(100);
    } catch (err: any) {
      setError(err.message || 'Upload failed. Please try again.');
    } finally {
      clearInterval(progressInterval);
      setUploading(false);
    }
  };

  const removeFile = () => {
    setFile(null);
    setProgress(0);
    setError(null);
  };

  const formatSize = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-slate-300 hover:border-indigo-300 hover:bg-slate-50'
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="w-10 h-10 text-slate-400 mx-auto mb-4" />
        <p className="text-lg font-medium text-slate-700">Drag & drop your video or audio</p>
        <p className="text-sm text-slate-400 mt-1">
          Video: MP4, MOV, AVI, MKV &bull; Audio: MP3, WAV, M4A, AAC &bull; Up to 500MB
        </p>
      </div>

      {/* File preview */}
      {file && (
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              isAudioFile(file.name) ? 'bg-purple-100' : 'bg-indigo-100'
            }`}>
              {isAudioFile(file.name) ? (
                <Music className="w-5 h-5 text-purple-500" />
              ) : (
                <Video className="w-5 h-5 text-indigo-500" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-700 truncate">{file.name}</p>
              <p className="text-xs text-slate-400">
                {formatSize(file.size)} {isAudioFile(file.name) && '• Audio only (no video analysis)'}
              </p>
            </div>
            {!uploading && (
              <button onClick={removeFile} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Progress bar */}
          {uploading && (
            <div className="mt-3">
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>Uploading...</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div
                  className="bg-indigo-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Upload button */}
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-4 w-full py-2.5 bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-300 text-white font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Upload & Analyze
              </>
            )}
          </button>

          {error && <p className="mt-2 text-sm text-red-500 text-center">{error}</p>}
        </div>
      )}
    </div>
  );
}

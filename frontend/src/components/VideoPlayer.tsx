'use client';

import { useRef, useState, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize, SkipBack, SkipForward } from 'lucide-react';

interface TimelineMarker {
  time: number;
  type: 'warning' | 'error' | 'info';
  label: string;
}

interface VideoPlayerProps {
  src: string;
  markers?: TimelineMarker[];
}

export function VideoPlayer({ src, markers = [] }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => setCurrentTime(video.currentTime);
    const onLoadedMetadata = () => setDuration(video.duration);
    const onEnded = () => setPlaying(false);

    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('loadedmetadata', onLoadedMetadata);
    video.addEventListener('ended', onEnded);

    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('loadedmetadata', onLoadedMetadata);
      video.removeEventListener('ended', onEnded);
    };
  }, []);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (playing) {
      video.pause();
    } else {
      video.play();
    }
    setPlaying(!playing);
  };

  const seek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
  };

  const handleSeekBar = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    seek(percent * duration);
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !muted;
    setMuted(!muted);
  };

  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      video.requestFullscreen();
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const markerColor = (type: string) => {
    switch (type) {
      case 'error': return 'bg-red-500';
      case 'warning': return 'bg-yellow-500';
      default: return 'bg-blue-500';
    }
  };

  return (
    <div className="card overflow-hidden">
      <div className="relative bg-black aspect-video">
        <video ref={videoRef} src={src} className="w-full h-full object-contain" />
      </div>

      {/* Controls */}
      <div className="p-3">
        {/* Seek bar */}
        <div className="relative mb-3 cursor-pointer group" onClick={handleSeekBar}>
          <div className="w-full bg-slate-200 rounded-full h-1.5 group-hover:h-2.5 transition-all">
            <div
              className="bg-indigo-500 h-full rounded-full relative"
              style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-indigo-500 rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
          {/* Timeline markers */}
          {markers.map((marker, idx) => (
            <div
              key={idx}
              className={`absolute top-0 w-2 h-2 rounded-full ${markerColor(marker.type)} -translate-x-1/2`}
              style={{ left: `${duration ? (marker.time / duration) * 100 : 0}%` }}
              title={marker.label}
            />
          ))}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => seek(Math.max(0, currentTime - 10))} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500">
              <SkipBack className="w-4 h-4" />
            </button>
            <button onClick={togglePlay} className="p-2 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-white">
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button onClick={() => seek(Math.min(duration, currentTime + 10))} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500">
              <SkipForward className="w-4 h-4" />
            </button>
            <span className="text-xs text-slate-500 ml-2">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={toggleMute} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500">
              {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
            </button>
            <button onClick={toggleFullscreen} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500">
              <Maximize className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

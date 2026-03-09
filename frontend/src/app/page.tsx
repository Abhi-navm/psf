'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getVideos } from '@/lib/api';
import { Upload, Video, TrendingUp, Clock, ArrowRight, Music } from 'lucide-react';

interface VideoItem {
  id: string;
  original_filename: string;
  created_at: string;
  duration?: number;
  analysis_id?: string;
  analysis_status?: string;
  overall_score?: number;
  comparison_score?: number;
  is_audio_only?: boolean;
}

export default function HomePage() {
  const [recentVideos, setRecentVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const data = await getVideos(0, 5);
        setRecentVideos(data.videos || []);
      } catch (error) {
        console.error('Failed to fetch videos:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVideos();
  }, []);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getScoreColor = (score?: number) => {
    if (!score) return 'bg-slate-100 text-slate-500';
    if (score >= 80) return 'bg-emerald-100 text-emerald-700';
    if (score >= 60) return 'bg-yellow-100 text-yellow-700';
    return 'bg-red-100 text-red-700';
  };

  const getStatusBadge = (status?: string) => {
    if (!status) return null;
    if (status === 'COMPLETED') return null; // Show score instead
    if (status === 'PROCESSING' || status.startsWith('ANALYZING')) {
      return (
        <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
          Processing...
        </span>
      );
    }
    if (status === 'FAILED') {
      return (
        <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">
          Failed
        </span>
      );
    }
    if (status === 'PENDING') {
      return (
        <span className="px-2 py-1 text-xs font-medium bg-slate-100 text-slate-600 rounded-full">
          Pending
        </span>
      );
    }
    return null;
  };

  const calculateAvgScore = () => {
    const scores = recentVideos
      .filter(v => v.overall_score !== undefined && v.overall_score !== null)
      .map(v => v.overall_score as number);
    if (scores.length === 0) return '--';
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-500 mt-1">Welcome to AI Pitch Analyzer</p>
      </div>

      {/* Stats */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Total Analyses</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{recentVideos.length}</p>
            </div>
            <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-indigo-500" />
            </div>
          </div>
        </div>
        
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Videos Uploaded</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{recentVideos.length}</p>
            </div>
            <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
              <Video className="w-6 h-6 text-emerald-500" />
            </div>
          </div>
        </div>
        
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Avg. Score</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{calculateAvgScore()}</p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-purple-500" />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <Link href="/upload" className="card p-6 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Upload className="w-7 h-7 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 mb-1">Upload New Video</h3>
              <p className="text-sm text-slate-500">Analyze a new sales pitch video</p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-400 group-hover:text-indigo-500 transition-colors" />
          </div>
        </Link>
        
        <Link href="/history" className="card p-6 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
              <Clock className="w-7 h-7 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 mb-1">View History</h3>
              <p className="text-sm text-slate-500">See all past analyses</p>
            </div>
            <ArrowRight className="w-5 h-5 text-slate-400 group-hover:text-emerald-500 transition-colors" />
          </div>
        </Link>
      </div>

      {/* Recent Videos */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">Recent Videos</h2>
          <Link href="/history" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
            View all →
          </Link>
        </div>
        
        {loading ? (
          <div className="text-center py-8 text-slate-400">Loading...</div>
        ) : recentVideos.length === 0 ? (
          <div className="text-center py-8">
            <Video className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No videos uploaded yet</p>
            <Link href="/upload" className="text-indigo-600 hover:text-indigo-700 text-sm font-medium mt-2 inline-block">
              Upload your first video →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {recentVideos.map((video) => (
              <Link 
                key={video.id} 
                href={video.analysis_id ? `/analysis/${video.analysis_id}` : `/upload?video=${video.id}`}
                className="flex items-center gap-4 p-3 hover:bg-slate-50 rounded-lg transition-colors"
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  video.is_audio_only ? 'bg-purple-100' : 'bg-slate-100'
                }`}>
                  {video.is_audio_only ? (
                    <Music className="w-5 h-5 text-purple-500" />
                  ) : (
                    <Video className="w-5 h-5 text-slate-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-700 truncate">
                    {video.original_filename || 'Untitled Video'}
                  </p>
                  <p className="text-sm text-slate-400">
                    {formatDate(video.created_at)} • {formatDuration(video.duration)}
                    {video.is_audio_only && ' • Audio'}
                  </p>
                </div>
                {/* Show score or status */}
                {video.analysis_status === 'COMPLETED' && video.overall_score !== undefined ? (
                  <div className="flex items-center gap-2">
                    {video.comparison_score !== undefined && video.comparison_score !== null && (
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getScoreColor(video.comparison_score)}`}>
                        Match: {Math.round(video.comparison_score)}%
                      </span>
                    )}
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getScoreColor(video.overall_score)}`}>
                      Score: {Math.round(video.overall_score)}
                    </span>
                  </div>
                ) : (
                  getStatusBadge(video.analysis_status) || (
                    <span className="px-2 py-1 text-xs font-medium bg-indigo-100 text-indigo-700 rounded-full">
                      Analyze
                    </span>
                  )
                )}
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

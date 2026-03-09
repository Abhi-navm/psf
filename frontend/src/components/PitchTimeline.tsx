'use client';

import { Play } from 'lucide-react';

interface TimelineIssue {
  timestamp: number;
  title: string;
  description: string;
  type?: 'warning' | 'error' | 'info';
}

interface PitchTimelineProps {
  issues: TimelineIssue[];
  onSeek?: (timestamp: number) => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export default function PitchTimeline({ issues, onSeek }: PitchTimelineProps) {
  const getButtonColor = (type?: string) => {
    switch (type) {
      case 'error': return 'bg-red-500 group-hover:bg-red-600';
      case 'warning': return 'bg-orange-500 group-hover:bg-orange-600';
      default: return 'bg-blue-500 group-hover:bg-blue-600';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-800">Pitch Analysis Timeline</h2>
        <span className="text-sm text-blue-600 font-medium">Key Issues: {issues.length}</span>
      </div>
      
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
        {issues.map((issue, i) => (
          <button
            key={i}
            onClick={() => onSeek?.(issue.timestamp)}
            className="w-full flex items-start gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors text-left group"
          >
            <div className={`w-10 h-10 rounded-full ${getButtonColor(issue.type)} flex items-center justify-center flex-shrink-0 transition-colors`}>
              <Play className="w-4 h-4 text-white ml-0.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-600">
                  {formatTime(issue.timestamp)}
                </span>
                <span className="text-sm text-slate-400">—</span>
                <span className="text-sm font-semibold text-slate-800 truncate">
                  {issue.title}
                </span>
              </div>
              <p className="text-sm text-slate-500 mt-0.5 line-clamp-2">
                {issue.description}
              </p>
            </div>
          </button>
        ))}
        
        {issues.length === 0 && (
          <div className="text-center py-8 text-slate-400">
            No issues detected
          </div>
        )}
      </div>
    </div>
  );
}

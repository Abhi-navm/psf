'use client';

import { Clock, AlertCircle, AlertTriangle, Info } from 'lucide-react';

interface TimelineItem {
  timestamp: number;
  type: 'error' | 'warning' | 'info';
  category: string;
  message: string;
}

interface TimelineAnalysisProps {
  items: TimelineItem[];
}

export function TimelineAnalysis({ items }: TimelineAnalysisProps) {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'warning': return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      default: return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  const getBgColor = (type: string) => {
    switch (type) {
      case 'error': return 'bg-red-50 border-red-100';
      case 'warning': return 'bg-amber-50 border-amber-100';
      default: return 'bg-blue-50 border-blue-100';
    }
  };

  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4 text-slate-400" />
        Timeline Analysis
      </h3>

      {items.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-4">No issues detected</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
          {items.map((item, idx) => (
            <div key={idx} className={`p-3 rounded-lg border ${getBgColor(item.type)} flex items-start gap-3`}>
              <div className="mt-0.5">{getIcon(item.type)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-mono text-slate-500">{formatTime(item.timestamp)}</span>
                  <span className="text-xs font-medium text-slate-600 bg-white px-1.5 py-0.5 rounded">
                    {item.category}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{item.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

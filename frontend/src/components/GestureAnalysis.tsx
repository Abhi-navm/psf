'use client';

import { Hand, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface GestureIssue {
  timestamp: number;
  gesture: string;
  severity: 'low' | 'medium' | 'high';
  suggestion: string;
  count?: number;
}

interface GestureAnalysisProps {
  issues: GestureIssue[];
}

export function GestureAnalysis({ issues }: GestureAnalysisProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getBadgeColor = (index: number, severity: string) => {
    if (severity === 'high') return 'bg-orange-500';
    if (severity === 'medium') return 'bg-amber-500';
    return 'bg-blue-500';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
          Gesture Analysis
        </h3>
        <span className="text-sm text-blue-600 font-medium">Key Issues: {issues.length}</span>
      </div>

      {issues.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-8">No gesture issues detected</p>
      ) : (
        <div className="space-y-3 max-h-[400px] overflow-y-auto">
          {issues.slice(0, 10).map((issue, idx) => (
            <div 
              key={idx} 
              className={`rounded-lg border transition-all ${
                expandedIndex === idx 
                  ? 'border-blue-300 bg-blue-50/50' 
                  : 'border-slate-200 bg-white hover:bg-slate-50'
              }`}
            >
              <button
                onClick={() => setExpandedIndex(expandedIndex === idx ? null : idx)}
                className="w-full flex items-center gap-3 p-4 text-left"
              >
                <div className={`w-8 h-8 rounded-full ${getBadgeColor(idx, issue.severity)} flex items-center justify-center flex-shrink-0`}>
                  <span className="text-sm font-bold text-white">{idx + 1}</span>
                </div>
                <p className="flex-1 text-sm text-slate-700">{issue.gesture}</p>
                {expandedIndex === idx ? (
                  <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
              </button>
              
              {expandedIndex === idx && issue.suggestion && (
                <div className="px-4 pb-4 ml-11">
                  <h4 className="text-sm font-semibold text-slate-700 mb-1">Corrective Measures</h4>
                  <p className="text-sm text-slate-600">{issue.suggestion}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

'use client';

import { useState } from 'react';
import { Sparkles, TrendingUp, AlertTriangle, ChevronDown, ChevronUp, Lightbulb } from 'lucide-react';

interface Improvement {
  description: string;
  tips?: string[];
  area?: string;
}

interface AISummaryProps {
  summary: string;
  strengths: string[];
  improvements: Improvement[];
}

export function AISummary({ summary, strengths, improvements }: AISummaryProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-indigo-500" />
        AI Summary
      </h3>
      <p className="text-sm text-slate-600 mb-4 leading-relaxed">{summary}</p>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Strengths */}
        <div className="bg-emerald-50 rounded-lg p-4">
          <h4 className="text-xs font-semibold text-emerald-700 mb-2 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            Strengths
          </h4>
          <ul className="space-y-1.5">
            {strengths.map((s, i) => (
              <li key={i} className="text-xs text-emerald-600 flex items-start gap-1.5">
                <span className="mt-1 w-1 h-1 rounded-full bg-emerald-400 flex-shrink-0" />
                {s}
              </li>
            ))}
          </ul>
        </div>

        {/* Improvements */}
        <div className="bg-amber-50 rounded-lg p-4">
          <h4 className="text-xs font-semibold text-amber-700 mb-2 flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            Areas to Improve
          </h4>
          <ul className="space-y-2">
            {improvements.map((item, i) => (
              <li key={i} className="text-xs text-amber-600">
                <div 
                  className={`flex items-start gap-1.5 ${item.tips && item.tips.length > 0 ? 'cursor-pointer hover:text-amber-700' : ''}`}
                  onClick={() => item.tips && item.tips.length > 0 && toggleExpand(i)}
                >
                  <span className="mt-1 w-1 h-1 rounded-full bg-amber-400 flex-shrink-0" />
                  <span className="flex-1">{item.description}</span>
                  {item.tips && item.tips.length > 0 && (
                    <span className="text-amber-500 ml-1">
                      {expandedIndex === i ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </span>
                  )}
                </div>
                
                {/* Expanded tips */}
                {expandedIndex === i && item.tips && item.tips.length > 0 && (
                  <div className="mt-2 ml-2.5 pl-2 border-l-2 border-amber-200 space-y-1.5">
                    <div className="text-[10px] font-semibold text-amber-700 flex items-center gap-1 mb-1">
                      <Lightbulb className="w-3 h-3" />
                      How to improve:
                    </div>
                    {item.tips.map((tip, j) => (
                      <div key={j} className="text-[11px] text-amber-700 bg-amber-100/50 rounded px-2 py-1">
                        {tip}
                      </div>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

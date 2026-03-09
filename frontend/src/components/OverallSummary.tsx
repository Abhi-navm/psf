'use client';

import { ChevronUp, ChevronDown, AlertCircle, Lightbulb } from 'lucide-react';
import { useState } from 'react';

interface VarianceItem {
  label: string;
  value: string;
}

interface OverallSummaryProps {
  score: number;
  confidenceIndex: number;
  adherenceToStandard: number;
  vocalDelivery: number;
  varianceItems?: VarianceItem[];
  aiCorrections?: string[];
}

export default function OverallSummary({
  score,
  confidenceIndex,
  adherenceToStandard,
  vocalDelivery,
  varianceItems = [],
  aiCorrections = [],
}: OverallSummaryProps) {
  const [varianceOpen, setVarianceOpen] = useState(true);
  const [correctionsOpen, setCorrectionsOpen] = useState(true);

  // Calculate gradient position based on score
  const gradientPosition = Math.min(100, Math.max(0, score));

  return (
    <div className="space-y-6">
      {/* Overall Summary Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">Overall Summary</h2>
        
        {/* Score Display */}
        <div className="flex items-baseline gap-1 mb-4">
          <span className="text-5xl font-bold text-slate-800">{Math.round(score)}</span>
          <span className="text-2xl text-slate-400">/100</span>
        </div>

        {/* Score Bar */}
        <div className="h-6 rounded-full overflow-hidden flex mb-4">
          {Array.from({ length: 25 }).map((_, i) => {
            const position = (i / 25) * 100;
            const isActive = position < gradientPosition;
            const isTransition = position >= gradientPosition - 10 && position < gradientPosition;
            
            let bgColor = 'bg-slate-200';
            if (isActive) {
              if (position < 40) bgColor = 'bg-blue-500';
              else if (position < 60) bgColor = 'bg-blue-400';
              else if (position < 75) bgColor = 'bg-amber-400';
              else bgColor = 'bg-red-400';
            } else if (position >= gradientPosition) {
              bgColor = 'bg-red-300';
            }
            
            return (
              <div
                key={i}
                className={`flex-1 h-full ${bgColor} ${i > 0 ? 'ml-0.5' : ''}`}
              />
            );
          })}
        </div>

        {/* Metrics */}
        <div className="flex gap-8 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-sm font-semibold text-blue-600">{confidenceIndex}%</span>
            <span className="text-sm text-slate-500">Confidence Index</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-slate-500" />
            <span className="text-sm font-semibold text-slate-600">{adherenceToStandard}%</span>
            <span className="text-sm text-slate-500">Adherence to Standard</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-amber-500" />
            <span className="text-sm font-semibold text-amber-600">{vocalDelivery}%</span>
            <span className="text-sm text-slate-500">Vocal Delivery</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: Variance Analysis + Corrections */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Critical Variance Analysis */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200">
          <button
            onClick={() => setVarianceOpen(!varianceOpen)}
            className="w-full p-4 flex items-center justify-between text-left"
          >
            <h3 className="font-semibold text-slate-800">Critical Variance Analysis</h3>
            {varianceOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
          </button>
          
          {varianceOpen && (
            <div className="px-4 pb-4 space-y-4">
              {varianceItems.length === 0 ? (
                <p className="text-sm text-slate-400">No variance data available</p>
              ) : (
                varianceItems.map((item, i) => (
                  <div key={`var-${i}`} className="flex gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-amber-600">{item.label || `Issue ${i + 1}`}:</span>
                      <span className="text-sm text-slate-600 ml-1">{item.value}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Recommended AI Corrections */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200">
          <button
            onClick={() => setCorrectionsOpen(!correctionsOpen)}
            className="w-full p-4 flex items-center justify-between text-left"
          >
            <h3 className="font-semibold text-slate-800">Recommended AI Corrections</h3>
            {correctionsOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
          </button>
          
          {correctionsOpen && (
            <div className="px-4 pb-4 space-y-3">
              {aiCorrections.length === 0 ? (
                <p className="text-sm text-slate-400">No corrections available</p>
              ) : (
                aiCorrections.map((correction, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="w-5 h-5 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Lightbulb className="w-3 h-3 text-purple-600" />
                    </div>
                    <div>
                      <span className="font-medium text-purple-600">Action {i + 1}:</span>
                      <span className="text-sm text-slate-600 ml-1">{correction}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

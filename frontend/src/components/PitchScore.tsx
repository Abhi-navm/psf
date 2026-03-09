'use client';

interface PitchScoreProps {
  score: number;
  maxScore?: number;
  metrics?: { label: string; value: number; color: string; skipped?: boolean }[];
}

export function PitchScore({ score, maxScore = 10, metrics = [] }: PitchScoreProps) {
  const percentage = (score / maxScore) * 100;
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const getColor = () => {
    if (percentage >= 80) return '#10b981';
    if (percentage >= 60) return '#f59e0b';
    if (percentage >= 40) return '#f97316';
    return '#ef4444';
  };

  const getLabel = () => {
    if (percentage >= 80) return 'Excellent';
    if (percentage >= 60) return 'Good';
    if (percentage >= 40) return 'Average';
    return 'Needs Work';
  };

  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">Pitch Score</h3>
      
      <div className="flex items-center justify-center mb-4">
        <div className="relative">
          <svg width="140" height="140" className="-rotate-90">
            <circle
              cx="70" cy="70" r={radius}
              stroke="#e2e8f0" strokeWidth="10" fill="none"
            />
            <circle
              cx="70" cy="70" r={radius}
              stroke={getColor()}
              strokeWidth="10"
              fill="none"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              className="transition-all duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold text-slate-800">{score.toFixed(1)}</span>
            <span className="text-xs text-slate-400">/ {maxScore}</span>
          </div>
        </div>
      </div>

      <p className="text-center text-sm font-medium mb-4" style={{ color: getColor() }}>
        {getLabel()}
      </p>

      {/* Metrics breakdown */}
      {metrics.length > 0 && (
        <div className="space-y-3">
          {metrics.map((metric, idx) => (
            <div key={idx}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-600">{metric.label}</span>
                {metric.skipped ? (
                  <span className="font-medium text-slate-400 italic">N/A</span>
                ) : (
                  <span className="font-medium text-slate-700">{metric.value.toFixed(1)}%</span>
                )}
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5">
                {metric.skipped ? (
                  <div className="h-1.5 rounded-full bg-slate-200 w-full" />
                ) : (
                  <div
                    className="h-1.5 rounded-full transition-all duration-700"
                    style={{ width: `${metric.value}%`, backgroundColor: metric.color }}
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

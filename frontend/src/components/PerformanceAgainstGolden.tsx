'use client';

interface MetricBadgeProps {
  value: number;
  maxValue?: number;
}

function MetricBadge({ value, maxValue = 5 }: MetricBadgeProps) {
  // Determine color based on score
  const percentage = (value / maxValue) * 100;
  let bgColor = 'bg-blue-500';
  let textColor = 'text-white';
  
  if (percentage < 40) {
    bgColor = 'bg-red-500';
  } else if (percentage < 60) {
    bgColor = 'bg-orange-500';
  } else if (percentage < 80) {
    bgColor = 'bg-blue-500';
  } else {
    bgColor = 'bg-blue-600';
  }

  return (
    <div className={`w-10 h-10 rounded-full ${bgColor} flex items-center justify-center`}>
      <span className={`text-sm font-bold ${textColor}`}>{Math.round(value)}</span>
    </div>
  );
}

interface PerformanceMetric {
  label: string;
  value: number;
  maxValue?: number;
}

interface PerformanceAgainstGoldenProps {
  metrics: PerformanceMetric[];
}

export default function PerformanceAgainstGolden({ metrics }: PerformanceAgainstGoldenProps) {
  // Split metrics into two columns
  const leftMetrics = metrics.filter((_, i) => i % 2 === 0);
  const rightMetrics = metrics.filter((_, i) => i % 2 === 1);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <h2 className="text-lg font-semibold text-slate-800 mb-6">Performance Against Golden Pitch Deck</h2>
      
      <div className="grid grid-cols-2 gap-x-12 gap-y-4">
        {/* Left Column */}
        <div className="space-y-4">
          {leftMetrics.map((metric, i) => (
            <div key={i} className="flex items-center justify-between">
              <span className="text-slate-600">{metric.label}</span>
              <MetricBadge value={metric.value} maxValue={metric.maxValue} />
            </div>
          ))}
        </div>
        
        {/* Right Column */}
        <div className="space-y-4">
          {rightMetrics.map((metric, i) => (
            <div key={i} className="flex items-center justify-between">
              <span className="text-slate-600">{metric.label}</span>
              <MetricBadge value={metric.value} maxValue={metric.maxValue} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

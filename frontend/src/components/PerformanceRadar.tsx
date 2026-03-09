'use client';

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';

interface RadarDataPoint {
  subject: string;
  value: number;
  fullMark: number;
}

interface PerformanceRadarProps {
  data: RadarDataPoint[];
  title?: string;
}

export function PerformanceRadar({ data, title = 'Performance Overview' }: PerformanceRadarProps) {
  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={250}>
        <RadarChart data={data}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#64748b' }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Score"
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

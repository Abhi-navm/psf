'use client';

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';

interface PitchAnalysisRadarProps {
  clarity: number;
  confidence: number;
  energy: number;
  voiceControl: number;
  executiveTone: number;
}

export function PitchAnalysisRadar({ clarity, confidence, energy, voiceControl, executiveTone }: PitchAnalysisRadarProps) {
  const data = [
    { subject: 'Clarity', value: clarity, fullMark: 100 },
    { subject: 'Confidence', value: confidence, fullMark: 100 },
    { subject: 'Energy', value: energy, fullMark: 100 },
    { subject: 'Voice Control', value: voiceControl, fullMark: 100 },
    { subject: 'Executive Tone', value: executiveTone, fullMark: 100 },
  ];

  return (
    <div className="card p-6">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">Pitch Analysis</h3>
      <ResponsiveContainer width="100%" height={250}>
        <RadarChart data={data}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#64748b' }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Score"
            dataKey="value"
            stroke="#8b5cf6"
            fill="#8b5cf6"
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

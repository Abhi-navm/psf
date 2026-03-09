'use client';

import { Star, Check, X, AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface ComparisonResultsProps {
  report: {
    golden_pitch_deck_id?: string;
    comparison_overall_score?: number;
    content_similarity_score?: number;
    keyword_coverage_score?: number;
    voice_similarity_score?: number;
    pose_similarity_score?: number;
    keyword_comparison?: {
      matched_keywords?: string[];
      missing_keywords?: string[];
      coverage_score?: number;
    };
    voice_comparison?: {
      comparisons?: Record<string, {
        reference?: number;
        uploaded?: number;
        similarity?: number;
        feedback?: string;
      }>;
    };
    pose_comparison?: {
      comparisons?: Record<string, {
        reference?: number;
        uploaded?: number;
        similarity?: number;
      }>;
    };
  };
}

export default function ComparisonResults({ report }: ComparisonResultsProps) {
  if (!report.golden_pitch_deck_id || report.comparison_overall_score === undefined) {
    return null;
  }

  const overallScore = report.comparison_overall_score || 0;
  const contentScore = report.content_similarity_score || 0;
  const keywordScore = report.keyword_coverage_score || 0;
  const voiceScore = report.voice_similarity_score || 0;
  const poseScore = report.pose_similarity_score || 0;

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-yellow-100';
    if (score >= 40) return 'bg-orange-100';
    return 'bg-red-100';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 80) return 'Excellent Match';
    if (score >= 60) return 'Good Match';
    if (score >= 40) return 'Moderate Match';
    return 'Needs Improvement';
  };

  const matchedKeywords = report.keyword_comparison?.matched_keywords || [];
  const missingKeywords = report.keyword_comparison?.missing_keywords || [];

  return (
    <div className="card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Star className="w-5 h-5 text-yellow-500" />
        <h3 className="text-lg font-semibold text-slate-800">Comparison with Golden Pitch Deck</h3>
      </div>

      {/* Overall Comparison Score */}
      <div className={`p-4 rounded-lg ${getScoreBgColor(overallScore)} mb-6`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-600">Overall Similarity</p>
            <p className={`text-3xl font-bold ${getScoreColor(overallScore)}`}>
              {overallScore.toFixed(0)}%
            </p>
          </div>
          <div className="text-right">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getScoreBgColor(overallScore)} ${getScoreColor(overallScore)}`}>
              {getScoreLabel(overallScore)}
            </span>
          </div>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <ScoreCard label="Content" score={contentScore} />
        <ScoreCard label="Keywords" score={keywordScore} />
        <ScoreCard label="Voice" score={voiceScore} />
        <ScoreCard label="Pose" score={poseScore} />
      </div>

      {/* Keyword Comparison */}
      {(matchedKeywords.length > 0 || missingKeywords.length > 0) && (
        <div className="border-t pt-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Keyword Coverage</h4>
          <div className="grid md:grid-cols-2 gap-4">
            {/* Matched Keywords */}
            {matchedKeywords.length > 0 && (
              <div>
                <div className="flex items-center gap-1 text-green-600 text-sm font-medium mb-2">
                  <Check className="w-4 h-4" />
                  Covered ({matchedKeywords.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {matchedKeywords.slice(0, 8).map((keyword, idx) => (
                    <span 
                      key={idx}
                      className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full"
                    >
                      {keyword}
                    </span>
                  ))}
                  {matchedKeywords.length > 8 && (
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs rounded-full">
                      +{matchedKeywords.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Missing Keywords */}
            {missingKeywords.length > 0 && (
              <div>
                <div className="flex items-center gap-1 text-red-500 text-sm font-medium mb-2">
                  <X className="w-4 h-4" />
                  Missing ({missingKeywords.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {missingKeywords.slice(0, 8).map((keyword, idx) => (
                    <span 
                      key={idx}
                      className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded-full"
                    >
                      {keyword}
                    </span>
                  ))}
                  {missingKeywords.length > 8 && (
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-500 text-xs rounded-full">
                      +{missingKeywords.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Voice Comparison Details */}
      {report.voice_comparison?.comparisons && Object.keys(report.voice_comparison.comparisons).length > 0 && (
        <div className="border-t pt-4 mt-4">
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Voice Metrics Comparison</h4>
          <div className="space-y-2">
            {Object.entries(report.voice_comparison.comparisons).map(([key, comp]) => (
              <MetricComparison
                key={key}
                label={formatMetricLabel(key)}
                reference={comp.reference}
                uploaded={comp.uploaded}
                similarity={comp.similarity}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ label, score }: { label: string; score: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return 'text-green-600';
    if (s >= 60) return 'text-yellow-600';
    if (s >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  return (
    <div className="text-center p-3 bg-slate-50 rounded-lg">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${getColor(score)}`}>
        {score > 0 ? `${score.toFixed(0)}%` : '--'}
      </p>
    </div>
  );
}

function MetricComparison({ 
  label, 
  reference, 
  uploaded, 
  similarity 
}: { 
  label: string; 
  reference?: number; 
  uploaded?: number; 
  similarity?: number;
}) {
  const diff = uploaded !== undefined && reference !== undefined ? uploaded - reference : 0;
  
  return (
    <div className="flex items-center justify-between py-2 px-3 bg-slate-50 rounded">
      <span className="text-sm text-slate-600">{label}</span>
      <div className="flex items-center gap-4 text-sm">
        <span className="text-slate-400">
          Ref: {reference !== undefined ? reference.toFixed(0) : '--'}
        </span>
        <span className="text-slate-600 font-medium">
          You: {uploaded !== undefined ? uploaded.toFixed(0) : '--'}
        </span>
        {diff !== 0 && (
          <span className={`flex items-center gap-1 ${diff > 0 ? 'text-green-500' : 'text-red-500'}`}>
            {diff > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {diff > 0 ? '+' : ''}{diff.toFixed(0)}
          </span>
        )}
        {similarity !== undefined && (
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            similarity >= 80 ? 'bg-green-100 text-green-700' :
            similarity >= 60 ? 'bg-yellow-100 text-yellow-700' :
            'bg-red-100 text-red-600'
          }`}>
            {similarity.toFixed(0)}% match
          </span>
        )}
      </div>
    </div>
  );
}

function formatMetricLabel(key: string): string {
  const labels: Record<string, string> = {
    speaking_rate: 'Speaking Rate',
    pitch: 'Pitch',
    energy: 'Energy',
    confidence: 'Confidence',
    pace: 'Pace',
  };
  return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

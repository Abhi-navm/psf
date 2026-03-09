'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getAnalysis, getAnalysisStatus } from '@/lib/api';
import { VideoPlayer, PitchAnalysisRadar, GestureAnalysis, OverallSummary, PerformanceAgainstGolden, PitchTimeline } from '@/components';
import { Loader2 } from 'lucide-react';

export default function AnalysisPage() {
  const params = useParams();
  const analysisId = params.id as string;
  const [analysis, setAnalysis] = useState<any>(null);
  const [status, setStatus] = useState<string>('loading');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!analysisId) return;

    const poll = async () => {
      try {
        const statusData = await getAnalysisStatus(analysisId);
        setStatus(statusData.status);
        setProgress(statusData.progress || 0);

        if (statusData.status === 'completed') {
          const fullAnalysis = await getAnalysis(analysisId);
          setAnalysis(fullAnalysis);
        } else if (statusData.status !== 'failed') {
          setTimeout(poll, 2000);
        }
      } catch (error) {
        console.error('Error polling status:', error);
        setTimeout(poll, 5000);
      }
    };

    poll();
  }, [analysisId]);

  if (status === 'loading' || (status !== 'completed' && status !== 'failed')) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mx-auto mb-4" />
          <p className="text-slate-600 font-medium">Analyzing your pitch...</p>
          <p className="text-sm text-slate-400 mt-1">{status} - {progress}%</p>
          <div className="w-64 bg-slate-100 rounded-full h-2 mt-4 mx-auto">
            <div className="bg-indigo-500 h-2 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-500 font-medium text-lg">Analysis Failed</p>
          <p className="text-sm text-slate-400 mt-1">Something went wrong. Please try again.</p>
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  // Extract data from analysis
  const report = analysis.report || {};
  const voiceAnalysis = analysis.voice_analysis || null;
  const facialAnalysis = analysis.facial_analysis || {};
  const poseAnalysis = analysis.pose_analysis || {};
  const contentAnalysis = analysis.content_analysis || {};
  const isAudioOnly = analysis.video?.is_audio_only || false;
  const hasAudio = voiceAnalysis !== null && voiceAnalysis.overall_score !== undefined;
  const contentSkipped = !analysis.content_analysis || analysis.content_analysis.overall_score == null;
  
  // For audio-only files, skip facial/pose in display
  const facialSkipped = isAudioOnly || (!facialAnalysis.overall_score && facialAnalysis.overall_score !== 0);
  const poseSkipped = isAudioOnly || (!poseAnalysis.overall_score && poseAnalysis.overall_score !== 0);

  const overallScore = report.overall_score || 0;
  const videoUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/videos/${analysis.video_id}/stream`;

  // Build timeline items from report issues
  const timelineItems = (report.timestamped_issues || []).map((issue: any) => ({
    timestamp: issue.timestamp || 0,
    type: issue.severity === 'high' ? 'error' : issue.severity === 'medium' ? 'warning' : 'info',
    category: issue.category || 'General',
    title: issue.description || issue.issue || 'Issue',
    description: issue.suggestion || '',
  }));

  // Build gesture issues from pose analysis
  const gestureIssues = (poseAnalysis.issues || poseAnalysis.pose_timeline || []).map((issue: any) => ({
    timestamp: issue.timestamp || (issue.timestamps ? issue.timestamps[0] : 0),
    gesture: issue.description || issue.type || issue.gesture || issue.issue || 'Unknown',
    severity: issue.severity || 'medium',
    suggestion: issue.suggestion || issue.message || '',
    count: issue.occurrence_count || 1,
  }));

  // Calculate metrics for OverallSummary
  const confidenceIndex = hasAudio ? (voiceAnalysis.confidence_score || 0) : 0;
  const adherenceToStandard = report.comparison_overall_score || report.content_similarity_score || 0;
  const vocalDelivery = hasAudio ? Math.round((voiceAnalysis.clarity_score + voiceAnalysis.pace_score + voiceAnalysis.energy_score) / 3) : 0;

  // Build variance items from improvements
  const varianceItems = (report.improvements || report.areas_for_improvement || []).slice(0, 3).map((item: any) => ({
    label: typeof item === 'string' ? item : item.area || item.description || '',
    value: typeof item === 'string' ? item : item.description || item.suggestion || '',
  }));

  // Build AI corrections from improvements
  const aiCorrections = (report.improvements || report.areas_for_improvement || []).slice(0, 3).map((item: any) => 
    typeof item === 'string' ? item : item.description || item.suggestion || ''
  );

  // Get comparison scores from report - these come from backend AnalysisReport model
  const keywordCoverageScore = report.keyword_coverage_score || 0;
  const semanticSimilarityScore = report.content_comparison?.semantic_similarity || report.content_similarity_score || 0;
  const voiceSimilarityScore = report.voice_similarity_score || 0;
  const poseSimilarityScore = report.pose_similarity_score || 0;
  const facialSimilarityScore = report.facial_similarity_score || 0;

  // Build performance metrics for golden pitch comparison
  // Use comparison similarity scores (how close to golden), not raw analysis scores
  const performanceMetrics = [
    { label: 'Voice Quality', value: voiceSimilarityScore, maxValue: 100 },
    { label: 'Facial Expression', value: facialSkipped ? 0 : facialSimilarityScore, maxValue: 100 },
    { label: 'Keyword Match', value: keywordCoverageScore, maxValue: 100 },
    { label: 'Context Alignment', value: semanticSimilarityScore, maxValue: 100 },
    { label: 'Confidence', value: poseSimilarityScore, maxValue: 100 },
    { label: 'Content Score', value: contentSkipped ? 0 : (contentAnalysis.overall_score || 0), maxValue: 100 },
  ];

  return (
    <div className="p-6 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Pitch Analysis</h1>
        <p className="text-slate-500 mt-1">AI-powered analysis of your sales pitch</p>
      </div>

      {/* Top Section: Video Player + Pitch Timeline */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <div>
          <VideoPlayer src={videoUrl} markers={timelineItems.map((item: any) => ({
            time: item.timestamp,
            type: item.type,
            label: item.description,
          }))} />
        </div>
        <PitchTimeline issues={timelineItems} />
      </div>

      {/* Overall Summary */}
      <div className="mb-6">
        <OverallSummary
          score={overallScore}
          confidenceIndex={confidenceIndex}
          adherenceToStandard={adherenceToStandard}
          vocalDelivery={vocalDelivery}
          varianceItems={varianceItems}
          aiCorrections={aiCorrections}
        />
      </div>

      {/* Bottom Section: Performance Metrics + Radar + Gesture */}
      <div className="grid lg:grid-cols-3 gap-6">
        <PerformanceAgainstGolden metrics={performanceMetrics} />
        
        {hasAudio ? (
          <PitchAnalysisRadar
            clarity={voiceAnalysis.clarity_score || 0}
            confidence={voiceAnalysis.confidence_score || 0}
            energy={voiceAnalysis.energy_score || 0}
            voiceControl={voiceAnalysis.pace_score || 0}
            executiveTone={voiceAnalysis.tone_score || 0}
          />
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex items-center justify-center">
            <div className="text-center">
              <p className="text-slate-400 text-sm font-medium">Pitch Analysis</p>
              <p className="text-slate-300 text-xs mt-2">
                {isAudioOnly ? 'Audio analysis in progress or failed' : 'No audio detected in this video'}
              </p>
            </div>
          </div>
        )}
        
        <GestureAnalysis issues={gestureIssues} />
      </div>
    </div>
  );
}

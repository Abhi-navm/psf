"""
Analysis endpoints for starting, monitoring, and retrieving results.
"""

import asyncio
from collections import Counter
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.core.config import settings
from app.db.database import get_db
from app.db.models import (
    Video,
    Analysis,
    AnalysisStatus,
    Transcription,
    VoiceAnalysis,
    FacialAnalysis,
    PoseAnalysis,
    ContentAnalysis,
    AnalysisReport,
)
from app.api.schemas import (
    AnalysisCreate,
    AnalysisStatusResponse,
    FullAnalysisResponse,
    TranscriptionResponse,
    VoiceAnalysisResponse,
    FacialAnalysisResponse,
    PoseAnalysisResponse,
    ContentAnalysisResponse,
    AnalysisReportResponse,
    ErrorResponse,
    WorkerAggregateRequest,
    WorkerAggregateResponse,
)
from app.tasks.analysis_tasks import run_full_analysis
from app.api.dependencies import get_user_id

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def _run_inprocess_safely(task_func, *args):
    """Run fallback background task and absorb exceptions already persisted by task code."""
    try:
        await asyncio.to_thread(task_func, *args)
    except Exception as e:
        logger.error(f"In-process analysis task failed: {e}")


@router.post(
    "",
    response_model=AnalysisStatusResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def start_analysis(
    request: AnalysisCreate,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_user_id),
):
    """
    Start a new analysis for a video.
    
    This will queue the video for processing through:
    1. Audio extraction
    2. Speech transcription (Whisper)
    3. Voice analysis (SpeechBrain/Librosa)
    4. Facial expression analysis (DeepFace)
    5. Body pose analysis (MediaPipe)
    6. Content analysis (Ollama/Llama 3)
    7. Report generation
    """
    video_id = request.video_id
    
    # Check video exists
    video_result = await db.execute(select(Video).where(Video.id == video_id))
    video = video_result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail={"error": "Video not found", "code": "VIDEO_NOT_FOUND"}
        )
    
    # Check for existing in-progress analysis
    existing_result = await db.execute(
        select(Analysis)
        .where(Analysis.video_id == video_id)
        .where(Analysis.status.in_([
            AnalysisStatus.PENDING,
            AnalysisStatus.PROCESSING,
            AnalysisStatus.EXTRACTING_AUDIO,
            AnalysisStatus.TRANSCRIBING,
            AnalysisStatus.ANALYZING_VOICE,
            AnalysisStatus.ANALYZING_FACIAL,
            AnalysisStatus.ANALYZING_POSE,
            AnalysisStatus.ANALYZING_CONTENT,
            AnalysisStatus.GENERATING_REPORT,
        ]))
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Analysis already in progress",
                "code": "ANALYSIS_IN_PROGRESS",
                "details": {"analysis_id": existing.id},
            }
        )
    
    # Create new analysis
    effective_user_id = request.user_id or user_id
    analysis = Analysis(
        video_id=video_id,
        user_id=effective_user_id,
        golden_pitch_deck_id=request.golden_pitch_deck_id,
        skip_comparison=request.skip_comparison,
        status=AnalysisStatus.PENDING,
        progress=0,
        started_at=datetime.utcnow(),
    )
    
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    
    # Dispatch analysis via Celery when available, otherwise run in-process.
    if settings.runpod_endpoint_id and settings.runpod_api_key:
        from app.tasks.analysis_tasks import run_via_runpod_task
        task = run_via_runpod_task.delay(
            analysis_id=analysis.id,
            video_id=video_id,
            video_path=video.file_path,
            is_audio_only=video.is_audio_only if hasattr(video, 'is_audio_only') else False,
            golden_pitch_deck_id=request.golden_pitch_deck_id,
            skip_comparison=request.skip_comparison,
        )
        if task is not None and getattr(task, "id", None):
            analysis.celery_task_id = task.id
            await db.commit()
            logger.info(f"Analysis {analysis.id} dispatched to RunPod via Celery task {task.id}")
        else:
            analysis.celery_task_id = f"inprocess-{analysis.id}"
            await db.commit()
            logger.warning(f"Celery unavailable. Running RunPod analysis in-process for {analysis.id}")
            asyncio.create_task(_run_inprocess_safely(
                run_via_runpod_task,
                None,
                analysis.id,
                video_id,
                video.file_path,
                video.is_audio_only if hasattr(video, 'is_audio_only') else False,
                request.golden_pitch_deck_id,
                request.skip_comparison,
            ))
    else:
        # Queue Celery task with comparison parameters
        task = run_full_analysis.delay(
            analysis_id=analysis.id,
            video_id=video_id,
            video_path=video.file_path,
            golden_pitch_deck_id=request.golden_pitch_deck_id,
            skip_comparison=request.skip_comparison,
            is_audio_only=video.is_audio_only if hasattr(video, 'is_audio_only') else False,
        )
        if task is not None and getattr(task, "id", None):
            analysis.celery_task_id = task.id
            await db.commit()
        else:
            analysis.celery_task_id = f"inprocess-{analysis.id}"
            await db.commit()
            logger.warning(f"Celery unavailable. Running local analysis in-process for {analysis.id}")
            asyncio.create_task(_run_inprocess_safely(
                run_full_analysis,
                None,
                analysis.id,
                video_id,
                video.file_path,
                request.golden_pitch_deck_id,
                request.skip_comparison,
                video.is_audio_only if hasattr(video, 'is_audio_only') else False,
            ))
    
    logger.info(f"Analysis started: {analysis.id} for video {video_id}")
    
    return analysis


@router.get(
    "/{analysis_id}",
    response_model=FullAnalysisResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get complete analysis results by ID."""
    result = await db.execute(
        select(Analysis)
        .options(
            selectinload(Analysis.video),
            selectinload(Analysis.transcription),
            selectinload(Analysis.voice_analysis),
            selectinload(Analysis.facial_analysis),
            selectinload(Analysis.pose_analysis),
            selectinload(Analysis.content_analysis),
            selectinload(Analysis.report),
        )
        .where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Analysis not found", "code": "ANALYSIS_NOT_FOUND"}
        )
    
    return analysis


@router.get(
    "/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_analysis_status(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get analysis status (for polling during processing)."""
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Analysis not found", "code": "ANALYSIS_NOT_FOUND"}
        )
    
    return analysis


@router.get(
    "/{analysis_id}/transcription",
    response_model=TranscriptionResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_transcription(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get transcription results for an analysis."""
    result = await db.execute(
        select(Transcription).where(Transcription.analysis_id == analysis_id)
    )
    transcription = result.scalar_one_or_none()
    
    if not transcription:
        raise HTTPException(
            status_code=404,
            detail={"error": "Transcription not found", "code": "TRANSCRIPTION_NOT_FOUND"}
        )
    
    return transcription


@router.get(
    "/{analysis_id}/voice",
    response_model=VoiceAnalysisResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_voice_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get voice analysis results."""
    result = await db.execute(
        select(VoiceAnalysis).where(VoiceAnalysis.analysis_id == analysis_id)
    )
    voice_analysis = result.scalar_one_or_none()
    
    if not voice_analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Voice analysis not found", "code": "VOICE_ANALYSIS_NOT_FOUND"}
        )
    
    return voice_analysis


@router.get(
    "/{analysis_id}/facial",
    response_model=FacialAnalysisResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_facial_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get facial expression analysis results."""
    result = await db.execute(
        select(FacialAnalysis).where(FacialAnalysis.analysis_id == analysis_id)
    )
    facial_analysis = result.scalar_one_or_none()
    
    if not facial_analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Facial analysis not found", "code": "FACIAL_ANALYSIS_NOT_FOUND"}
        )
    
    return facial_analysis


@router.get(
    "/{analysis_id}/pose",
    response_model=PoseAnalysisResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_pose_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get body pose analysis results."""
    result = await db.execute(
        select(PoseAnalysis).where(PoseAnalysis.analysis_id == analysis_id)
    )
    pose_analysis = result.scalar_one_or_none()
    
    if not pose_analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Pose analysis not found", "code": "POSE_ANALYSIS_NOT_FOUND"}
        )
    
    return pose_analysis


@router.get(
    "/{analysis_id}/content",
    response_model=ContentAnalysisResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_content_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get speech content analysis results."""
    result = await db.execute(
        select(ContentAnalysis).where(ContentAnalysis.analysis_id == analysis_id)
    )
    content_analysis = result.scalar_one_or_none()
    
    if not content_analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Content analysis not found", "code": "CONTENT_ANALYSIS_NOT_FOUND"}
        )
    
    return content_analysis


@router.get(
    "/{analysis_id}/report",
    response_model=AnalysisReportResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_analysis_report(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the final analysis report."""
    result = await db.execute(
        select(AnalysisReport).where(AnalysisReport.analysis_id == analysis_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail={"error": "Report not found", "code": "REPORT_NOT_FOUND"}
        )
    
    return report


@router.get(
    "/video/{video_id}",
    response_model=list[AnalysisStatusResponse],
)
async def list_analyses_for_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all analyses for a specific video."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.video_id == video_id)
        .order_by(Analysis.created_at.desc())
    )
    analyses = result.scalars().all()
    
    return analyses


@router.delete(
    "/{analysis_id}",
    responses={404: {"model": ErrorResponse}},
)
async def cancel_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or in-progress analysis."""
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail={"error": "Analysis not found", "code": "ANALYSIS_NOT_FOUND"}
        )
    
    # Try to revoke Celery task
    if analysis.celery_task_id:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(analysis.celery_task_id, terminate=True)
    
    # Update status
    analysis.status = AnalysisStatus.FAILED
    analysis.error_message = "Cancelled by user"
    await db.commit()
    
    logger.info(f"Analysis cancelled: {analysis_id}")
    
    return {"message": "Analysis cancelled"}


@router.post(
    "/aggregate",
    response_model=WorkerAggregateResponse,
    responses={400: {"model": ErrorResponse}},
)
async def aggregate_analyses(
    request: WorkerAggregateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate AI recommendations across multiple analyses for a single worker.

    Given a list of analysis IDs, returns:
    - Average scores across all analyses
    - Recurring issues sorted by frequency
    - Consolidated AI recommendations prioritized by how often they appear
    - Common filler words across all videos
    - Score trend over time
    """
    if len(request.analysis_ids) > 100:
        raise HTTPException(
            status_code=400,
            detail={"error": "Maximum 100 analysis IDs", "code": "TOO_MANY_IDS"},
        )

    # Fetch all completed analyses with reports and content analysis
    result = await db.execute(
        select(Analysis)
        .options(
            selectinload(Analysis.report),
            selectinload(Analysis.content_analysis),
            selectinload(Analysis.voice_analysis),
        )
        .where(
            Analysis.id.in_(request.analysis_ids),
            Analysis.status == AnalysisStatus.COMPLETED,
        )
    )
    analyses = result.scalars().all()

    if not analyses:
        raise HTTPException(
            status_code=400,
            detail={"error": "No completed analyses found for given IDs", "code": "NO_COMPLETED_ANALYSES"},
        )

    total = len(analyses)

    # ── Collect scores ──
    overall_scores, voice_scores, facial_scores = [], [], []
    pose_scores, content_scores, comparison_scores = [], [], []
    score_trend = []

    for a in sorted(analyses, key=lambda x: x.created_at):
        r = a.report
        if not r:
            continue
        overall_scores.append(r.overall_score)
        voice_scores.append(r.voice_score)
        facial_scores.append(r.facial_score)
        pose_scores.append(r.pose_score)
        content_scores.append(r.content_score)
        if r.comparison_overall_score is not None:
            comparison_scores.append(r.comparison_overall_score)
        score_trend.append({
            "analysis_id": a.id,
            "date": a.created_at.isoformat(),
            "overall_score": r.overall_score,
        })

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0.0

    # ── Aggregate issues from improvements + recommendations ──
    issue_counter: Counter = Counter()      # (category, issue_key) -> count
    issue_details: dict = {}                # (category, issue_key) -> {description, suggestion, severity}
    rec_counter: Counter = Counter()        # (category, title) -> count
    rec_details: dict = {}                  # (category, title) -> {description, priority}
    filler_counter: Counter = Counter()     # word -> total count

    for a in analyses:
        r = a.report
        if not r:
            continue

        # Improvements (per-video issues)
        for imp in (r.improvements or []):
            area = imp.get("area", "General")
            desc = imp.get("description", "")
            key = (area, desc)
            issue_counter[key] += 1
            if key not in issue_details:
                issue_details[key] = {
                    "suggestion": imp.get("suggestion", ""),
                    "severity": imp.get("priority", "medium"),
                }

        # Recommendations (includes comparison recs)
        for rec in (r.recommendations or []):
            cat = rec.get("category", "general")
            title = rec.get("title", "")
            key = (cat, title)
            rec_counter[key] += 1
            if key not in rec_details:
                rec_details[key] = {
                    "description": rec.get("description", ""),
                    "priority": rec.get("priority", "medium"),
                }

        # Filler words from content analysis
        ca = a.content_analysis
        if ca and ca.filler_words:
            for fw in ca.filler_words:
                word = fw.get("word", "") if isinstance(fw, dict) else str(fw)
                count = fw.get("count", 1) if isinstance(fw, dict) else 1
                filler_counter[word] += count

    # ── Build recurring issues (sorted by frequency) ──
    recurring_issues = []
    for (category, desc), count in issue_counter.most_common():
        details = issue_details[(category, desc)]
        recurring_issues.append({
            "category": category,
            "issue": desc,
            "description": desc,
            "suggestion": details["suggestion"],
            "severity": details["severity"],
            "occurrence_count": count,
            "total_analyses": total,
            "frequency_percent": round(count / total * 100, 1),
        })

    # ── Build aggregated recommendations (sorted by frequency) ──
    aggregated_recs = []
    for (cat, title), count in rec_counter.most_common():
        details = rec_details[(cat, title)]
        aggregated_recs.append({
            "category": cat,
            "title": title,
            "description": details["description"],
            "priority": details["priority"],
            "occurrence_count": count,
            "frequency_percent": round(count / total * 100, 1),
        })

    # ── Common filler words ──
    common_fillers = [
        {"word": word, "total_count": count, "avg_per_video": round(count / total, 1)}
        for word, count in filler_counter.most_common(10)
    ]

    return WorkerAggregateResponse(
        total_analyses=total,
        avg_overall_score=_avg(overall_scores),
        avg_voice_score=_avg(voice_scores),
        avg_facial_score=_avg(facial_scores),
        avg_pose_score=_avg(pose_scores),
        avg_content_score=_avg(content_scores),
        avg_comparison_score=_avg(comparison_scores) if comparison_scores else None,
        recurring_issues=recurring_issues,
        aggregated_recommendations=aggregated_recs,
        common_filler_words=common_fillers,
        score_trend=score_trend,
    )

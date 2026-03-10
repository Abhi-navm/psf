"""
Analysis endpoints for starting, monitoring, and retrieving results.
"""

import threading
from datetime import datetime
from typing import Optional

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
)
from app.tasks.analysis_tasks import run_full_analysis

router = APIRouter(prefix="/analyses", tags=["analyses"])


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
    analysis = Analysis(
        video_id=video_id,
        status=AnalysisStatus.PENDING,
        progress=0,
        started_at=datetime.utcnow(),
    )
    
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    
    # Dispatch analysis
    if settings.runpod_endpoint_id and settings.runpod_api_key:
        from app.tasks.analysis_tasks import _run_via_runpod

        def _bg():
            try:
                _run_via_runpod(
                    analysis_id=analysis.id,
                    video_id=video_id,
                    video_path=video.file_path,
                    is_audio_only=video.is_audio_only if hasattr(video, 'is_audio_only') else False,
                )
            except Exception as e:
                logger.error(f"RunPod background thread failed: {e}")

        t = threading.Thread(target=_bg, daemon=True)
        t.start()
        logger.info(f"Analysis {analysis.id} dispatched to RunPod (background thread)")
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
        # Update with task ID
        analysis.celery_task_id = task.id
        await db.commit()
    
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

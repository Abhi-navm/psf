"""
Video upload and management endpoints.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    VideoTooLargeError,
    InvalidVideoFormatError,
    VideoNotFoundError,
)
from app.db.database import get_db
from app.db.models import Video, Analysis, AnalysisReport, AnalysisStatus
from app.api.schemas import VideoResponse, VideoListResponse, VideoWithAnalysisResponse, ErrorResponse

router = APIRouter(prefix="/videos", tags=["videos"])

# Allowed video formats
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
}

# Allowed audio formats
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "audio/x-ms-wma",
}

# Combined allowed formats
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS
ALLOWED_MIME_TYPES = ALLOWED_VIDEO_MIME_TYPES | ALLOWED_AUDIO_MIME_TYPES


def get_upload_path() -> Path:
    """Get the upload directory path."""
    upload_path = Path(settings.local_storage_path)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


@router.post(
    "/upload",
    response_model=VideoResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
    },
)
async def upload_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video file for analysis.
    
    - Max file size: 500MB (configurable)
    - Supported formats: MP4, MOV, AVI, MKV, WebM, M4V
    """
    logger.info(f"Uploading video: {file.filename}")
    
    # Validate file extension
    original_filename = file.filename or "video.mp4"
    extension = Path(original_filename).suffix.lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid file format: {extension}",
                "code": "INVALID_VIDEO_FORMAT",
                "details": {"allowed_formats": list(ALLOWED_EXTENSIONS)},
            }
        )
    
    # Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
        logger.warning(f"Unexpected MIME type: {content_type}, allowing based on extension")
    
    # Generate unique filename
    video_id = str(uuid.uuid4())
    new_filename = f"{video_id}{extension}"
    
    # Prepare upload directory (use absolute paths for Celery worker compatibility)
    upload_dir = (get_upload_path() / "videos").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = (upload_dir / new_filename).resolve()
    
    # Save file and check size
    file_size = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                
                # Check size limit
                if file_size > settings.max_video_size_bytes:
                    buffer.close()
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "error": f"File too large. Max size: {settings.max_video_size_mb}MB",
                            "code": "VIDEO_TOO_LARGE",
                        }
                    )
                
                buffer.write(chunk)
        
        logger.info(f"File saved: {file_path}, size: {file_size / 1024 / 1024:.2f}MB")
        
        # Extract video metadata
        metadata = await extract_video_metadata(str(file_path))
        
        # Check duration limit
        duration = metadata.get("duration", 0)
        if duration > settings.max_video_duration_seconds:
            os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"File too long ({duration:.0f}s). Max: {settings.max_video_duration_seconds}s",
                    "code": "FILE_TOO_LONG",
                }
            )
        
        # Determine if audio-only file
        is_audio_only = extension in ALLOWED_AUDIO_EXTENSIONS
        
        # Create database record
        video = Video(
            id=video_id,
            filename=new_filename,
            original_filename=original_filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=content_type,
            duration=metadata.get("duration"),
            width=metadata.get("width") if not is_audio_only else None,
            height=metadata.get("height") if not is_audio_only else None,
            fps=metadata.get("fps") if not is_audio_only else None,
            is_audio_only=is_audio_only,
        )
        
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        logger.info(f"Video uploaded successfully: {video_id}")
        
        return video
        
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on error
        if file_path.exists():
            os.remove(file_path)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def extract_video_metadata(file_path: str) -> dict:
    """Extract metadata from video file."""
    try:
        from moviepy.editor import VideoFileClip
        
        video = VideoFileClip(file_path)
        metadata = {
            "duration": video.duration,
            "width": video.size[0],
            "height": video.size[1],
            "fps": video.fps,
        }
        video.close()
        return metadata
    except Exception as e:
        logger.warning(f"Could not extract metadata: {e}")
        return {}


@router.get(
    "",
    response_model=VideoListResponse,
)
async def list_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded videos with pagination and analysis info."""
    offset = (page - 1) * page_size
    
    # Get total count
    count_result = await db.execute(select(func.count(Video.id)))
    total = count_result.scalar() or 0
    
    # Get videos
    result = await db.execute(
        select(Video)
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    videos = result.scalars().all()
    
    # Build response with analysis info
    videos_with_analysis = []
    for video in videos:
        # Get the latest analysis for this video
        analysis_result = await db.execute(
            select(Analysis)
            .where(Analysis.video_id == video.id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()
        
        # Get report if analysis exists and is completed
        overall_score = None
        comparison_score = None
        if analysis and analysis.status == AnalysisStatus.COMPLETED:
            report_result = await db.execute(
                select(AnalysisReport)
                .where(AnalysisReport.analysis_id == analysis.id)
            )
            report = report_result.scalar_one_or_none()
            if report:
                overall_score = report.overall_score
                comparison_score = report.comparison_overall_score
        
        videos_with_analysis.append(VideoWithAnalysisResponse(
            id=video.id,
            original_filename=video.original_filename,
            filename=video.filename,
            file_path=video.file_path,
            file_size=video.file_size,
            mime_type=video.mime_type,
            duration=video.duration,
            width=video.width,
            height=video.height,
            fps=video.fps,
            is_audio_only=video.is_audio_only if hasattr(video, 'is_audio_only') else False,
            created_at=video.created_at,
            analysis_id=analysis.id if analysis else None,
            analysis_status=analysis.status.value if analysis else None,
            overall_score=overall_score,
            comparison_score=comparison_score,
        ))
    
    return VideoListResponse(
        videos=videos_with_analysis,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get video details by ID."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail={"error": "Video not found", "code": "VIDEO_NOT_FOUND"}
        )
    
    return video


@router.delete(
    "/{video_id}",
    responses={404: {"model": ErrorResponse}},
)
async def delete_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a video and its associated analyses."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail={"error": "Video not found", "code": "VIDEO_NOT_FOUND"}
        )
    
    # Delete file
    try:
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
    except Exception as e:
        logger.warning(f"Could not delete file: {e}")
    
    # Delete from database (cascade will handle analyses)
    await db.delete(video)
    await db.commit()
    
    logger.info(f"Video deleted: {video_id}")
    
    return {"message": "Video deleted successfully"}


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Stream a video file for playback."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = Path(video.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    # Determine media type from extension
    ext = file_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".m4v": "video/x-m4v",
    }
    media_type = media_types.get(ext, "video/mp4")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=video.original_filename,
    )

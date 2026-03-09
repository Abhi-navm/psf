"""
Video processing tasks.
"""

import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.config import settings

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def extract_audio(self, video_path: str, output_path: str) -> Dict[str, Any]:
    """
    Extract audio from video file.
    
    Args:
        video_path: Path to the video file
        output_path: Path for the output audio file
        
    Returns:
        Dict with audio file info
    """
    try:
        from moviepy.editor import VideoFileClip
        
        logger.info(f"Extracting audio from {video_path}")
        
        video = VideoFileClip(video_path)
        audio = video.audio
        
        if audio is None:
            raise ValueError("Video has no audio track")
        
        # Export as WAV for best quality analysis
        audio.write_audiofile(
            output_path,
            fps=16000,  # 16kHz for speech recognition
            nbytes=2,
            codec='pcm_s16le',
            verbose=False,
            logger=None,
        )
        
        duration = video.duration
        video.close()
        
        logger.info(f"Audio extracted successfully: {output_path}")
        
        return {
            "success": True,
            "audio_path": output_path,
            "duration": duration,
            "sample_rate": 16000,
        }
        
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def extract_video_metadata(self, video_path: str) -> Dict[str, Any]:
    """
    Extract metadata from video file.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dict with video metadata
    """
    try:
        from moviepy.editor import VideoFileClip
        
        logger.info(f"Extracting metadata from {video_path}")
        
        video = VideoFileClip(video_path)
        
        metadata = {
            "duration": video.duration,
            "fps": video.fps,
            "width": video.size[0],
            "height": video.size[1],
            "has_audio": video.audio is not None,
        }
        
        video.close()
        
        logger.info(f"Metadata extracted: {metadata}")
        
        return metadata
        
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True)
def extract_frames(
    self,
    video_path: str,
    output_dir: str,
    fps: float = 1.0,
) -> Dict[str, Any]:
    """
    Extract frames from video at specified FPS.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory for output frames
        fps: Frames per second to extract
        
    Returns:
        Dict with frame paths and metadata
    """
    try:
        import cv2
        
        logger.info(f"Extracting frames from {video_path} at {fps} FPS")
        
        os.makedirs(output_dir, exist_ok=True)
        
        video = cv2.VideoCapture(video_path)
        video_fps = video.get(cv2.CAP_PROP_FPS)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        
        # Calculate frame interval
        frame_interval = int(video_fps / fps)
        
        frames = []
        frame_idx = 0
        extracted_count = 0
        
        while True:
            ret, frame = video.read()
            if not ret:
                break
            
            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / video_fps
                frame_filename = f"frame_{extracted_count:06d}_{timestamp:.2f}s.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                
                cv2.imwrite(frame_path, frame)
                
                frames.append({
                    "path": frame_path,
                    "timestamp": timestamp,
                    "frame_number": extracted_count,
                })
                extracted_count += 1
            
            frame_idx += 1
        
        video.release()
        
        logger.info(f"Extracted {extracted_count} frames")
        
        return {
            "success": True,
            "frames": frames,
            "total_frames": extracted_count,
            "duration": duration,
        }
        
    except Exception as e:
        logger.error(f"Frame extraction failed: {e}")
        raise


@shared_task
def cleanup_old_files() -> Dict[str, Any]:
    """
    Clean up old temporary files and uploads.
    Runs periodically via Celery beat.
    """
    try:
        logger.info("Starting cleanup of old files")
        
        upload_dir = Path(settings.local_storage_path)
        temp_dir = upload_dir / "temp"
        
        deleted_count = 0
        deleted_size = 0
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        
        # Clean temp directory
        if temp_dir.exists():
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        deleted_size += size
        
        logger.info(f"Cleanup complete: {deleted_count} files, {deleted_size / 1024 / 1024:.2f} MB")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "deleted_size_mb": deleted_size / 1024 / 1024,
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"success": False, "error": str(e)}

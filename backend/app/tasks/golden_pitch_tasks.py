"""
Celery tasks for processing golden pitch deck videos.
"""

import os
import asyncio
import time
import logging as _logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.core.config import settings

logger = _logging.getLogger(__name__)
logger.setLevel(_logging.INFO)
if not any(isinstance(h, _logging.StreamHandler) for h in logger.handlers):
    logger.addHandler(_logging.StreamHandler())

# Celery decorator — only import if available
def _noop_task(bind=True, max_retries=2):
    def wrapper(func):
        func.delay = lambda *a, **kw: None
        return func
    return wrapper

try:
    from celery import shared_task
except ImportError:
    shared_task = _noop_task


def get_or_create_event_loop():
    """Get existing event loop or create a new one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def run_async(coro):
    """Run async function in sync context."""
    loop = get_or_create_event_loop()
    return loop.run_until_complete(coro)


@shared_task(bind=True, max_retries=2)
def process_golden_pitch_deck(
    self,
    golden_pitch_deck_id: str,
    video_id: str,
    video_path: str,
) -> Dict[str, Any]:
    """
    Process a golden pitch deck video to extract reference metrics.
    """
    # If RunPod is configured, delegate
    if settings.runpod_endpoint_id and settings.runpod_api_key:
        return _process_golden_via_runpod(golden_pitch_deck_id, video_id, video_path)

    return _process_golden_locally(golden_pitch_deck_id, video_id, video_path)


def _process_golden_via_runpod(
    golden_pitch_deck_id: str,
    video_id: str,
    video_path: str,
) -> Dict[str, Any]:
    """Send golden pitch to RunPod, get back analysis, extract reference data locally."""
    import base64
    import httpx
    from app.db.database import async_session_maker
    from app.db.models import GoldenPitchDeck
    from sqlalchemy import update as sql_update
    from app.analyzers.comparison import ComparisonAnalyzer

    async def update_status(is_processed: bool = False, error: str = None, **kwargs):
        async with async_session_maker() as session:
            values = {"is_processed": is_processed, "processing_error": error,
                       "updated_at": datetime.utcnow(), **kwargs}
            stmt = sql_update(GoldenPitchDeck).where(
                GoldenPitchDeck.id == golden_pitch_deck_id
            ).values(**values)
            await session.execute(stmt)
            await session.commit()

    try:
        logger.info(f"Processing golden pitch deck {golden_pitch_deck_id} via RunPod")
        base_url = f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}"
        headers = {
            "Authorization": f"Bearer {settings.runpod_api_key}",
            "Content-Type": "application/json",
        }

        # Upload video to temp file host (RunPod has 10MB request body limit)
        from app.tasks.analysis_tasks import _upload_to_temp_host
        video_url = _upload_to_temp_host(video_path)

        payload = {"input": {"video_url": video_url}}

        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{base_url}/run", headers=headers, json=payload)
            resp.raise_for_status()
            job = resp.json()

        job_id = job["id"]
        logger.info(f"RunPod golden pitch job: {job_id}")

        # Poll with retry logic for stale-worker failures
        MAX_ATTEMPTS = 3
        result = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                logger.info(f"Retrying RunPod golden pitch job (attempt {attempt}/{MAX_ATTEMPTS})...")
                with httpx.Client(timeout=60) as client:
                    resp = client.post(f"{base_url}/run", headers=headers, json=payload)
                    resp.raise_for_status()
                    job = resp.json()
                job_id = job["id"]
                logger.info(f"RunPod golden pitch retry job: {job_id}")

            max_wait = 600
            elapsed = 0
            result = None
            job_failed = False

            with httpx.Client(timeout=30) as client:
                while elapsed < max_wait:
                    time.sleep(5)
                    elapsed += 5
                    status_resp = client.get(f"{base_url}/status/{job_id}", headers=headers)
                    status_resp.raise_for_status()
                    data = status_resp.json()
                    status = data.get("status")

                    if status == "COMPLETED":
                        result = data.get("output", {})
                        break
                    elif status == "FAILED":
                        error = data.get("error", "RunPod job failed")
                        if attempt < MAX_ATTEMPTS:
                            logger.warning(f"RunPod golden pitch job {job_id} failed (attempt {attempt}): {error}")
                            job_failed = True
                            break
                        raise RuntimeError(error)

            if job_failed:
                continue

            if result is None:
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod golden pitch job {job_id} timed out (attempt {attempt}), retrying...")
                    continue
                raise TimeoutError(f"RunPod job timed out after {max_wait}s")

            if "error" in result:
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod golden pitch job {job_id} error (attempt {attempt}): {result['error']}")
                    continue
                raise RuntimeError(result["error"])

            # Verify transcription isn't empty (stale worker symptom)
            t_check = result.get("transcription", {})
            if isinstance(t_check, dict) and not t_check.get("text", ""):
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod golden pitch job {job_id} empty transcription (attempt {attempt}), retrying...")
                    continue
                logger.warning("All retry attempts returned empty transcription for golden pitch")

            break  # Success

        # Extract reference data from RunPod results
        transcription = result.get("transcription", {})
        transcript = transcription.get("text", "")

        # Use actual analysis results returned by RunPod handler
        voice_analysis = result.get("voice_analysis", {"skipped": True})
        pose_analysis = result.get("pose_analysis", {"skipped": True})
        facial_analysis = result.get("facial_analysis", {"skipped": True})
        content_analysis = result.get("content_analysis", {"skipped": True})

        comparison_analyzer = ComparisonAnalyzer()
        reference_data = comparison_analyzer.extract_reference_data(
            transcript=transcript,
            voice_analysis=voice_analysis,
            pose_analysis=pose_analysis,
            facial_analysis=facial_analysis,
            content_analysis=content_analysis,
        )

        run_async(update_status(
            is_processed=True,
            keywords=reference_data.get("keywords"),
            key_phrases=reference_data.get("key_phrases"),
            voice_metrics=reference_data.get("voice_metrics"),
            pose_metrics=reference_data.get("pose_metrics"),
            facial_metrics=reference_data.get("facial_metrics"),
            content_metrics=reference_data.get("content_metrics"),
            transcript=transcript,
        ))

        logger.info(f"Golden pitch deck {golden_pitch_deck_id} processed via RunPod")
        return {"success": True, "golden_pitch_deck_id": golden_pitch_deck_id}

    except Exception as e:
        logger.error(f"Golden pitch deck RunPod processing failed: {e}")
        run_async(update_status(is_processed=False, error=str(e)))
        raise


def _process_golden_locally(
    golden_pitch_deck_id: str,
    video_id: str,
    video_path: str,
) -> Dict[str, Any]:
    """
    Process a golden pitch deck video to extract reference metrics.
    
    This extracts:
    - Transcript and keywords
    - Voice metrics (pitch, pace, energy)
    - Pose/gesture patterns
    - Facial expression patterns
    - Content structure and key points
    """
    from app.db.database import async_session_maker
    from app.db.models import GoldenPitchDeck
    from sqlalchemy import update as sql_update
    
    async def update_status(is_processed: bool = False, error: str = None, **kwargs):
        """Update golden pitch deck status in database."""
        async with async_session_maker() as session:
            values = {
                "is_processed": is_processed,
                "processing_error": error,
                "updated_at": datetime.utcnow(),
                **kwargs,
            }
            stmt = sql_update(GoldenPitchDeck).where(
                GoldenPitchDeck.id == golden_pitch_deck_id
            ).values(**values)
            await session.execute(stmt)
            await session.commit()
    
    try:
        logger.info(f"Processing golden pitch deck {golden_pitch_deck_id}")
        
        # Create temp directories
        base_dir = Path(settings.local_storage_path)
        golden_dir = base_dir / "golden_pitch_decks" / golden_pitch_deck_id
        audio_dir = golden_dir / "audio"
        frames_dir = golden_dir / "frames"
        
        for dir_path in [golden_dir, audio_dir, frames_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        audio_path = str(audio_dir / "audio.wav")
        
        # Step 1: Extract audio
        logger.info("Extracting audio...")
        audio_result = _extract_audio_sync(video_path, audio_path)
        has_audio = audio_result.get("success", False)
        
        if not has_audio:
            logger.warning(f"Golden pitch deck has no audio: {audio_result.get('error')}")
        
        # Step 2: Extract frames
        logger.info("Extracting frames...")
        frames_result = _extract_frames_sync(video_path, str(frames_dir), fps=0.5)
        frames = frames_result.get("frames", [])
        
        # Step 3: Run transcription (if audio exists)
        transcript = ""
        segments = []
        if has_audio:
            logger.info("Running transcription...")
            transcription_result = _run_transcription_sync(audio_path)
            transcript = transcription_result.get("text", "")
            segments = transcription_result.get("segments", [])
        
        # Step 4: Run voice analysis (if audio exists)
        voice_result = {}
        if has_audio:
            logger.info("Running voice analysis...")
            voice_result = _run_voice_analysis_sync(audio_path)
            # Correct WPM using transcript word count (acoustic WPM is unreliable)
            if transcript and segments and not voice_result.get("skipped"):
                word_count = len(transcript.split())
                speak_start = segments[0].get("start", 0)
                speak_end = segments[-1].get("end", 0)
                speaking_duration = speak_end - speak_start
                if speaking_duration > 0 and word_count > 10:
                    actual_wpm = (word_count / speaking_duration) * 60
                    voice_result["speaking_rate_wpm"] = round(actual_wpm, 1)
                    logger.info(f"Golden pitch WPM corrected: acoustic -> {actual_wpm:.1f}")
        
        # Step 5: Run facial analysis
        logger.info("Running facial analysis...")
        facial_result = _run_facial_analysis_sync(frames)
        
        # Step 6: Run pose analysis
        logger.info("Running pose analysis...")
        pose_result = _run_pose_analysis_sync(frames)
        
        # Step 7: Run content analysis (if transcript exists)
        content_result = {}
        if transcript:
            logger.info("Running content analysis...")
            content_result = _run_content_analysis_sync(transcript, segments)
        
        # Step 8: Extract reference data for comparison
        logger.info("Extracting reference data...")
        from app.analyzers.comparison import ComparisonAnalyzer
        
        comparison_analyzer = ComparisonAnalyzer()
        reference_data = comparison_analyzer.extract_reference_data(
            transcript=transcript,
            voice_analysis=voice_result,
            pose_analysis=pose_result,
            facial_analysis=facial_result,
            content_analysis=content_result,
        )
        
        # Save reference data to database
        run_async(update_status(
            is_processed=True,
            keywords=reference_data.get("keywords"),
            key_phrases=reference_data.get("key_phrases"),
            voice_metrics=reference_data.get("voice_metrics"),
            pose_metrics=reference_data.get("pose_metrics"),
            facial_metrics=reference_data.get("facial_metrics"),
            content_metrics=reference_data.get("content_metrics"),
            transcript=transcript,
        ))
        
        logger.info(f"Golden pitch deck {golden_pitch_deck_id} processed successfully")
        
        return {
            "success": True,
            "golden_pitch_deck_id": golden_pitch_deck_id,
            "has_audio": has_audio,
            "transcript_length": len(transcript),
            "keywords_count": len(reference_data.get("keywords", {}).get("keywords", [])),
        }
        
    except Exception as e:
        logger.error(f"Golden pitch deck processing failed: {e}")
        run_async(update_status(is_processed=False, error=str(e)))
        raise


def _extract_audio_sync(video_path: str, output_path: str) -> Dict[str, Any]:
    """Extract audio from video file."""
    try:
        from moviepy.editor import VideoFileClip
        
        video = VideoFileClip(video_path)
        audio = video.audio
        
        if audio is None:
            return {"success": False, "error": "Video has no audio track"}
        
        audio.write_audiofile(
            output_path,
            fps=16000,
            nbytes=2,
            codec='pcm_s16le',
            verbose=False,
            logger=None,
        )
        
        duration = video.duration
        video.close()
        
        return {
            "success": True,
            "audio_path": output_path,
            "duration": duration,
        }
        
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        return {"success": False, "error": str(e)}


def _extract_frames_sync(video_path: str, output_dir: str, fps: float = 0.5) -> Dict[str, Any]:
    """Extract frames from video."""
    try:
        import cv2
        
        os.makedirs(output_dir, exist_ok=True)
        
        video = cv2.VideoCapture(video_path)
        video_fps = video.get(cv2.CAP_PROP_FPS)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0
        
        frame_interval = max(1, int(video_fps / fps))
        
        frames = []
        frame_idx = 0
        extracted_count = 0
        
        while True:
            ret, frame = video.read()
            if not ret:
                break
            
            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / video_fps if video_fps > 0 else 0
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
        
        return {
            "success": True,
            "frames": frames,
            "total_frames": extracted_count,
            "duration": duration,
        }
        
    except Exception as e:
        logger.error(f"Frame extraction failed: {e}")
        return {"success": False, "frames": [], "error": str(e)}


def _run_transcription_sync(audio_path: str) -> Dict[str, Any]:
    """Run transcription."""
    try:
        from app.analyzers.transcription import WhisperTranscriber
        
        transcriber = WhisperTranscriber()
        return transcriber.transcribe(audio_path)
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {"text": "", "segments": [], "error": str(e)}


def _run_voice_analysis_sync(audio_path: str) -> Dict[str, Any]:
    """Run voice analysis."""
    try:
        from app.analyzers.voice import VoiceAnalyzer
        
        analyzer = VoiceAnalyzer()
        return analyzer.analyze(audio_path)
        
    except Exception as e:
        logger.error(f"Voice analysis failed: {e}")
        return {"error": str(e)}


def _run_facial_analysis_sync(frames: list) -> Dict[str, Any]:
    """Run facial analysis."""
    try:
        from app.analyzers.facial import FacialExpressionAnalyzer
        
        analyzer = FacialExpressionAnalyzer()
        return analyzer.analyze_frames(frames)
        
    except Exception as e:
        logger.error(f"Facial analysis failed: {e}")
        return {"error": str(e)}


def _run_pose_analysis_sync(frames: list) -> Dict[str, Any]:
    """Run pose analysis."""
    try:
        from app.analyzers.pose import PoseAnalyzer
        
        analyzer = PoseAnalyzer()
        return analyzer.analyze_frames(frames)
        
    except Exception as e:
        logger.error(f"Pose analysis failed: {e}")
        return {"error": str(e)}


def _run_content_analysis_sync(transcript: str, segments: list) -> Dict[str, Any]:
    """Run content analysis."""
    try:
        from app.analyzers.content import ContentAnalyzer
        
        analyzer = ContentAnalyzer()
        return analyzer.analyze(transcript, segments)
        
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        return {"error": str(e)}

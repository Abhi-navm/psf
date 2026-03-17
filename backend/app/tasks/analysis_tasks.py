"""
Main analysis orchestration tasks.
"""

import os
import asyncio
import time
import logging as _logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.core.config import settings

# Use standard logging when running without Celery
logger = _logging.getLogger(__name__)
logger.setLevel(_logging.INFO)

# Log to file
os.makedirs("logs", exist_ok=True)
_file_handler = _logging.FileHandler("logs/celery_worker.log")
_file_handler.setFormatter(_logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_file_handler)

# Add stream handler for console output
if not any(isinstance(h, _logging.StreamHandler) for h in logger.handlers):
    logger.addHandler(_logging.StreamHandler())

# Celery decorator — only import if not in RunPod-only mode
def _noop_task(bind=True, max_retries=2):
    """No-op decorator when Celery is not available."""
    def wrapper(func):
        func.delay = lambda *a, **kw: None
        return func
    return wrapper

try:
    from celery import shared_task
except ImportError:
    shared_task = _noop_task


def _convert_numpy(obj):
    """Recursively convert numpy types to native Python types."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_numpy(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


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


def _upload_to_temp_host(file_path: str) -> str:
    """Upload a file to a temporary file host and return the download URL."""
    import httpx

    logger.info(f"Uploading {file_path} to temp file host...")
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    with httpx.Client(timeout=600, follow_redirects=True) as client:
        with open(file_path, "rb") as f:
            resp = client.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (os.path.basename(file_path), f, "video/mp4")},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise RuntimeError(f"tmpfiles.org upload failed: {data}")
        # Convert page URL to direct download URL
        page_url = data["data"]["url"]
        dl_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        logger.info(f"Uploaded {file_size_mb:.1f}MB -> {dl_url}")
        return dl_url


def _run_via_runpod(
    analysis_id: str,
    video_id: str,
    video_path: str,
    is_audio_only: bool = False,
    golden_pitch_deck_id: Optional[str] = None,
    skip_comparison: bool = False,
) -> Dict[str, Any]:
    """
    Proxy the analysis to the RunPod serverless endpoint.
    Base64-encodes the video, sends to RunPod, polls for results,
    and saves them into the local DB so the frontend can display them.
    """
    import base64
    import httpx
    from app.db.database import async_session_maker
    from app.db.models import (
        Analysis, AnalysisStatus, Transcription, VoiceAnalysis,
        FacialAnalysis, PoseAnalysis, ContentAnalysis, AnalysisReport,
    )

    base_url = f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}"
    headers = {
        "Authorization": f"Bearer {settings.runpod_api_key}",
        "Content-Type": "application/json",
    }

    async def update_status(status: AnalysisStatus, progress: int = 0):
        async with async_session_maker() as session:
            from sqlalchemy import update
            stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                status=status, progress=progress, updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
            await session.commit()

    async def mark_failed(error_msg: str):
        async with async_session_maker() as session:
            from sqlalchemy import update
            stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                status=AnalysisStatus.FAILED,
                error_message=error_msg,
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
            await session.commit()

    try:
        run_async(update_status(AnalysisStatus.PROCESSING, 5))

        # Upload video to temp file host (RunPod has 10MB request body limit)
        video_url = _upload_to_temp_host(video_path)

        run_async(update_status(AnalysisStatus.PROCESSING, 10))

        # Submit to RunPod (async /run endpoint)
        payload = {
            "input": {
                "video_url": video_url,
                "is_audio_only": is_audio_only,
            }
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{base_url}/run", headers=headers, json=payload)
            resp.raise_for_status()
            job = resp.json()

        job_id = job["id"]
        logger.info(f"RunPod job submitted: {job_id}")
        run_async(update_status(AnalysisStatus.TRANSCRIBING, 25))

        # Submit + poll with retry logic for stale-worker failures
        MAX_ATTEMPTS = 3
        result = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                logger.info(f"Retrying RunPod job (attempt {attempt}/{MAX_ATTEMPTS})...")
                # Re-submit a new job
                with httpx.Client(timeout=60) as client:
                    resp = client.post(f"{base_url}/run", headers=headers, json=payload)
                    resp.raise_for_status()
                    job = resp.json()
                job_id = job["id"]
                logger.info(f"RunPod retry job submitted: {job_id}")

            poll_interval = 5
            max_wait = 600  # 10 minutes
            elapsed = 0
            result = None
            job_failed = False

            with httpx.Client(timeout=30) as client:
                while elapsed < max_wait:
                    time.sleep(poll_interval)
                    elapsed += poll_interval

                    status_resp = client.get(
                        f"{base_url}/status/{job_id}", headers=headers
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    job_status = status_data.get("status")

                    if job_status == "COMPLETED":
                        result = status_data.get("output", {})
                        break
                    elif job_status == "FAILED":
                        error = status_data.get("error", "RunPod job failed")
                        if attempt < MAX_ATTEMPTS:
                            logger.warning(f"RunPod job {job_id} failed (attempt {attempt}): {error}")
                            job_failed = True
                            break
                        raise RuntimeError(error)
                    elif job_status == "IN_PROGRESS":
                        run_async(update_status(AnalysisStatus.ANALYZING_CONTENT, 60))
                    # else still IN_QUEUE

                    if elapsed % 30 == 0:
                        logger.info(f"RunPod job {job_id}: {job_status} ({elapsed}s)")

            if job_failed:
                continue

            if result is None:
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod job {job_id} timed out (attempt {attempt}), retrying...")
                    continue
                raise TimeoutError(f"RunPod job {job_id} timed out after {max_wait}s")

            if "error" in result:
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod job {job_id} returned error (attempt {attempt}): {result['error']}")
                    continue
                raise RuntimeError(result["error"])

            # Check if transcription is empty for a video with audio (stale worker)
            transcription_check = result.get("transcription", {})
            transcript_text_check = ""
            if isinstance(transcription_check, dict):
                transcript_text_check = transcription_check.get("text", "")
            if not transcript_text_check and not is_audio_only:
                if attempt < MAX_ATTEMPTS:
                    logger.warning(f"RunPod job {job_id} returned empty transcription (attempt {attempt}), retrying...")
                    continue
                logger.warning("All retry attempts returned empty transcription")

            break  # Success

        logger.info(f"RunPod job {job_id} completed. Saving results to DB...")
        run_async(update_status(AnalysisStatus.GENERATING_REPORT, 90))

        # Extract results from RunPod response
        transcription = result.get("transcription", {})
        voice = result.get("voice_analysis", {})
        facial = result.get("facial_analysis", {})
        pose = result.get("pose_analysis", {})
        content = result.get("content_analysis", {})
        timings = result.get("timings", {})

        # If facial was skipped (no person detected), also skip pose
        if facial.get("skipped") and not pose.get("skipped"):
            pose = {
                "skipped": True,
                "reason": facial.get("reason", "No face/person detected in video"),
                "overall_score": 0,
                "posture_score": 0, "gesture_score": 0, "movement_score": 0,
                "avg_shoulder_alignment": 0, "gesture_frequency": 0, "fidgeting_frequency": 0,
                "issues": [], "pose_timeline": [],
            }

        # Run comparison against golden pitch deck locally (lightweight, no GPU)
        comparison_result = None
        actual_golden_id = None
        if not skip_comparison and golden_pitch_deck_id:
            golden_reference = run_async(_get_golden_pitch_deck_reference(golden_pitch_deck_id))
        else:
            golden_reference = None
        if golden_reference and golden_reference.get("is_processed"):
            actual_golden_id = golden_reference.get("id")
            logger.info(f"Comparing against golden pitch deck: {actual_golden_id}")
            transcript_text = transcription.get("text", "")
            comparison_result = _run_comparison_sync(
                golden_reference=golden_reference,
                transcript=transcript_text,
                voice_result=voice,
                pose_result=pose,
                facial_result=facial,
                content_result=content,
            )
            logger.info(f"Comparison completed: {comparison_result.get('summary', {}).get('overall_comparison_score', 'N/A')}")
        else:
            logger.info("No processed golden pitch deck available for comparison")

        # Convert numpy types before saving
        if comparison_result:
            comparison_result = _convert_numpy(comparison_result)

        # Generate report locally with comparison data
        from app.analyzers.report_generator import ReportGenerator
        report_gen = ReportGenerator()
        report = report_gen.generate({
            "voice": voice,
            "facial": facial,
            "pose": pose,
            "content": content,
            "has_audio": not is_audio_only,
            "comparison": comparison_result,
            "golden_pitch_deck_id": actual_golden_id,
        })
        report = _convert_numpy(report)

        # Save each sub-analysis and the report to DB.
        async def save_results():
            async with async_session_maker() as session:
                # Transcription
                session.add(Transcription(
                    analysis_id=analysis_id,
                    full_text=transcription.get("text", ""),
                    language=transcription.get("language", "en"),
                    confidence=0.0,
                    segments=transcription.get("segments"),
                ))

                # Voice analysis - use detailed per-metric scores
                session.add(VoiceAnalysis(
                    analysis_id=analysis_id,
                    overall_score=voice.get("overall_score", report.get("voice_score", 50.0)),
                    energy_score=voice.get("energy_score", 50.0),
                    clarity_score=voice.get("clarity_score", 50.0),
                    pace_score=voice.get("pace_score", 50.0),
                    confidence_score=voice.get("confidence_score", 50.0),
                    tone_score=voice.get("tone_score", 50.0),
                    avg_pitch=voice.get("avg_pitch"),
                    pitch_variance=voice.get("pitch_variance"),
                    speaking_rate_wpm=voice.get("speaking_rate_wpm"),
                    pause_frequency=voice.get("pause_frequency"),
                    emotion_timeline=voice.get("emotion_timeline"),
                    issues=voice.get("issues"),
                ))

                # Facial analysis
                session.add(FacialAnalysis(
                    analysis_id=analysis_id,
                    overall_score=facial.get("overall_score", report.get("facial_score", 50.0)),
                    positivity_score=facial.get("positivity_score", 50.0),
                    engagement_score=facial.get("engagement_score", 50.0),
                    confidence_score=facial.get("confidence_score", 50.0),
                    emotion_distribution=facial.get("emotion_distribution"),
                    emotion_timeline=facial.get("emotion_timeline"),
                    eye_contact_percentage=facial.get("eye_contact_percentage"),
                    issues=facial.get("issues"),
                ))

                # Pose analysis
                session.add(PoseAnalysis(
                    analysis_id=analysis_id,
                    overall_score=pose.get("overall_score", report.get("pose_score", 50.0)),
                    posture_score=pose.get("posture_score", 50.0),
                    gesture_score=pose.get("gesture_score", 50.0),
                    movement_score=pose.get("movement_score", 50.0),
                    avg_shoulder_alignment=pose.get("avg_shoulder_alignment"),
                    fidgeting_frequency=pose.get("fidgeting_frequency"),
                    gesture_frequency=pose.get("gesture_frequency"),
                    pose_timeline=pose.get("pose_timeline"),
                    issues=pose.get("issues"),
                ))

                # Content analysis
                session.add(ContentAnalysis(
                    analysis_id=analysis_id,
                    overall_score=content.get("overall_score", report.get("content_score", 50.0)),
                    clarity_score=content.get("clarity_score", 50.0),
                    persuasion_score=content.get("persuasion_score", 50.0),
                    structure_score=content.get("structure_score", 50.0),
                    filler_words=content.get("filler_words"),
                    filler_word_count=content.get("filler_word_count", 0),
                    weak_phrases=content.get("weak_phrases"),
                    negative_language=content.get("negative_language"),
                    key_points=content.get("key_points"),
                    llm_feedback=content.get("llm_feedback"),
                ))

                # Report (with comparison data)
                session.add(AnalysisReport(
                    analysis_id=analysis_id,
                    overall_score=report.get("overall_score", 50.0),
                    voice_score=report.get("voice_score", 50.0),
                    facial_score=report.get("facial_score", 50.0),
                    pose_score=report.get("pose_score", 50.0),
                    content_score=report.get("content_score", 50.0),
                    executive_summary=report.get("executive_summary", "Analysis completed."),
                    strengths=report.get("strengths"),
                    improvements=report.get("improvements"),
                    timestamped_issues=report.get("timestamped_issues"),
                    recommendations=report.get("recommendations"),
                    golden_pitch_deck_id=report.get("golden_pitch_deck_id"),
                    comparison_overall_score=report.get("comparison_overall_score"),
                    content_similarity_score=report.get("content_similarity_score"),
                    keyword_coverage_score=report.get("keyword_coverage_score"),
                    voice_similarity_score=report.get("voice_similarity_score"),
                    pose_similarity_score=report.get("pose_similarity_score"),
                    facial_similarity_score=report.get("facial_similarity_score"),
                    keyword_comparison=report.get("keyword_comparison"),
                    content_comparison=report.get("content_comparison"),
                    pose_comparison=report.get("pose_comparison"),
                    voice_comparison=report.get("voice_comparison"),
                    facial_comparison=report.get("facial_comparison"),
                ))

                await session.commit()

        run_async(save_results())

        # Mark completed
        async def mark_completed():
            async with async_session_maker() as session:
                from sqlalchemy import update
                stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                    status=AnalysisStatus.COMPLETED,
                    progress=100,
                    completed_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                await session.execute(stmt)
                await session.commit()

        run_async(mark_completed())
        logger.info(f"RunPod analysis {analysis_id} saved. Timings: {timings}")

        return {"success": True, "analysis_id": analysis_id, "report": report}

    except Exception as e:
        logger.error(f"RunPod analysis {analysis_id} failed: {e}")
        run_async(mark_failed(str(e)))
        raise


@shared_task(bind=True, max_retries=2)
def run_full_analysis(
    self,
    analysis_id: str,
    video_id: str,
    video_path: str,
    golden_pitch_deck_id: Optional[str] = None,
    skip_comparison: bool = False,
    is_audio_only: bool = False,
) -> Dict[str, Any]:
    """
    Run the complete video/audio analysis pipeline with comparison to golden pitch deck.
    
    Args:
        analysis_id: The analysis record ID
        video_id: The video ID being analyzed
        video_path: Path to the video/audio file
        golden_pitch_deck_id: Optional specific golden pitch deck to compare against
        skip_comparison: If True, skip comparison even if golden pitch deck exists
        is_audio_only: If True, skip visual analysis (facial, pose)
        
    All operations are run directly (not as subtasks) to avoid Celery restrictions.
    """
    # If RunPod is configured, delegate to serverless endpoint
    if settings.runpod_endpoint_id and settings.runpod_api_key:
        logger.info(f"RunPod proxy mode: delegating analysis {analysis_id} to endpoint {settings.runpod_endpoint_id}")
        return _run_via_runpod(analysis_id, video_id, video_path, is_audio_only,
                              golden_pitch_deck_id, skip_comparison)

    from app.db.database import async_session_maker
    from app.db.models import Analysis, AnalysisStatus
    
    async def update_status(status: AnalysisStatus, progress: int = 0):
        """Update analysis status in database."""
        async with async_session_maker() as session:
            from sqlalchemy import update
            stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                status=status,
                progress=progress,
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
            await session.commit()
    
    async def mark_completed():
        async with async_session_maker() as session:
            from sqlalchemy import update
            stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                status=AnalysisStatus.COMPLETED,
                progress=100,
                completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
            await session.commit()
    
    async def mark_failed(error_msg: str):
        async with async_session_maker() as session:
            from sqlalchemy import update
            stmt = update(Analysis).where(Analysis.id == analysis_id).values(
                status=AnalysisStatus.FAILED,
                error_message=error_msg,
                updated_at=datetime.utcnow(),
            )
            await session.execute(stmt)
            await session.commit()
    
    try:
        pipeline_start = time.time()
        logger.info(f"Starting full analysis for video {video_id}")
        
        # Create temp directories
        base_dir = Path(settings.local_storage_path)
        analysis_dir = base_dir / "analyses" / analysis_id
        audio_dir = analysis_dir / "audio"
        frames_dir = analysis_dir / "frames"
        
        for dir_path in [analysis_dir, audio_dir, frames_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        audio_path = str(audio_dir / "audio.wav")
        
        # Update status to processing
        run_async(update_status(AnalysisStatus.PROCESSING, 5))
        
        # ============================================================
        # PHASE 1: Extract audio + frames in parallel
        # ============================================================
        phase1_start = time.time()
        run_async(update_status(AnalysisStatus.EXTRACTING_AUDIO, 10))
        
        has_audio = False
        person_frames = []
        
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="extract") as executor:
            # Submit audio extraction
            def _extract_audio_task():
                if is_audio_only:
                    logger.info("Converting audio file to WAV format...")
                    try:
                        from moviepy.editor import AudioFileClip
                        audio_clip = AudioFileClip(video_path)
                        audio_clip.write_audiofile(
                            audio_path, fps=16000, nbytes=2,
                            codec='pcm_s16le', verbose=False, logger=None,
                        )
                        duration = audio_clip.duration
                        audio_clip.close()
                        return {"success": True, "duration": duration}
                    except Exception as e:
                        logger.error(f"Audio conversion failed: {e}")
                        return {"success": False, "error": str(e)}
                else:
                    logger.info("Extracting audio...")
                    return _extract_audio_sync(video_path, audio_path)
            
            # Track whether a face/person was detected in the video
            face_detected_in_video = True  # assume True; set False if detection says no

            # Submit frame extraction
            def _extract_frames_task():
                nonlocal face_detected_in_video
                if is_audio_only:
                    logger.info("Skipping frame extraction (audio-only file)")
                    face_detected_in_video = False
                    return []
                logger.info("Extracting frames...")
                frames_result = _extract_frames_sync(video_path, str(frames_dir), fps=settings.frame_extraction_fps)
                raw_frames = frames_result.get("frames", [])
                
                # Detect face region
                logger.info("Detecting face region...")
                face_region_info = _detect_face_region_sync(raw_frames)
                face_detected_in_video = face_region_info.get("has_face", False)
                
                if not face_detected_in_video:
                    logger.warning("No face/person detected in video — facial and pose analysis will be skipped")
                
                if face_region_info.get("is_overlay") and face_region_info.get("crop_region"):
                    logger.info("Webcam overlay detected — creating cropped frames")
                    cropped_dir = str(analysis_dir / "cropped_frames")
                    return _create_cropped_frames_sync(
                        raw_frames, face_region_info["crop_region"], cropped_dir
                    )
                return raw_frames
            
            audio_future = executor.submit(_extract_audio_task)
            frames_future = executor.submit(_extract_frames_task)
            
            audio_result = audio_future.result()
            has_audio = audio_result.get("success", False)
            person_frames = frames_future.result()
        
        if not has_audio:
            logger.warning(f"No audio: {audio_result.get('error', 'Unknown')}. Skipping audio-based analyses.")
        
        logger.info(f"Phase 1 complete in {time.time()-phase1_start:.1f}s: has_audio={has_audio}, frames={len(person_frames)}")
        
        # ============================================================
        # PHASE 2: Run all independent analyses in parallel
        # Transcription + Voice + Facial + Pose run simultaneously
        # ============================================================
        phase2_start = time.time()
        run_async(update_status(AnalysisStatus.TRANSCRIBING, 25))
        logger.info("Starting parallel analysis phase...")
        
        transcription_result = {"text": "", "segments": [], "skipped": True, "reason": "No audio track"}
        voice_result = {"skipped": True, "reason": "No audio track"}
        facial_result = {"skipped": True, "reason": "Audio-only file"}
        pose_result = {"skipped": True, "reason": "Audio-only file"}
        
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="analyze") as executor:
            futures = {}
            
            # Submit transcription
            if has_audio:
                futures["transcription"] = executor.submit(
                    _run_transcription_sync, analysis_id, audio_path
                )
            
            # Submit voice analysis
            if has_audio:
                futures["voice"] = executor.submit(
                    _run_voice_analysis_sync, analysis_id, audio_path
                )
            
            # Sub-sample frames for facial/pose (cap at 30 for speed)
            MAX_ANALYSIS_FRAMES = 30
            if len(person_frames) > MAX_ANALYSIS_FRAMES:
                step = len(person_frames) / MAX_ANALYSIS_FRAMES
                sampled_frames = [person_frames[int(i * step)] for i in range(MAX_ANALYSIS_FRAMES)]
                logger.info(f"Sub-sampled {len(person_frames)} frames to {len(sampled_frames)} for analysis")
            else:
                sampled_frames = person_frames
            
            # Submit facial analysis (only if a face/person was detected)
            if not is_audio_only and sampled_frames and face_detected_in_video:
                futures["facial"] = executor.submit(
                    _run_facial_analysis_sync, analysis_id, sampled_frames
                )
            elif not is_audio_only and not face_detected_in_video:
                facial_result = {"skipped": True, "reason": "No face/person detected in video", "overall_score": 0}
            
            # Submit pose analysis (only if a face/person was detected)
            if not is_audio_only and sampled_frames and face_detected_in_video:
                futures["pose"] = executor.submit(
                    _run_pose_analysis_sync, analysis_id, sampled_frames
                )
            elif not is_audio_only and not face_detected_in_video:
                pose_result = {"skipped": True, "reason": "No face/person detected in video", "overall_score": 0}
            
            # Collect results as they complete
            for name, future in futures.items():
                try:
                    result = future.result()
                    elapsed = time.time() - phase2_start
                    duration = result.pop("_duration", None)
                    dur_str = f" (task={duration:.1f}s)" if duration else ""
                    if name == "transcription":
                        transcription_result = result
                        logger.info(f"Transcription completed at {elapsed:.1f}s{dur_str}")
                    elif name == "voice":
                        voice_result = result
                        logger.info(f"Voice analysis completed at {elapsed:.1f}s{dur_str}")
                    elif name == "facial":
                        facial_result = result
                        logger.info(f"Facial analysis completed at {elapsed:.1f}s{dur_str}")
                    elif name == "pose":
                        pose_result = result
                        logger.info(f"Pose analysis completed at {elapsed:.1f}s{dur_str}")
                except Exception as e:
                    logger.error(f"{name} analysis failed: {e}")
        
        run_async(update_status(AnalysisStatus.ANALYZING_CONTENT, 75))
        logger.info(f"Phase 2 complete in {time.time()-phase2_start:.1f}s. All parallel analyses finished.")
        
        # ============================================================
        # PHASE 3: Content analysis (needs transcript text)
        # ============================================================
        phase3_start = time.time()
        transcript_text = transcription_result.get("text", "")
        if transcript_text and not transcription_result.get("skipped"):
            logger.info("Running content analysis...")
            content_result = _run_content_analysis_sync(
                analysis_id,
                transcript_text,
                transcription_result.get("segments", []),
            )
        else:
            logger.info("Skipping content analysis (no transcript available)")
            content_result = {"skipped": True, "reason": "No transcript available"}
        
        logger.info(f"Phase 3 (content) complete in {time.time()-phase3_start:.1f}s")
        
        # ============================================================
        # PHASE 4: Comparison + Report (needs all results)
        # ============================================================
        phase4_start = time.time()
        comparison_result = None
        golden_reference = None
        actual_golden_id = None
        
        if not skip_comparison and golden_pitch_deck_id:
            golden_reference = run_async(_get_golden_pitch_deck_reference(golden_pitch_deck_id))
            
            if golden_reference and golden_reference.get("is_processed"):
                actual_golden_id = golden_reference.get("id")
                logger.info(f"Comparing against golden pitch deck: {actual_golden_id}")
                
                comparison_result = _run_comparison_sync(
                    golden_reference=golden_reference,
                    transcript=transcript_text,
                    voice_result=voice_result,
                    pose_result=pose_result,
                    facial_result=facial_result,
                    content_result=content_result,
                )
            else:
                logger.info("No processed golden pitch deck available for comparison")
        
        # Generate final report
        run_async(update_status(AnalysisStatus.GENERATING_REPORT, 95))
        logger.info("Generating report...")
        report_result = _generate_report_sync(
            analysis_id,
            {
                "voice": voice_result,
                "facial": facial_result,
                "pose": pose_result,
                "content": content_result,
                "has_audio": has_audio,
                "comparison": comparison_result,
                "golden_pitch_deck_id": actual_golden_id,
            }
        )
        
        # Mark as completed
        run_async(mark_completed())
        
        logger.info(f"Phase 4 (comparison+report) complete in {time.time()-phase4_start:.1f}s")
        logger.info(f"Analysis {analysis_id} completed in {time.time()-pipeline_start:.1f}s total")
        
        # Step 10: Send webhook notification if configured
        _send_webhook_notification(
            analysis_id=analysis_id,
            status="completed",
            overall_score=report_result.get("overall_score"),
        )
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "report": report_result,
        }
        
    except Exception as e:
        logger.error(f"Analysis {analysis_id} failed: {e}")
        run_async(mark_failed(str(e)))
        # Send webhook for failure too
        _send_webhook_notification(
            analysis_id=analysis_id,
            status="failed",
            error=str(e),
        )
        raise


def _send_webhook_notification(
    analysis_id: str,
    status: str,
    overall_score: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    """Send webhook notification when analysis completes or fails."""
    if not settings.webhook_enabled or not settings.webhook_url:
        return
    
    try:
        import httpx
        
        payload = {
            "event": "analysis_complete" if status == "completed" else "analysis_failed",
            "analysis_id": analysis_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if overall_score is not None:
            payload["overall_score"] = overall_score
        if error:
            payload["error"] = error
        
        with httpx.Client(timeout=settings.webhook_timeout) as client:
            response = client.post(
                settings.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            logger.info(f"Webhook sent to {settings.webhook_url}: {response.status_code}")
            
    except Exception as e:
        logger.warning(f"Failed to send webhook notification: {e}")


def _extract_audio_sync(video_path: str, output_path: str) -> Dict[str, Any]:
    """Extract audio from video file (sync version)."""
    try:
        from moviepy.editor import VideoFileClip
        
        logger.info(f"Extracting audio from {video_path}")
        
        video = VideoFileClip(video_path)
        audio = video.audio
        
        if audio is None:
            return {"success": False, "error": "Video has no audio track"}
        
        # Export as WAV for best quality analysis
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
            "sample_rate": 16000,
        }
        
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        return {"success": False, "error": str(e)}


def _extract_frames_sync(video_path: str, output_dir: str, fps: float = 1.0) -> Dict[str, Any]:
    """Extract frames from video (sync version)."""
    try:
        import cv2
        
        logger.info(f"Extracting frames from {video_path} at {fps} FPS")
        
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
        
        logger.info(f"Extracted {extracted_count} frames")
        
        return {
            "success": True,
            "frames": frames,
            "total_frames": extracted_count,
            "duration": duration,
        }
        
    except Exception as e:
        logger.error(f"Frame extraction failed: {e}")
        return {"success": False, "frames": [], "error": str(e)}


def _run_transcription_sync(analysis_id: str, audio_path: str) -> Dict[str, Any]:
    """Run transcription (sync version)."""
    try:
        from app.analyzers.transcription import WhisperTranscriber
        
        t0 = time.time()
        transcriber = WhisperTranscriber()
        result = transcriber.transcribe(audio_path)
        duration = time.time() - t0
        device = getattr(transcriber, 'device', 'unknown')
        logger.info(f"Transcription internal: {duration:.1f}s on device={device}")
        result["_duration"] = duration
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import Transcription
        
        async def save_transcription():
            async with async_session_maker() as session:
                transcription = Transcription(
                    analysis_id=analysis_id,
                    full_text=result.get("text", ""),
                    language=result.get("language", "en"),
                    confidence=result.get("confidence", 0.0),
                    word_timestamps=result.get("word_timestamps"),
                    segments=result.get("segments"),
                )
                session.add(transcription)
                await session.commit()
        
        run_async(save_transcription())
        
        return result
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {"text": "", "language": "en", "confidence": 0.0, "error": str(e)}


def _run_voice_analysis_sync(analysis_id: str, audio_path: str) -> Dict[str, Any]:
    """Run voice analysis (sync version)."""
    try:
        from app.analyzers.voice import VoiceAnalyzer
        
        t0 = time.time()
        analyzer = VoiceAnalyzer()
        result = analyzer.analyze(audio_path)
        result["_duration"] = time.time() - t0
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import VoiceAnalysis
        
        async def save_voice_analysis():
            async with async_session_maker() as session:
                voice_analysis = VoiceAnalysis(
                    analysis_id=analysis_id,
                    overall_score=result.get("overall_score", 50.0),
                    energy_score=result.get("energy_score", 50.0),
                    clarity_score=result.get("clarity_score", 50.0),
                    pace_score=result.get("pace_score", 50.0),
                    confidence_score=result.get("confidence_score", 50.0),
                    tone_score=result.get("tone_score", 50.0),
                    avg_pitch=result.get("avg_pitch"),
                    pitch_variance=result.get("pitch_variance"),
                    speaking_rate_wpm=result.get("speaking_rate_wpm"),
                    pause_frequency=result.get("pause_frequency"),
                    emotion_timeline=result.get("emotion_timeline"),
                    issues=result.get("issues"),
                )
                session.add(voice_analysis)
                await session.commit()
        
        run_async(save_voice_analysis())
        
        return result
        
    except Exception as e:
        logger.error(f"Voice analysis failed: {e}")
        return {
            "overall_score": 50.0,
            "energy_score": 50.0,
            "clarity_score": 50.0,
            "pace_score": 50.0,
            "confidence_score": 50.0,
            "tone_score": 50.0,
            "error": str(e)
        }


def _run_facial_analysis_sync(analysis_id: str, frames: list) -> Dict[str, Any]:
    """Run facial analysis (sync version)."""
    try:
        from app.analyzers.facial import FacialExpressionAnalyzer
        
        t0 = time.time()
        analyzer = FacialExpressionAnalyzer()
        result = analyzer.analyze_frames(frames)
        result["_duration"] = time.time() - t0
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import FacialAnalysis
        
        async def save_facial_analysis():
            async with async_session_maker() as session:
                facial_analysis = FacialAnalysis(
                    analysis_id=analysis_id,
                    overall_score=result.get("overall_score", 50.0),
                    positivity_score=result.get("positivity_score", 50.0),
                    engagement_score=result.get("engagement_score", 50.0),
                    confidence_score=result.get("confidence_score", 50.0),
                    emotion_distribution=result.get("emotion_distribution"),
                    emotion_timeline=result.get("emotion_timeline"),
                    eye_contact_percentage=result.get("eye_contact_percentage"),
                    issues=result.get("issues"),
                )
                session.add(facial_analysis)
                await session.commit()
        
        run_async(save_facial_analysis())
        
        return result
        
    except Exception as e:
        logger.error(f"Facial analysis failed: {e}")
        return {
            "overall_score": 50.0,
            "positivity_score": 50.0,
            "engagement_score": 50.0,
            "confidence_score": 50.0,
            "error": str(e)
        }


def _run_pose_analysis_sync(analysis_id: str, frames: list) -> Dict[str, Any]:
    """Run pose analysis (sync version)."""
    try:
        from app.analyzers.pose import PoseAnalyzer
        
        t0 = time.time()
        analyzer = PoseAnalyzer()
        result = analyzer.analyze_frames(frames)
        result["_duration"] = time.time() - t0
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import PoseAnalysis
        
        async def save_pose_analysis():
            async with async_session_maker() as session:
                pose_analysis = PoseAnalysis(
                    analysis_id=analysis_id,
                    overall_score=result.get("overall_score", 50.0),
                    posture_score=result.get("posture_score", 50.0),
                    gesture_score=result.get("gesture_score", 50.0),
                    movement_score=result.get("movement_score", 50.0),
                    avg_shoulder_alignment=result.get("avg_shoulder_alignment"),
                    fidgeting_frequency=result.get("fidgeting_frequency"),
                    gesture_frequency=result.get("gesture_frequency"),
                    pose_timeline=result.get("pose_timeline"),
                    issues=result.get("issues"),
                )
                session.add(pose_analysis)
                await session.commit()
        
        run_async(save_pose_analysis())
        
        return result
        
    except Exception as e:
        logger.error(f"Pose analysis failed: {e}")
        return {
            "overall_score": 50.0,
            "posture_score": 50.0,
            "gesture_score": 50.0,
            "movement_score": 50.0,
            "error": str(e)
        }


def _run_content_analysis_sync(analysis_id: str, transcript: str, segments: list) -> Dict[str, Any]:
    """Run content analysis (sync version)."""
    try:
        from app.analyzers.content import ContentAnalyzer
        
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(transcript, segments)
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import ContentAnalysis
        
        async def save_content_analysis():
            async with async_session_maker() as session:
                content_analysis = ContentAnalysis(
                    analysis_id=analysis_id,
                    overall_score=result.get("overall_score", 50.0),
                    clarity_score=result.get("clarity_score", 50.0),
                    persuasion_score=result.get("persuasion_score", 50.0),
                    structure_score=result.get("structure_score", 50.0),
                    filler_words=result.get("filler_words"),
                    filler_word_count=result.get("filler_word_count", 0),
                    weak_phrases=result.get("weak_phrases"),
                    negative_language=result.get("negative_language"),
                    key_points=result.get("key_points"),
                    llm_feedback=result.get("llm_feedback"),
                )
                session.add(content_analysis)
                await session.commit()
        
        run_async(save_content_analysis())
        
        return result
        
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        return {
            "overall_score": 0.0,
            "clarity_score": 0.0,
            "persuasion_score": 0.0,
            "structure_score": 0.0,
            "skipped": True,
            "reason": f"Content analysis failed: {str(e)}",
            "error": str(e)
        }


def _generate_report_sync(analysis_id: str, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate analysis report (sync version)."""
    try:
        from app.analyzers.report_generator import ReportGenerator
        
        generator = ReportGenerator()
        report = generator.generate(analysis_results)
        
        # Save to database
        from app.db.database import async_session_maker
        from app.db.models import AnalysisReport
        
        async def save_report():
            async with async_session_maker() as session:
                analysis_report = AnalysisReport(
                    analysis_id=analysis_id,
                    overall_score=report.get("overall_score", 50.0),
                    voice_score=report.get("voice_score", 50.0),
                    facial_score=report.get("facial_score", 50.0),
                    pose_score=report.get("pose_score", 50.0),
                    content_score=report.get("content_score", 50.0),
                    executive_summary=report.get("executive_summary", "Analysis completed."),
                    strengths=report.get("strengths"),
                    improvements=report.get("improvements"),
                    timestamped_issues=report.get("timestamped_issues"),
                    recommendations=report.get("recommendations"),
                    # Comparison fields
                    golden_pitch_deck_id=report.get("golden_pitch_deck_id"),
                    comparison_overall_score=report.get("comparison_overall_score"),
                    content_similarity_score=report.get("content_similarity_score"),
                    keyword_coverage_score=report.get("keyword_coverage_score"),
                    voice_similarity_score=report.get("voice_similarity_score"),
                    pose_similarity_score=report.get("pose_similarity_score"),
                    facial_similarity_score=report.get("facial_similarity_score"),
                    keyword_comparison=report.get("keyword_comparison"),
                    content_comparison=report.get("content_comparison"),
                    pose_comparison=report.get("pose_comparison"),
                    voice_comparison=report.get("voice_comparison"),
                    facial_comparison=report.get("facial_comparison"),
                )
                session.add(analysis_report)
                await session.commit()
        
        run_async(save_report())
        
        return report
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {
            "overall_score": 50.0,
            "voice_score": 50.0,
            "facial_score": 50.0,
            "pose_score": 50.0,
            "content_score": 50.0,
            "executive_summary": f"Analysis completed with errors: {str(e)}",
            "error": str(e)
        }


# Keep these as separate tasks for potential future use
@shared_task(bind=True, max_retries=2)
def run_transcription(self, analysis_id: str, audio_path: str) -> Dict[str, Any]:
    """Standalone transcription task."""
    return _run_transcription_sync(analysis_id, audio_path)


@shared_task(bind=True, max_retries=2)
def run_voice_analysis(self, analysis_id: str, audio_path: str) -> Dict[str, Any]:
    """Standalone voice analysis task."""
    return _run_voice_analysis_sync(analysis_id, audio_path)


@shared_task(bind=True, max_retries=2)
def run_facial_analysis(self, analysis_id: str, frames: list) -> Dict[str, Any]:
    """Standalone facial analysis task."""
    return _run_facial_analysis_sync(analysis_id, frames)


@shared_task(bind=True, max_retries=2)
def run_pose_analysis(self, analysis_id: str, frames: list) -> Dict[str, Any]:
    """Standalone pose analysis task."""
    return _run_pose_analysis_sync(analysis_id, frames)


@shared_task(bind=True, max_retries=2)
def run_content_analysis(self, analysis_id: str, transcript: str, segments: list) -> Dict[str, Any]:
    """Standalone content analysis task."""
    return _run_content_analysis_sync(analysis_id, transcript, segments)


@shared_task(bind=True)
def generate_analysis_report(self, analysis_id: str, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone report generation task."""
    return _generate_report_sync(analysis_id, analysis_results)


def _detect_face_region_sync(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect face region in video frames to handle webcam overlay layouts."""
    try:
        from app.analyzers.face_region import FaceRegionDetector
        
        detector = FaceRegionDetector()
        result = detector.detect_face_region(frames)
        
        logger.info(
            f"Face region detection: has_face={result['has_face']}, "
            f"is_overlay={result['is_overlay']}, "
            f"area_ratio={result['face_area_ratio']}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Face region detection failed: {e}")
        return {
            "has_face": False,
            "is_overlay": False,
            "crop_region": None,
            "frame_size": (0, 0),
            "face_area_ratio": 0.0,
        }


def _create_cropped_frames_sync(
    frames: List[Dict[str, Any]],
    crop_region: tuple,
    output_dir: str,
) -> List[Dict[str, Any]]:
    """Create cropped frames focused on the person region."""
    try:
        from app.analyzers.face_region import FaceRegionDetector
        
        detector = FaceRegionDetector()
        cropped = detector.create_cropped_frames(frames, crop_region, output_dir)
        
        logger.info(f"Created {len(cropped)} cropped frames from {len(frames)} originals")
        return cropped
        
    except Exception as e:
        logger.error(f"Frame cropping failed: {e}. Using original frames.")
        return frames


async def _get_golden_pitch_deck_reference(
    golden_pitch_deck_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get golden pitch deck reference data for comparison.
    
    Args:
        golden_pitch_deck_id: Specific deck ID to compare against. If None, returns None (no comparison).
        
    Returns:
        Dict with reference data or None if not available
    """
    if not golden_pitch_deck_id:
        return None

    from app.db.database import async_session_maker
    from app.db.models import GoldenPitchDeck
    from sqlalchemy import select
    
    async with async_session_maker() as session:
        query = select(GoldenPitchDeck).where(
            GoldenPitchDeck.id == golden_pitch_deck_id
        )
        
        result = await session.execute(query)
        golden_deck = result.scalar_one_or_none()
        
        if not golden_deck:
            return None
        
        return {
            "id": golden_deck.id,
            "name": golden_deck.name,
            "is_processed": golden_deck.is_processed,
            "keywords": golden_deck.keywords,
            "key_phrases": golden_deck.key_phrases,
            "voice_metrics": golden_deck.voice_metrics,
            "pose_metrics": golden_deck.pose_metrics,
            "facial_metrics": golden_deck.facial_metrics,
            "content_metrics": golden_deck.content_metrics,
            "transcript": golden_deck.transcript,
        }


def _run_comparison_sync(
    golden_reference: Dict[str, Any],
    transcript: str,
    voice_result: Dict[str, Any],
    pose_result: Dict[str, Any],
    facial_result: Dict[str, Any],
    content_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run comparison against golden pitch deck.
    
    Args:
        golden_reference: Reference data from golden pitch deck
        transcript: Uploaded video transcript
        voice_result: Voice analysis result
        pose_result: Pose analysis result
        facial_result: Facial analysis result
        content_result: Content analysis result
        
    Returns:
        Dict with comparison results
    """
    try:
        from app.analyzers.comparison import ComparisonAnalyzer
        
        analyzer = ComparisonAnalyzer()
        
        # Compare content (keywords, semantic similarity)
        content_comparison = analyzer.compare_content(
            reference_data=golden_reference,
            uploaded_transcript=transcript,
            uploaded_content_analysis=content_result,
        )
        
        # Compare voice metrics
        voice_comparison = analyzer.compare_voice(
            reference_metrics=golden_reference.get("voice_metrics", {}),
            uploaded_voice_analysis=voice_result,
        )
        
        # Compare pose metrics
        pose_comparison = analyzer.compare_pose(
            reference_metrics=golden_reference.get("pose_metrics", {}),
            uploaded_pose_analysis=pose_result,
        )
        
        # Compare facial metrics
        facial_comparison = analyzer.compare_facial(
            reference_metrics=golden_reference.get("facial_metrics", {}),
            uploaded_facial_analysis=facial_result,
        )
        
        # Generate comparison summary
        summary = analyzer.generate_comparison_summary(
            content_comparison=content_comparison,
            voice_comparison=voice_comparison,
            pose_comparison=pose_comparison,
            facial_comparison=facial_comparison,
            golden_name=golden_reference.get("name", "golden pitch deck"),
        )
        
        return {
            "content_comparison": content_comparison,
            "voice_comparison": voice_comparison,
            "pose_comparison": pose_comparison,
            "facial_comparison": facial_comparison,
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        return {
            "error": str(e),
            "content_comparison": {},
            "voice_comparison": {},
            "pose_comparison": {},
        }

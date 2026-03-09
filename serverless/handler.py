"""
RunPod Serverless Handler for Sales Pitch Analyzer.
Standalone pipeline — no DB, no Celery. Results returned directly in response.
"""

import os
import sys
import time
import uuid
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional

import runpod

# ── Ensure backend package is importable ──────────────────────────────
sys.path.insert(0, "/app/backend")

# ── Model singletons (survive across warm-worker invocations) ─────────
_whisper_model = None
_voice_analyzer = None
_facial_analyzer = None
_pose_analyzer = None
_content_analyzer = None
_comparison_analyzer = None
_report_generator = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from app.analyzers.transcription import WhisperTranscriber
        _whisper_model = WhisperTranscriber()
    return _whisper_model


def _get_voice_analyzer():
    global _voice_analyzer
    if _voice_analyzer is None:
        from app.analyzers.voice import VoiceAnalyzer
        _voice_analyzer = VoiceAnalyzer()
    return _voice_analyzer


def _get_facial_analyzer():
    global _facial_analyzer
    if _facial_analyzer is None:
        from app.analyzers.facial import FacialExpressionAnalyzer
        _facial_analyzer = FacialExpressionAnalyzer()
    return _facial_analyzer


def _get_pose_analyzer():
    global _pose_analyzer
    if _pose_analyzer is None:
        from app.analyzers.pose import PoseAnalyzer
        _pose_analyzer = PoseAnalyzer()
    return _pose_analyzer


def _get_content_analyzer():
    global _content_analyzer
    if _content_analyzer is None:
        from app.analyzers.content import ContentAnalyzer
        _content_analyzer = ContentAnalyzer()
    return _content_analyzer


def _get_comparison_analyzer():
    global _comparison_analyzer
    if _comparison_analyzer is None:
        from app.analyzers.comparison import ComparisonAnalyzer
        _comparison_analyzer = ComparisonAnalyzer()
    return _comparison_analyzer


def _get_report_generator():
    global _report_generator
    if _report_generator is None:
        from app.analyzers.report_generator import ReportGenerator
        _report_generator = ReportGenerator()
    return _report_generator


# ── Utility helpers ───────────────────────────────────────────────────

def _download_video(url: str, dest: str) -> str:
    """Download video from URL to local path."""
    import httpx
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
    return dest


def _extract_audio(video_path: str, output_path: str) -> Dict[str, Any]:
    from moviepy.editor import VideoFileClip
    video = VideoFileClip(video_path)
    audio = video.audio
    if audio is None:
        video.close()
        return {"success": False, "error": "No audio track"}
    audio.write_audiofile(output_path, fps=16000, nbytes=2,
                          codec="pcm_s16le", verbose=False, logger=None)
    duration = video.duration
    video.close()
    return {"success": True, "duration": duration}


def _extract_frames(video_path: str, output_dir: str, fps: float = 0.3) -> list:
    import cv2
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(video_fps / fps))
    frames, idx, count = [], 0, 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % interval == 0:
            ts = idx / video_fps if video_fps > 0 else 0
            path = os.path.join(output_dir, f"frame_{count:06d}_{ts:.2f}s.jpg")
            cv2.imwrite(path, frame)
            frames.append({"path": path, "timestamp": ts, "frame_number": count})
            count += 1
        idx += 1
    cap.release()
    return frames


def _detect_and_crop_face_region(frames, analysis_dir):
    """Detect face region and return cropped frames if webcam overlay."""
    try:
        from app.analyzers.face_region import FaceRegionDetector
        detector = FaceRegionDetector()
        info = detector.detect_face_region(frames)
        if info.get("is_overlay") and info.get("crop_region"):
            cropped_dir = str(Path(analysis_dir) / "cropped_frames")
            return detector.create_cropped_frames(frames, info["crop_region"], cropped_dir)
    except Exception:
        pass
    return frames


# ── Analysis wrappers (no DB writes) ─────────────────────────────────

def _transcribe(audio_path: str) -> Dict[str, Any]:
    t0 = time.time()
    result = _get_whisper().transcribe(audio_path)
    result["_duration"] = time.time() - t0
    return result


def _analyze_voice(audio_path: str) -> Dict[str, Any]:
    t0 = time.time()
    result = _get_voice_analyzer().analyze(audio_path)
    result["_duration"] = time.time() - t0
    return result


def _analyze_facial(frames: list) -> Dict[str, Any]:
    t0 = time.time()
    result = _get_facial_analyzer().analyze_frames(frames)
    result["_duration"] = time.time() - t0
    return result


def _analyze_pose(frames: list) -> Dict[str, Any]:
    t0 = time.time()
    result = _get_pose_analyzer().analyze_frames(frames)
    result["_duration"] = time.time() - t0
    return result


def _analyze_content(transcript: str, segments: list) -> Dict[str, Any]:
    return _get_content_analyzer().analyze(transcript, segments)


def _run_comparison(
    golden_reference: Dict[str, Any],
    transcript: str,
    voice_result: Dict[str, Any],
    pose_result: Dict[str, Any],
    facial_result: Dict[str, Any],
    content_result: Dict[str, Any],
) -> Dict[str, Any]:
    analyzer = _get_comparison_analyzer()
    content_cmp = analyzer.compare_content(
        reference_data=golden_reference,
        uploaded_transcript=transcript,
        uploaded_content_analysis=content_result,
    )
    voice_cmp = analyzer.compare_voice(
        reference_metrics=golden_reference.get("voice_metrics", {}),
        uploaded_voice_analysis=voice_result,
    )
    pose_cmp = analyzer.compare_pose(
        reference_metrics=golden_reference.get("pose_metrics", {}),
        uploaded_pose_analysis=pose_result,
    )
    facial_cmp = analyzer.compare_facial(
        reference_metrics=golden_reference.get("facial_metrics", {}),
        uploaded_facial_analysis=facial_result,
    )
    summary = analyzer.generate_comparison_summary(
        content_comparison=content_cmp,
        voice_comparison=voice_cmp,
        pose_comparison=pose_cmp,
        facial_comparison=facial_cmp,
        golden_name=golden_reference.get("name", "golden pitch deck"),
    )
    return {
        "content_comparison": content_cmp,
        "voice_comparison": voice_cmp,
        "pose_comparison": pose_cmp,
        "facial_comparison": facial_cmp,
        "summary": summary,
    }


def _generate_report(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    return _get_report_generator().generate(analysis_results)


# ── Main handler ──────────────────────────────────────────────────────

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler.

    Input (job["input"]):
        video_url: str              — public URL to download the video
        video_base64: str           — OR base64-encoded video bytes
        is_audio_only: bool         — skip visual analysis (default False)
        golden_reference: dict|None — golden pitch deck reference data for comparison
        frame_fps: float            — frame extraction rate (default 0.3)

    Returns:
        dict with report, transcription, and timing info.
    """
    job_input = job["input"]
    pipeline_start = time.time()

    video_url = job_input.get("video_url")
    video_b64 = job_input.get("video_base64")
    is_audio_only = job_input.get("is_audio_only", False)
    golden_reference = job_input.get("golden_reference")
    frame_fps = job_input.get("frame_fps", 0.3)

    if not video_url and not video_b64:
        return {"error": "Provide 'video_url' or 'video_base64'"}

    # Create temp working directory
    work_dir = tempfile.mkdtemp(prefix="spa_")
    timings: Dict[str, float] = {}

    try:
        # ── Download / decode video ──────────────────────────────
        t0 = time.time()
        ext = ".mp4"
        if video_url:
            video_path = os.path.join(work_dir, f"input{ext}")
            _download_video(video_url, video_path)
        else:
            import base64
            video_path = os.path.join(work_dir, f"input{ext}")
            with open(video_path, "wb") as f:
                f.write(base64.b64decode(video_b64))
        timings["download"] = round(time.time() - t0, 2)

        audio_path = os.path.join(work_dir, "audio.wav")
        frames_dir = os.path.join(work_dir, "frames")

        # ── Phase 1: Extract audio + frames in parallel ──────────
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=2) as pool:
            audio_fut = pool.submit(_extract_audio, video_path, audio_path)
            frames_fut = pool.submit(
                lambda: [] if is_audio_only else _extract_frames(video_path, frames_dir, frame_fps)
            )
            audio_result = audio_fut.result()
            raw_frames = frames_fut.result()

        has_audio = audio_result.get("success", False)

        # Face region detection / cropping
        if raw_frames:
            person_frames = _detect_and_crop_face_region(raw_frames, work_dir)
        else:
            person_frames = []

        timings["extraction"] = round(time.time() - t0, 2)

        # ── Phase 2: Parallel analyses ───────────────────────────
        t0 = time.time()
        transcription_result = {"text": "", "segments": [], "skipped": True}
        voice_result = {"skipped": True}
        facial_result = {"skipped": True}
        pose_result = {"skipped": True}

        # Sub-sample frames for speed
        MAX_FRAMES = 30
        if len(person_frames) > MAX_FRAMES:
            step = len(person_frames) / MAX_FRAMES
            sampled = [person_frames[int(i * step)] for i in range(MAX_FRAMES)]
        else:
            sampled = person_frames

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {}
            if has_audio:
                futures["transcription"] = pool.submit(_transcribe, audio_path)
                futures["voice"] = pool.submit(_analyze_voice, audio_path)
            if not is_audio_only and sampled:
                futures["facial"] = pool.submit(_analyze_facial, sampled)
                futures["pose"] = pool.submit(_analyze_pose, sampled)

            for name, fut in futures.items():
                try:
                    res = fut.result()
                    dur = res.pop("_duration", None)
                    if dur:
                        timings[name] = round(dur, 2)
                    if name == "transcription":
                        transcription_result = res
                    elif name == "voice":
                        voice_result = res
                    elif name == "facial":
                        facial_result = res
                    elif name == "pose":
                        pose_result = res
                except Exception as e:
                    timings[name] = f"error: {e}"

        timings["phase2_total"] = round(time.time() - t0, 2)

        # ── Phase 3: Content analysis (needs transcript) ─────────
        t0 = time.time()
        transcript_text = transcription_result.get("text", "")
        if transcript_text and not transcription_result.get("skipped"):
            content_result = _analyze_content(
                transcript_text,
                transcription_result.get("segments", []),
            )
        else:
            content_result = {"skipped": True, "reason": "No transcript"}
        timings["content"] = round(time.time() - t0, 2)

        # ── Phase 4: Comparison + Report ─────────────────────────
        t0 = time.time()
        comparison_result = None
        if golden_reference and golden_reference.get("is_processed"):
            comparison_result = _run_comparison(
                golden_reference, transcript_text,
                voice_result, pose_result, facial_result, content_result,
            )

        report = _generate_report({
            "voice": voice_result,
            "facial": facial_result,
            "pose": pose_result,
            "content": content_result,
            "has_audio": has_audio,
            "comparison": comparison_result,
            "golden_pitch_deck_id": golden_reference.get("id") if golden_reference else None,
        })
        timings["report"] = round(time.time() - t0, 2)
        timings["total"] = round(time.time() - pipeline_start, 2)

        return {
            "report": report,
            "transcription": {
                "text": transcript_text,
                "segments": transcription_result.get("segments", []),
                "language": transcription_result.get("language", "en"),
            },
            "timings": timings,
        }

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


# ── Entry point ───────────────────────────────────────────────────────
runpod.serverless.start({"handler": handler})

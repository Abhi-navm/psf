"""
Custom exceptions for Sales Pitch Analyzer.
"""

from typing import Any, Dict, Optional


class SalesPitchAnalyzerError(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class VideoProcessingError(SalesPitchAnalyzerError):
    """Error during video processing."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VIDEO_PROCESSING_ERROR", details)


class VideoNotFoundError(SalesPitchAnalyzerError):
    """Video file not found."""
    
    def __init__(self, video_id: str):
        super().__init__(
            f"Video with ID {video_id} not found",
            "VIDEO_NOT_FOUND",
            {"video_id": video_id}
        )


class VideoTooLargeError(SalesPitchAnalyzerError):
    """Video file exceeds size limit."""
    
    def __init__(self, size_mb: float, max_size_mb: int):
        super().__init__(
            f"Video size ({size_mb:.1f}MB) exceeds maximum allowed ({max_size_mb}MB)",
            "VIDEO_TOO_LARGE",
            {"size_mb": size_mb, "max_size_mb": max_size_mb}
        )


class VideoDurationError(SalesPitchAnalyzerError):
    """Video duration exceeds limit."""
    
    def __init__(self, duration: float, max_duration: int):
        super().__init__(
            f"Video duration ({duration:.0f}s) exceeds maximum allowed ({max_duration}s)",
            "VIDEO_TOO_LONG",
            {"duration_seconds": duration, "max_duration_seconds": max_duration}
        )


class InvalidVideoFormatError(SalesPitchAnalyzerError):
    """Invalid video format."""
    
    def __init__(self, format: str, allowed_formats: list):
        super().__init__(
            f"Invalid video format: {format}. Allowed: {', '.join(allowed_formats)}",
            "INVALID_VIDEO_FORMAT",
            {"format": format, "allowed_formats": allowed_formats}
        )


class AnalysisNotFoundError(SalesPitchAnalyzerError):
    """Analysis not found."""
    
    def __init__(self, analysis_id: str):
        super().__init__(
            f"Analysis with ID {analysis_id} not found",
            "ANALYSIS_NOT_FOUND",
            {"analysis_id": analysis_id}
        )


class AnalysisInProgressError(SalesPitchAnalyzerError):
    """Analysis is already in progress."""
    
    def __init__(self, video_id: str):
        super().__init__(
            f"Analysis already in progress for video {video_id}",
            "ANALYSIS_IN_PROGRESS",
            {"video_id": video_id}
        )


class AIModelError(SalesPitchAnalyzerError):
    """Error with AI model processing."""
    
    def __init__(self, model_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"AI Model '{model_name}' error: {message}",
            "AI_MODEL_ERROR",
            {"model_name": model_name, **(details or {})}
        )


class TranscriptionError(AIModelError):
    """Error during transcription."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("whisper", message, details)


class VideoTooShortError(SalesPitchAnalyzerError):
    """Video or audio clip is shorter than the minimum required duration."""

    def __init__(self, duration: float, min_duration: int):
        super().__init__(
            f"Video too short ({duration:.0f}s). Minimum allowed: {min_duration}s",
            "VIDEO_TOO_SHORT",
            {"duration_seconds": round(duration, 2), "min_duration_seconds": min_duration},
        )


class UnsupportedLanguageError(SalesPitchAnalyzerError):
    """Whisper detected a language that is not in the supported list."""

    def __init__(self, language: str, supported: list):
        super().__init__(
            f"Unsupported language detected: '{language}'. Supported: {supported}",
            "UNSUPPORTED_LANGUAGE",
            {"detected_language": language, "supported_languages": supported},
        )


class TranscriptTooShortError(SalesPitchAnalyzerError):
    """Transcript word count is below the minimum threshold."""

    def __init__(self, word_count: int, min_words: int):
        super().__init__(
            f"Transcript too short ({word_count} words). Minimum required: {min_words}",
            "TRANSCRIPT_TOO_SHORT",
            {"word_count": word_count, "min_words": min_words},
        )


class ContentNotRelevantError(SalesPitchAnalyzerError):
    """LLM classifier determined the content is not a sales pitch or business presentation."""

    def __init__(self, reason: str = ""):
        super().__init__(
            "Content does not appear to be a sales pitch or business presentation",
            "CONTENT_NOT_RELEVANT",
            {"reason": reason},
        )


class StorageError(SalesPitchAnalyzerError):
    """Error with file storage."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "STORAGE_ERROR", details)

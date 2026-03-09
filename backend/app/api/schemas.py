"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ============== Enums ==============

class AnalysisStatusEnum(str, Enum):
    """Analysis status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING_VOICE = "analyzing_voice"
    ANALYZING_FACIAL = "analyzing_facial"
    ANALYZING_POSE = "analyzing_pose"
    ANALYZING_CONTENT = "analyzing_content"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


# ============== Video Schemas ==============

class VideoBase(BaseModel):
    """Base video schema."""
    original_filename: str


class VideoCreate(VideoBase):
    """Schema for video upload."""
    pass


class VideoResponse(VideoBase):
    """Schema for video response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    is_audio_only: bool = False
    created_at: datetime


class VideoWithAnalysisResponse(VideoBase):
    """Schema for video response with analysis info."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    is_audio_only: bool = False
    created_at: datetime
    # Analysis info
    analysis_id: Optional[str] = None
    analysis_status: Optional[str] = None
    overall_score: Optional[float] = None
    comparison_score: Optional[float] = None


class VideoListResponse(BaseModel):
    """Schema for video list response."""
    videos: List[VideoWithAnalysisResponse]
    total: int
    page: int
    page_size: int


# ============== Analysis Schemas ==============

class AnalysisCreate(BaseModel):
    """Schema for starting analysis."""
    video_id: str
    # Optional: specify which golden pitch deck to compare against
    # If not provided, uses the active golden pitch deck
    golden_pitch_deck_id: Optional[str] = None
    # If True, skip comparison even if golden pitch deck exists
    skip_comparison: bool = False


class AnalysisStatusResponse(BaseModel):
    """Schema for analysis status response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    video_id: str
    status: AnalysisStatusEnum
    progress: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class TranscriptionResponse(BaseModel):
    """Schema for transcription response."""
    model_config = ConfigDict(from_attributes=True)
    
    full_text: str
    language: str
    confidence: float
    segments: Optional[List[Dict[str, Any]]] = None
    word_timestamps: Optional[List[Dict[str, Any]]] = None


class VoiceAnalysisResponse(BaseModel):
    """Schema for voice analysis response."""
    model_config = ConfigDict(from_attributes=True)
    
    overall_score: float
    energy_score: float
    clarity_score: float
    pace_score: float
    confidence_score: float = 50.0
    tone_score: float = 50.0
    avg_pitch: Optional[float] = None
    pitch_variance: Optional[float] = None
    speaking_rate_wpm: Optional[float] = None
    pause_frequency: Optional[float] = None
    emotion_timeline: Optional[List[Dict[str, Any]]] = None
    issues: Optional[List[Dict[str, Any]]] = None


class FacialAnalysisResponse(BaseModel):
    """Schema for facial analysis response."""
    model_config = ConfigDict(from_attributes=True)
    
    overall_score: float
    positivity_score: float
    engagement_score: float
    confidence_score: float
    emotion_distribution: Optional[Dict[str, float]] = None
    emotion_timeline: Optional[List[Dict[str, Any]]] = None
    eye_contact_percentage: Optional[float] = None
    issues: Optional[List[Dict[str, Any]]] = None


class PoseAnalysisResponse(BaseModel):
    """Schema for pose analysis response."""
    model_config = ConfigDict(from_attributes=True)
    
    overall_score: float
    posture_score: float
    gesture_score: float
    movement_score: float
    avg_shoulder_alignment: Optional[float] = None
    fidgeting_frequency: Optional[float] = None
    gesture_frequency: Optional[float] = None
    pose_timeline: Optional[List[Dict[str, Any]]] = None
    issues: Optional[List[Dict[str, Any]]] = None


class ContentAnalysisResponse(BaseModel):
    """Schema for content analysis response."""
    model_config = ConfigDict(from_attributes=True)
    
    overall_score: float
    clarity_score: float
    persuasion_score: float
    structure_score: float
    filler_words: Optional[List[Dict[str, Any]]] = None
    filler_word_count: int = 0
    weak_phrases: Optional[List[Dict[str, Any]]] = None
    negative_language: Optional[List[Dict[str, Any]]] = None
    key_points: Optional[List[str]] = None
    llm_feedback: Optional[str] = None


class AnalysisReportResponse(BaseModel):
    """Schema for analysis report response."""
    model_config = ConfigDict(from_attributes=True)
    
    overall_score: float
    voice_score: float
    facial_score: float
    pose_score: float
    content_score: float
    executive_summary: str
    strengths: Optional[List[str]] = None
    improvements: Optional[List[Dict[str, Any]]] = None
    timestamped_issues: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    # Comparison fields (present when compared against golden pitch deck)
    golden_pitch_deck_id: Optional[str] = None
    comparison_overall_score: Optional[float] = None
    content_similarity_score: Optional[float] = None
    keyword_coverage_score: Optional[float] = None
    voice_similarity_score: Optional[float] = None
    pose_similarity_score: Optional[float] = None
    facial_similarity_score: Optional[float] = None
    keyword_comparison: Optional[Dict[str, Any]] = None
    content_comparison: Optional[Dict[str, Any]] = None
    pose_comparison: Optional[Dict[str, Any]] = None
    voice_comparison: Optional[Dict[str, Any]] = None
    facial_comparison: Optional[Dict[str, Any]] = None


class FullAnalysisResponse(BaseModel):
    """Schema for complete analysis response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    video_id: str
    status: AnalysisStatusEnum
    progress: int
    video: VideoResponse
    transcription: Optional[TranscriptionResponse] = None
    voice_analysis: Optional[VoiceAnalysisResponse] = None
    facial_analysis: Optional[FacialAnalysisResponse] = None
    pose_analysis: Optional[PoseAnalysisResponse] = None
    content_analysis: Optional[ContentAnalysisResponse] = None
    report: Optional[AnalysisReportResponse] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============== Health Check ==============

class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = "ok"
    environment: str
    version: str = "0.1.0"
    services: Dict[str, str]


# ============== Error Response ==============

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None


# ============== Golden Pitch Deck Schemas ==============

class GoldenPitchDeckCreate(BaseModel):
    """Schema for creating a golden pitch deck."""
    video_id: str
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    set_as_active: bool = True


class GoldenPitchDeckUpdate(BaseModel):
    """Schema for updating a golden pitch deck."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class GoldenPitchDeckResponse(BaseModel):
    """Schema for golden pitch deck response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    description: Optional[str] = None
    video_id: str
    is_active: bool
    is_processed: bool
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Reference data (when processed)
    keywords: Optional[Dict[str, Any]] = None
    key_phrases: Optional[List[str]] = None
    voice_metrics: Optional[Dict[str, Any]] = None
    pose_metrics: Optional[Dict[str, Any]] = None
    facial_metrics: Optional[Dict[str, Any]] = None
    content_metrics: Optional[Dict[str, Any]] = None


class GoldenPitchDeckListResponse(BaseModel):
    """Schema for golden pitch deck list response."""
    items: List[GoldenPitchDeckResponse]
    total: int

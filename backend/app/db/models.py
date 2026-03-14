"""
Database models for Sales Pitch Analyzer.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


class AnalysisStatus(str, PyEnum):
    """Status of video analysis."""
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


class Video(Base):
    """Video/Audio file metadata."""
    
    __tablename__ = "videos"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # seconds
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_audio_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analyses: Mapped[List["Analysis"]] = relationship(
        "Analysis", back_populates="video", cascade="all, delete-orphan"
    )


class Analysis(Base):
    """Video analysis record."""
    
    __tablename__ = "analyses"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-100
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Comparison tracking
    golden_pitch_deck_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    skip_comparison: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Task tracking
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="analyses")
    transcription: Mapped[Optional["Transcription"]] = relationship(
        "Transcription", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    voice_analysis: Mapped[Optional["VoiceAnalysis"]] = relationship(
        "VoiceAnalysis", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    facial_analysis: Mapped[Optional["FacialAnalysis"]] = relationship(
        "FacialAnalysis", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    pose_analysis: Mapped[Optional["PoseAnalysis"]] = relationship(
        "PoseAnalysis", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    content_analysis: Mapped[Optional["ContentAnalysis"]] = relationship(
        "ContentAnalysis", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    report: Mapped[Optional["AnalysisReport"]] = relationship(
        "AnalysisReport", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )


class Transcription(Base):
    """Speech transcription results."""
    
    __tablename__ = "transcriptions"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Word-level timestamps: [{word, start, end, confidence}, ...]
    word_timestamps: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Segment-level: [{text, start, end}, ...]
    segments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="transcription")


class VoiceAnalysis(Base):
    """Voice and audio analysis results."""
    
    __tablename__ = "voice_analyses"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Overall scores (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    energy_score: Mapped[float] = mapped_column(Float, nullable=False)
    clarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    pace_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    tone_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    
    # Metrics
    avg_pitch: Mapped[float] = mapped_column(Float, nullable=True)
    pitch_variance: Mapped[float] = mapped_column(Float, nullable=True)
    speaking_rate_wpm: Mapped[float] = mapped_column(Float, nullable=True)  # words per minute
    pause_frequency: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Emotion detection: [{timestamp, emotion, confidence}, ...]
    emotion_timeline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Issues detected: [{type, timestamp, description, severity}, ...]
    issues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="voice_analysis")


class FacialAnalysis(Base):
    """Facial expression analysis results."""
    
    __tablename__ = "facial_analyses"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Overall scores (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    positivity_score: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Emotion distribution: {happy: %, sad: %, angry: %, ...}
    emotion_distribution: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timeline: [{timestamp, dominant_emotion, emotions: {}, confidence}, ...]
    emotion_timeline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Eye contact metrics
    eye_contact_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Issues: [{type, timestamp, description, severity}, ...]
    issues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="facial_analysis")


class PoseAnalysis(Base):
    """Body pose and gesture analysis results."""
    
    __tablename__ = "pose_analyses"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Overall scores (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    posture_score: Mapped[float] = mapped_column(Float, nullable=False)
    gesture_score: Mapped[float] = mapped_column(Float, nullable=False)
    movement_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Metrics
    avg_shoulder_alignment: Mapped[float] = mapped_column(Float, nullable=True)
    fidgeting_frequency: Mapped[float] = mapped_column(Float, nullable=True)
    gesture_frequency: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Detected poses timeline: [{timestamp, pose_type, confidence}, ...]
    pose_timeline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Issues: [{type, timestamp, description, severity}, ...]
    issues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="pose_analysis")


class ContentAnalysis(Base):
    """Speech content analysis results (via LLM)."""
    
    __tablename__ = "content_analyses"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Overall scores (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    clarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    persuasion_score: Mapped[float] = mapped_column(Float, nullable=False)
    structure_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Filler words: [{word, count, timestamps: []}, ...]
    filler_words: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    filler_word_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Weak phrases: [{phrase, timestamp, suggestion}, ...]
    weak_phrases: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Negative language: [{phrase, timestamp, sentiment_score}, ...]
    negative_language: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Key points extracted
    key_points: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # LLM feedback
    llm_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="content_analysis")


class GoldenPitchDeck(Base):
    """Golden (master reference) pitch deck video for comparison."""
    
    __tablename__ = "golden_pitch_decks"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Video file info
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    
    # Is this the active golden reference?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Extracted reference data (cached for comparison)
    # Keywords extracted from transcript
    keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Key phrases and topics
    key_phrases: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Voice metrics reference
    voice_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Pose/gesture reference patterns
    pose_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Facial expression reference
    facial_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Content structure and key points
    content_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Full transcript
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship("Video")


class AnalysisReport(Base):
    """Final aggregated analysis report."""
    
    __tablename__ = "analysis_reports"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    
    # Reference to golden pitch deck used for comparison (if any)
    golden_pitch_deck_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("golden_pitch_decks.id", ondelete="SET NULL"), nullable=True
    )
    
    # Overall score (0-100)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Category scores
    voice_score: Mapped[float] = mapped_column(Float, nullable=False)
    facial_score: Mapped[float] = mapped_column(Float, nullable=False)
    pose_score: Mapped[float] = mapped_column(Float, nullable=False)
    content_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Comparison scores (similarity to golden pitch deck, 0-100)
    # None if no golden pitch deck was used
    comparison_overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    content_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    keyword_coverage_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    voice_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pose_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    facial_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Detailed comparison results
    # {matched_keywords: [], missing_keywords: [], extra_keywords: []}
    keyword_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Detailed content comparison analysis
    content_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Pose/gesture comparison details
    pose_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Voice metrics comparison
    voice_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Facial expression comparison
    facial_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Summary
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Strengths: [str, ...]
    strengths: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Areas for improvement: [{area, description, priority}, ...]
    improvements: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timestamped issues: [{timestamp, category, issue, severity, suggestion}, ...]
    timestamped_issues: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Recommendations
    recommendations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    
    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="report")

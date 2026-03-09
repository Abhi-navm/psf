"""
Facial expression analysis using DeepFace.
"""

from typing import Dict, Any, List, Optional
import os

from app.core.logging import logger


class FacialExpressionAnalyzer:
    """Analyze facial expressions from video frames."""
    
    # Emotion weights for sales context (positive emotions are better)
    EMOTION_WEIGHTS = {
        "happy": 1.0,
        "neutral": 0.6,
        "surprise": 0.5,
        "sad": -0.3,
        "angry": -0.5,
        "fear": -0.4,
        "disgust": -0.5,
    }
    
    # Positive emotions for sales
    POSITIVE_EMOTIONS = {"happy", "surprise"}
    NEGATIVE_EMOTIONS = {"sad", "angry", "fear", "disgust"}
    
    def __init__(self):
        """Initialize the facial analyzer."""
        self._analyzer = None
    
    @property
    def analyzer(self):
        """Lazy load DeepFace."""
        if self._analyzer is None:
            try:
                from deepface import DeepFace
                self._analyzer = DeepFace
                logger.info("DeepFace loaded successfully")
            except ImportError as e:
                logger.error(f"Failed to load DeepFace: {e}")
                raise
        return self._analyzer
    
    def analyze_frames(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze facial expressions across video frames.
        
        Args:
            frames: List of frame info dicts with 'path' and 'timestamp'
            
        Returns:
            Dict with facial analysis results
        """
        logger.info(f"Analyzing {len(frames)} frames for facial expressions")
        
        emotion_timeline = []
        emotion_counts = {e: 0 for e in self.EMOTION_WEIGHTS.keys()}
        face_detected_count = 0
        total_frames = len(frames)
        
        issues = []
        
        for frame_info in frames:
            frame_path = frame_info.get("path")
            timestamp = frame_info.get("timestamp", 0)
            
            if not frame_path or not os.path.exists(frame_path):
                continue
            
            try:
                result = self._analyze_single_frame(frame_path)
                
                if result:
                    face_detected_count += 1
                    dominant_emotion = result["dominant_emotion"]
                    emotions = result["emotions"]
                    
                    emotion_counts[dominant_emotion] = emotion_counts.get(dominant_emotion, 0) + 1
                    
                    emotion_timeline.append({
                        "timestamp": timestamp,
                        "dominant_emotion": dominant_emotion,
                        "emotions": emotions,
                        "confidence": emotions.get(dominant_emotion, 0),
                    })
                    
                    # Detect issues in real-time
                    frame_issues = self._detect_frame_issues(
                        timestamp, dominant_emotion, emotions
                    )
                    issues.extend(frame_issues)
                    
            except Exception as e:
                logger.debug(f"Frame analysis failed for {frame_path}: {e}")
        
        # Calculate emotion distribution
        if face_detected_count > 0:
            emotion_distribution = {
                e: count / face_detected_count * 100 
                for e, count in emotion_counts.items()
            }
        else:
            emotion_distribution = {}
        
        # Calculate scores
        scores = self._calculate_scores(emotion_distribution, face_detected_count, total_frames)
        
        # Consolidate issues (remove duplicates, keep most severe)
        consolidated_issues = self._consolidate_issues(issues)
        
        return {
            "overall_score": scores["overall"],
            "positivity_score": scores["positivity"],
            "engagement_score": scores["engagement"],
            "confidence_score": scores["confidence"],
            "emotion_distribution": emotion_distribution,
            "emotion_timeline": emotion_timeline,
            "eye_contact_percentage": (face_detected_count / total_frames * 100) if total_frames > 0 else 0,
            "issues": consolidated_issues,
            "frames_analyzed": face_detected_count,
            "total_frames": total_frames,
        }
    
    def _analyze_single_frame(self, frame_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a single frame for facial expressions."""
        try:
            result = self.analyzer.analyze(
                frame_path,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )
            
            if result and len(result) > 0:
                face_result = result[0]
                return {
                    "dominant_emotion": face_result.get("dominant_emotion", "neutral"),
                    "emotions": face_result.get("emotion", {}),
                }
            return None
            
        except Exception as e:
            logger.debug(f"DeepFace analysis error: {e}")
            return None
    
    def _detect_frame_issues(
        self, 
        timestamp: float, 
        dominant_emotion: str, 
        emotions: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Detect issues in a single frame."""
        issues = []
        
        # Check for negative emotions
        if dominant_emotion in self.NEGATIVE_EMOTIONS:
            severity = "high" if emotions.get(dominant_emotion, 0) > 70 else "medium"
            
            issue_descriptions = {
                "sad": ("Sad expression detected", "Maintain a positive, upbeat demeanor"),
                "angry": ("Angry expression detected", "Relax facial muscles and maintain composure"),
                "fear": ("Anxious expression detected", "Take a breath and project confidence"),
                "disgust": ("Negative expression detected", "Keep a neutral or positive expression"),
            }
            
            desc, suggestion = issue_descriptions.get(
                dominant_emotion, 
                ("Negative expression", "Maintain positive expression")
            )
            
            issues.append({
                "type": f"negative_expression_{dominant_emotion}",
                "timestamp": timestamp,
                "severity": severity,
                "description": desc,
                "suggestion": suggestion,
            })
        
        # Check for lack of positive emotion over time
        happy_score = emotions.get("happy", 0)
        if happy_score < 5 and dominant_emotion == "neutral":
            issues.append({
                "type": "lack_of_enthusiasm",
                "timestamp": timestamp,
                "severity": "low",
                "description": "Expression appears flat or unenthusiastic",
                "suggestion": "Add more warmth and enthusiasm to your expression",
            })
        
        return issues
    
    def _consolidate_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consolidate similar issues into summarized issues."""
        if not issues:
            return []
        
        # Group by type
        issue_groups = {}
        for issue in issues:
            issue_type = issue["type"]
            if issue_type not in issue_groups:
                issue_groups[issue_type] = []
            issue_groups[issue_type].append(issue)
        
        consolidated = []
        for issue_type, group in issue_groups.items():
            # Report any detected issues
            if len(group) >= 1:
                timestamps = [i["timestamp"] for i in group]
                max_severity = max(group, key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x["severity"], 0))
                
                consolidated.append({
                    "type": issue_type,
                    "timestamps": timestamps[:5],  # First 5 occurrences
                    "occurrence_count": len(group),
                    "severity": max_severity["severity"],
                    "description": max_severity["description"],
                    "suggestion": max_severity["suggestion"],
                })
        
        # Sort by severity and occurrence
        severity_order = {"high": 0, "medium": 1, "low": 2}
        consolidated.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x["occurrence_count"]))
        
        return consolidated[:10]  # Return top 10 issues
    
    def _calculate_scores(
        self, 
        emotion_distribution: Dict[str, float],
        face_detected: int,
        total_frames: int,
    ) -> Dict[str, float]:
        """Calculate facial expression scores."""
        
        if not emotion_distribution:
            return {
                "overall": 50.0,
                "positivity": 50.0,
                "engagement": 50.0,
                "confidence": 50.0,
            }
        
        # Positivity score (weighted sum of positive emotions)
        positive_pct = sum(
            emotion_distribution.get(e, 0) for e in self.POSITIVE_EMOTIONS
        )
        negative_pct = sum(
            emotion_distribution.get(e, 0) for e in self.NEGATIVE_EMOTIONS
        )
        neutral_pct = emotion_distribution.get("neutral", 0)
        
        positivity_score = min(100, max(0, 50 + positive_pct - negative_pct))
        
        # Engagement score (not too neutral, presence of expression)
        engagement_score = 100 - (neutral_pct * 0.3) - (negative_pct * 0.5)
        engagement_score = min(100, max(0, engagement_score))
        
        # Confidence score (based on face detection and lack of fear/anxiety)
        face_visibility = (face_detected / total_frames * 100) if total_frames > 0 else 0
        fear_penalty = emotion_distribution.get("fear", 0) * 0.5
        confidence_score = min(100, max(0, face_visibility - fear_penalty))
        
        # Overall score
        overall = (positivity_score * 0.4 + engagement_score * 0.3 + confidence_score * 0.3)
        
        return {
            "overall": round(overall, 1),
            "positivity": round(positivity_score, 1),
            "engagement": round(engagement_score, 1),
            "confidence": round(confidence_score, 1),
        }

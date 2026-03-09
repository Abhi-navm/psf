"""
Voice and audio analysis using SpeechBrain and Librosa.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.core.config import settings
from app.core.logging import logger


class VoiceAnalyzer:
    """Analyze voice characteristics from audio."""
    
    # Ideal speaking rate ranges
    IDEAL_WPM_MIN = 120
    IDEAL_WPM_MAX = 150
    
    # Filler word patterns
    COMMON_FILLERS = ["um", "uh", "like", "you know", "basically", "actually", 
                      "literally", "so", "well", "right", "okay"]
    
    def __init__(self):
        """Initialize the voice analyzer."""
        self._emotion_model = None
    
    @property
    def emotion_model(self):
        """Lazy load SpeechBrain emotion recognition model."""
        if self._emotion_model is None and not hasattr(self, '_emotion_model_failed'):
            try:
                from speechbrain.inference.interfaces import foreign_class
                
                self._emotion_model = foreign_class(
                    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                    pymodule_file="custom_interface.py",
                    classname="CustomEncoderWav2vec2Classifier",
                    savedir="models/emotion_recognition"
                )
                logger.info("SpeechBrain emotion model loaded")
            except Exception as e:
                logger.warning(f"Could not load SpeechBrain model: {e}. Emotion detection will be disabled.")
                self._emotion_model = None
                self._emotion_model_failed = True
        return self._emotion_model
    
    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Perform comprehensive voice analysis.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dict with analysis results
        """
        import librosa
        import soundfile as sf
        
        logger.info(f"Analyzing voice from: {audio_path}")
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr
        
        # Analyze different aspects
        pitch_analysis = self._analyze_pitch(y, sr)
        energy_analysis = self._analyze_energy(y, sr)
        pace_analysis = self._analyze_pace(y, sr, duration)
        emotion_analysis = self._analyze_emotions(audio_path, y, sr)
        
        # Detect issues
        issues = self._detect_issues(
            pitch_analysis, energy_analysis, pace_analysis, emotion_analysis
        )
        
        # Calculate scores
        scores = self._calculate_scores(
            pitch_analysis, energy_analysis, pace_analysis, emotion_analysis
        )
        
        return {
            "overall_score": scores["overall"],
            "energy_score": scores["energy"],
            "clarity_score": scores["clarity"],
            "pace_score": scores["pace"],
            "confidence_score": scores["confidence"],
            "tone_score": scores["tone"],
            "avg_pitch": pitch_analysis["mean_pitch"],
            "pitch_variance": pitch_analysis["pitch_variance"],
            "speaking_rate_wpm": pace_analysis.get("estimated_wpm"),
            "pause_frequency": pace_analysis.get("pause_frequency"),
            "emotion_timeline": emotion_analysis.get("timeline", []),
            "issues": issues,
        }
    
    def _analyze_pitch(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze pitch characteristics."""
        import librosa
        
        # Downsample long audio for faster pyin analysis
        # For audio > 60s, analyze evenly-spaced 60s worth of samples
        max_samples = sr * 60  # 60 seconds max
        if len(y) > max_samples:
            step = len(y) / max_samples
            indices = np.arange(0, len(y), step).astype(int)[:max_samples]
            y_pitch = y[indices]
        else:
            y_pitch = y
        
        # Extract pitch using pyin
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y_pitch, 
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )
        
        # Filter out unvoiced segments
        voiced_f0 = f0[~np.isnan(f0)]
        
        if len(voiced_f0) == 0:
            return {
                "mean_pitch": 0,
                "pitch_variance": 0,
                "pitch_range": 0,
                "is_monotone": True,
            }
        
        mean_pitch = float(np.mean(voiced_f0))
        pitch_std = float(np.std(voiced_f0))
        pitch_range = float(np.max(voiced_f0) - np.min(voiced_f0))
        
        # Monotone detection (low variance relative to mean)
        is_monotone = pitch_std / mean_pitch < 0.1 if mean_pitch > 0 else True
        
        return {
            "mean_pitch": mean_pitch,
            "pitch_variance": pitch_std,
            "pitch_range": pitch_range,
            "is_monotone": is_monotone,
        }
    
    def _analyze_energy(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Analyze energy and volume characteristics."""
        import librosa
        
        # RMS energy
        rms = librosa.feature.rms(y=y)[0]
        
        # Convert to dB
        rms_db = librosa.amplitude_to_db(rms)
        
        mean_energy = float(np.mean(rms_db))
        energy_variance = float(np.std(rms_db))
        
        # Detect energy drops (potential uncertainty)
        energy_drops = np.sum(np.diff(rms_db) < -10)
        
        return {
            "mean_energy": mean_energy,
            "energy_variance": energy_variance,
            "energy_drops": int(energy_drops),
            "is_low_energy": mean_energy < -30,
        }
    
    def _analyze_pace(self, y: np.ndarray, sr: int, duration: float) -> Dict[str, Any]:
        """Analyze speaking pace and pauses."""
        import librosa
        
        # Detect speech segments using energy threshold
        rms = librosa.feature.rms(y=y)[0]
        threshold = np.mean(rms) * 0.5
        
        # Find speech and pause segments
        is_speech = rms > threshold
        
        # Count transitions (approximates syllables/words)
        transitions = np.sum(np.abs(np.diff(is_speech.astype(int))))
        
        # Estimate words per minute (rough approximation)
        # Average ~1.5 syllables per word, ~2 transitions per syllable
        estimated_words = transitions / 3
        estimated_wpm = (estimated_words / duration) * 60 if duration > 0 else 0
        
        # Detect pauses (consecutive silence frames)
        frame_duration = 512 / sr  # Default hop length
        pause_frames = np.sum(~is_speech)
        total_pause_time = pause_frames * frame_duration
        pause_frequency = total_pause_time / duration if duration > 0 else 0
        
        # Check if pace is too fast or too slow
        is_too_fast = estimated_wpm > self.IDEAL_WPM_MAX
        is_too_slow = estimated_wpm < self.IDEAL_WPM_MIN
        
        return {
            "estimated_wpm": float(estimated_wpm),
            "pause_frequency": float(pause_frequency),
            "total_pause_time": float(total_pause_time),
            "is_too_fast": is_too_fast,
            "is_too_slow": is_too_slow,
        }
    
    def _analyze_emotions(
        self, 
        audio_path: str, 
        y: np.ndarray, 
        sr: int
    ) -> Dict[str, Any]:
        """Analyze emotions throughout the audio."""
        import librosa
        
        timeline = []
        dominant_emotions = {}
        
        # Analyze in chunks (every 15 seconds for speed)
        chunk_duration = 15.0
        chunk_samples = int(chunk_duration * sr)
        
        for i in range(0, len(y), chunk_samples):
            chunk = y[i:i + chunk_samples]
            if len(chunk) < sr:  # Skip if less than 1 second
                continue
            
            timestamp = i / sr
            
            try:
                if self.emotion_model is not None:
                    # Use SpeechBrain for emotion detection
                    # This is a placeholder - actual implementation depends on model
                    emotion = self._detect_chunk_emotion(chunk, sr)
                else:
                    # Fallback: estimate emotion from acoustic features
                    emotion = self._estimate_emotion_from_features(chunk, sr)
                
                timeline.append({
                    "timestamp": timestamp,
                    "emotion": emotion["dominant"],
                    "confidence": emotion["confidence"],
                    "emotions": emotion["scores"],
                })
                
                # Count dominant emotions
                dominant_emotions[emotion["dominant"]] = \
                    dominant_emotions.get(emotion["dominant"], 0) + 1
                
            except Exception as e:
                logger.warning(f"Emotion detection failed for chunk at {timestamp}s: {e}")
        
        return {
            "timeline": timeline,
            "dominant_emotions": dominant_emotions,
        }
    
    def _detect_chunk_emotion(self, chunk: np.ndarray, sr: int) -> Dict[str, Any]:
        """Detect emotion in audio chunk using SpeechBrain."""
        # Placeholder - actual implementation would use the model
        return {
            "dominant": "neutral",
            "confidence": 0.5,
            "scores": {"neutral": 0.5, "happy": 0.2, "sad": 0.1, "angry": 0.1, "fear": 0.1}
        }
    
    def _estimate_emotion_from_features(
        self, 
        chunk: np.ndarray, 
        sr: int
    ) -> Dict[str, Any]:
        """Estimate emotion from acoustic features (fallback)."""
        import librosa
        
        # Extract lightweight features only (no pyin — too slow per chunk)
        rms = np.mean(librosa.feature.rms(y=chunk))
        zcr = np.mean(librosa.feature.zero_crossing_rate(chunk))
        
        # Simple rule-based emotion estimation using energy and zero-crossing rate
        if rms > 0.1 and zcr > 0.1:
            dominant = "excited"
            confidence = 0.6
        elif rms < 0.02:
            dominant = "sad"
            confidence = 0.5
        elif zcr < 0.03:
            dominant = "neutral"
            confidence = 0.7
        else:
            dominant = "neutral"
            confidence = 0.5
        
        return {
            "dominant": dominant,
            "confidence": confidence,
            "scores": {dominant: confidence, "neutral": 1 - confidence}
        }
    
    def _detect_issues(
        self,
        pitch: Dict[str, Any],
        energy: Dict[str, Any],
        pace: Dict[str, Any],
        emotion: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Detect voice-related issues."""
        issues = []
        
        # Monotone voice
        if pitch.get("is_monotone"):
            issues.append({
                "type": "monotone_voice",
                "severity": "medium",
                "description": "Voice lacks variation in pitch, may sound monotonous",
                "suggestion": "Try varying your pitch to emphasize key points",
            })
        
        # Low energy
        if energy.get("is_low_energy"):
            issues.append({
                "type": "low_energy",
                "severity": "medium",
                "description": "Speaking volume is consistently low",
                "suggestion": "Speak with more projection and energy",
            })
        
        # Speaking too fast
        if pace.get("is_too_fast"):
            issues.append({
                "type": "speaking_too_fast",
                "severity": "high",
                "description": f"Speaking rate ({pace['estimated_wpm']:.0f} WPM) is above ideal range",
                "suggestion": "Slow down to allow audience to process information",
            })
        
        # Speaking too slow
        if pace.get("is_too_slow"):
            issues.append({
                "type": "speaking_too_slow",
                "severity": "low",
                "description": f"Speaking rate ({pace['estimated_wpm']:.0f} WPM) is below ideal range",
                "suggestion": "Increase pace slightly to maintain audience engagement",
            })
        
        # Excessive pauses
        if pace.get("pause_frequency", 0) > 0.3:
            issues.append({
                "type": "excessive_pauses",
                "severity": "medium",
                "description": "Too many pauses detected in speech",
                "suggestion": "Practice smoother delivery with fewer hesitations",
            })
        
        return issues
    
    def _calculate_scores(
        self,
        pitch: Dict[str, Any],
        energy: Dict[str, Any],
        pace: Dict[str, Any],
        emotion: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate overall and component scores."""
        
        # Energy score (0-100)
        energy_score = 50.0
        if not energy.get("is_low_energy"):
            energy_score = min(100, 60 + energy.get("energy_variance", 0) * 2)
        
        # Clarity score based on pitch variance (not too monotone, not too erratic)
        pitch_variance = pitch.get("pitch_variance", 0)
        if pitch_variance < 10:
            clarity_score = 40.0  # Too monotone
        elif pitch_variance > 100:
            clarity_score = 60.0  # Too erratic
        else:
            clarity_score = 70 + min(30, pitch_variance * 0.5)
        
        # Pace score
        wpm = pace.get("estimated_wpm", 130)
        if self.IDEAL_WPM_MIN <= wpm <= self.IDEAL_WPM_MAX:
            pace_score = 90.0
        else:
            deviation = abs(wpm - 135)  # 135 is middle of ideal range
            pace_score = max(30, 90 - deviation * 0.5)
        
        # Confidence score - based on energy consistency, pitch stability, and emotion
        # Higher energy variance with fewer drops = more confident delivery
        energy_drops = energy.get("energy_drops", 0)
        confidence_base = 70.0
        
        # Penalize for energy drops (uncertainty markers)
        confidence_score = confidence_base - (energy_drops * 3)
        
        # Bonus for good pitch variance (expressive but controlled)
        if 20 <= pitch_variance <= 60:
            confidence_score += 15
        elif 10 <= pitch_variance < 20 or 60 < pitch_variance <= 80:
            confidence_score += 8
        
        # Factor in emotion if available (neutral/happy emotions boost confidence)
        timeline = emotion.get("timeline", [])
        if timeline:
            confident_emotions = ["neutral", "happy", "excited"]
            confident_count = sum(1 for e in timeline if e.get("emotion", "").lower() in confident_emotions)
            emotion_ratio = confident_count / len(timeline) if timeline else 0
            confidence_score += emotion_ratio * 15
        
        confidence_score = max(20, min(100, confidence_score))
        
        # Tone score (Executive presence) - measures professionalism and authority
        # Based on: consistent pacing, appropriate energy, controlled pitch
        tone_base = 60.0
        
        # Reward for ideal speaking pace
        if self.IDEAL_WPM_MIN <= wpm <= self.IDEAL_WPM_MAX:
            tone_base += 15
        elif abs(wpm - 135) < 20:
            tone_base += 8
        
        # Penalize monotone delivery
        if pitch.get("is_monotone"):
            tone_base -= 15
        
        # Reward for energy consistency (lower variance but not flat)
        energy_var = energy.get("energy_variance", 0)
        if 3 <= energy_var <= 8:
            tone_base += 15  # Controlled, professional variation
        elif 2 <= energy_var < 3 or 8 < energy_var <= 12:
            tone_base += 8
        
        # Pause frequency impacts executive tone (strategic pauses are good)
        pause_freq = pace.get("pause_frequency", 0)
        if 0.08 <= pause_freq <= 0.15:
            tone_base += 10  # Good use of pauses for emphasis
        elif pause_freq > 0.25:
            tone_base -= 10  # Too many pauses
        
        tone_score = max(20, min(100, tone_base))
        
        # Overall score (weighted average including new scores)
        overall = (
            energy_score * 0.2 + 
            clarity_score * 0.25 + 
            pace_score * 0.2 + 
            confidence_score * 0.2 + 
            tone_score * 0.15
        )
        
        return {
            "overall": round(overall, 1),
            "energy": round(energy_score, 1),
            "clarity": round(clarity_score, 1),
            "pace": round(pace_score, 1),
            "confidence": round(confidence_score, 1),
            "tone": round(tone_score, 1),
        }

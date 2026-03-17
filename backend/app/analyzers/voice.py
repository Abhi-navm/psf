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
        
        # Calculate speaking time (exclude silence) for accurate WPM
        frame_duration = 512 / sr  # Default hop length
        speech_frames = np.sum(is_speech)
        speaking_time = speech_frames * frame_duration
        
        # Use onset detection for better syllable/word estimation
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(y=y, sr=sr, onset_envelope=onset_env)
        num_onsets = len(onsets)
        
        # Each onset roughly corresponds to a syllable; ~1.5 syllables per word
        estimated_words = num_onsets / 1.5
        
        # Use speaking_time (not total duration) for WPM to avoid penalizing pauses
        effective_duration = max(speaking_time, duration * 0.5)  # At least half the total
        estimated_wpm = (estimated_words / effective_duration) * 60 if effective_duration > 0 else 0
        
        # Detect pauses (consecutive silence frames)
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
        try:
            import torch
            import torchaudio
            
            # Resample to 16kHz if needed
            waveform = torch.tensor(chunk).unsqueeze(0).float()
            
            # Run inference
            out_prob, score, index, text_lab = self.emotion_model.classify_batch(waveform)
            label = text_lab[0].lower()
            prob = float(score.squeeze())
            
            # Map SpeechBrain labels to our emotion set
            label_map = {"hap": "happy", "sad": "sad", "ang": "angry", "neu": "neutral"}
            dominant = label_map.get(label, "neutral")
            
            scores = {"neutral": 0.1, "happy": 0.1, "sad": 0.1, "angry": 0.1}
            scores[dominant] = prob
            remaining = 1.0 - prob
            for k in scores:
                if k != dominant:
                    scores[k] = remaining / (len(scores) - 1)
            
            return {"dominant": dominant, "confidence": prob, "scores": scores}
        except Exception as e:
            logger.warning(f"SpeechBrain emotion detection failed: {e}")
            return self._estimate_emotion_from_features(chunk, sr)
    
    def _estimate_emotion_from_features(
        self, 
        chunk: np.ndarray, 
        sr: int
    ) -> Dict[str, Any]:
        """Estimate emotion from acoustic features (fallback)."""
        import librosa
        
        # Extract lightweight features
        rms = float(np.mean(librosa.feature.rms(y=chunk)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(chunk)))
        spec_cent = float(np.mean(librosa.feature.spectral_centroid(y=chunk, sr=sr)))
        
        # Normalize spectral centroid (higher = brighter/more energetic)
        spec_norm = min(spec_cent / 4000.0, 1.0)
        
        # Multi-feature emotion estimation
        scores = {"neutral": 0.25, "happy": 0.2, "sad": 0.15, "angry": 0.15, "excited": 0.25}
        
        if rms > 0.08 and spec_norm > 0.5:
            scores["excited"] = 0.5
            scores["happy"] = 0.3
            scores["neutral"] = 0.1
        elif rms > 0.05 and zcr > 0.08:
            scores["happy"] = 0.45
            scores["excited"] = 0.25
            scores["neutral"] = 0.15
        elif rms < 0.015:
            scores["sad"] = 0.4
            scores["neutral"] = 0.35
        elif rms > 0.06 and spec_norm > 0.4:
            scores["angry"] = 0.3
            scores["neutral"] = 0.3
            scores["excited"] = 0.2
        else:
            scores["neutral"] = 0.45
            scores["happy"] = 0.25
        
        # Normalize
        total = sum(scores.values())
        scores = {k: round(v / total, 3) for k, v in scores.items()}
        
        dominant = max(scores, key=scores.get)
        confidence = scores[dominant]
        
        return {"dominant": dominant, "confidence": confidence, "scores": scores}
    
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
        mean_energy = energy.get("mean_energy", -30)
        energy_var = energy.get("energy_variance", 0)
        if energy.get("is_low_energy"):
            # Low energy: scale between 30-55 based on how low
            energy_score = max(30, 55 + (mean_energy + 30) * 2)
        else:
            # Normal energy: base 65, boost for good variance (dynamic delivery)
            energy_score = 65.0
            if energy_var > 3:
                energy_score += min(25, energy_var * 3)  # Up to +25 for dynamic delivery
            if mean_energy > -20:
                energy_score += 10  # Strong projection bonus
            energy_score = min(100, energy_score)
        
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
        
        # Confidence score - based on energy consistency, pitch stability, pace, and emotion
        confidence_score = 50.0
        
        # Pitch variance: expressive but controlled = confident
        if 20 <= pitch_variance <= 80:
            confidence_score += 20  # Good expressive range
        elif 10 <= pitch_variance < 20 or 80 < pitch_variance <= 120:
            confidence_score += 12
        elif pitch_variance < 10:
            confidence_score += 0  # Monotone = less confident
        else:
            confidence_score += 5  # Very erratic
        
        # Energy: consistent volume = confident (penalize only excessive drops)
        energy_drops = energy.get("energy_drops", 0)
        drop_rate = energy_drops / max(1, pace.get("estimated_wpm", 100) / 10)
        if drop_rate < 1:
            confidence_score += 15
        elif drop_rate < 2:
            confidence_score += 8
        else:
            confidence_score -= 5
        
        # Pace: speaking at a good pace = confident
        if self.IDEAL_WPM_MIN <= wpm <= self.IDEAL_WPM_MAX:
            confidence_score += 15
        elif abs(wpm - 135) < 30:
            confidence_score += 8
        
        # Factor in emotion if available
        timeline = emotion.get("timeline", [])
        if timeline:
            confident_emotions = ["neutral", "happy", "excited"]
            confident_count = sum(1 for e in timeline if e.get("emotion", "").lower() in confident_emotions)
            emotion_ratio = confident_count / len(timeline)
            confidence_score += emotion_ratio * 10
        
        confidence_score = max(25, min(100, confidence_score))
        
        # Tone score (Executive presence) - measures professionalism and authority
        tone_score = 55.0
        
        # Reward for good speaking pace (within or close to ideal range)
        if self.IDEAL_WPM_MIN <= wpm <= self.IDEAL_WPM_MAX:
            tone_score += 15
        elif abs(wpm - 135) < 30:
            tone_score += 10
        elif abs(wpm - 135) < 50:
            tone_score += 5
        
        # Pitch expressiveness (not monotone but not erratic)
        if pitch.get("is_monotone"):
            tone_score -= 10
        elif 15 <= pitch_variance <= 80:
            tone_score += 10  # Good controlled variation
        
        # Energy consistency
        energy_var = energy.get("energy_variance", 0)
        if 2 <= energy_var <= 12:
            tone_score += 10  # Controlled, professional variation
        elif energy_var > 12:
            tone_score += 3  # A bit too dynamic but still engaged
        
        # Pause frequency (strategic pauses are good, too many is bad)
        pause_freq = pace.get("pause_frequency", 0)
        if 0.05 <= pause_freq <= 0.20:
            tone_score += 10  # Good use of pauses
        elif 0.20 < pause_freq <= 0.30:
            tone_score += 3  # Slightly too many pauses
        elif pause_freq > 0.30:
            tone_score -= 5  # Excessive pausing
        
        tone_score = max(25, min(100, tone_score))
        
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

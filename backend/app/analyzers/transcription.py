"""
Whisper-based speech transcription analyzer.
"""

from typing import Dict, Any, List, Optional
import os
import sys

# Prevent HuggingFace from making HTTP requests when model is already cached
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Add cuDNN DLLs to PATH for ctranslate2 CUDA support (Windows only)
if sys.platform == "win32":
    _cudnn_bin = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
    if os.path.isdir(_cudnn_bin):
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_cudnn_bin)
        if _cudnn_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _cudnn_bin + os.pathsep + os.environ.get("PATH", "")

from app.core.config import settings
from app.core.logging import logger

# Module-level singleton for Whisper model to avoid reloading
_whisper_model_instance = None
_whisper_model_name = None
_whisper_use_faster = None
_whisper_device = None


class WhisperTranscriber:
    """Speech-to-text transcription using OpenAI Whisper."""
    
    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize the transcriber.
        
        Args:
            model_name: Whisper model name (tiny, base, small, medium, large)
            device: Device to run on (cpu or cuda)
        """
        self.model_name = model_name or settings.whisper_model
        self._requested_device = device or settings.whisper_device
        self._model = None
    
    def _get_available_device(self) -> str:
        """Check CUDA availability and return the best available device."""
        if self._requested_device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
                    return "cuda"
                else:
                    logger.warning("CUDA requested but not available. Install PyTorch with CUDA:")
                    logger.warning("  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121")
                    return "cpu"
            except Exception as e:
                logger.warning(f"CUDA check failed: {e}, falling back to CPU")
                return "cpu"
        return self._requested_device
    
    @property
    def model(self):
        """Lazy load the Whisper model (singleton across instances)."""
        global _whisper_model_instance, _whisper_model_name, _whisper_use_faster, _whisper_device
        
        if _whisper_model_instance is not None and _whisper_model_name == self.model_name:
            self._model = _whisper_model_instance
            self._use_faster_whisper = _whisper_use_faster
            self.device = _whisper_device
            return self._model
        
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            
            # Auto-detect available device
            device = self._get_available_device()
            
            try:
                # Try faster-whisper first (more efficient - 2-4x faster)
                from faster_whisper import WhisperModel
                
                # Optimize compute type for GPU
                if device == "cuda":
                    compute_type = "float16"  # Fast GPU inference
                else:
                    compute_type = "int8"  # CPU optimization
                
                try:
                    self._model = WhisperModel(
                        self.model_name,
                        device=device,
                        compute_type=compute_type,
                        cpu_threads=4,
                        num_workers=2,
                    )
                    self.device = device
                except Exception as cuda_err:
                    if device == "cuda":
                        logger.warning(f"faster-whisper CUDA init failed: {cuda_err}, falling back to CPU")
                        self._model = WhisperModel(
                            self.model_name,
                            device="cpu",
                            compute_type="int8",
                            cpu_threads=4,
                            num_workers=2,
                        )
                        self.device = "cpu"
                    else:
                        raise
                
                self._use_faster_whisper = True
                logger.info(f"Using faster-whisper with {compute_type if self.device == device else 'int8'} on {self.device}")
            except ImportError:
                # Fall back to original whisper
                import whisper
                self._model = whisper.load_model(self.model_name, device=device)
                self._use_faster_whisper = False
                self.device = device
                logger.info("Using original whisper")
            
            # Store in module-level singleton
            _whisper_model_instance = self._model
            _whisper_model_name = self.model_name
            _whisper_use_faster = self._use_faster_whisper
            _whisper_device = self.device
        
        return self._model
    
    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dict containing:
                - text: Full transcription text
                - language: Detected language
                - confidence: Average confidence score
                - segments: List of segments with timestamps
                - word_timestamps: Word-level timestamps (if available)
        """
        logger.info(f"Transcribing: {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Force model load to determine which implementation to use
        _ = self.model
        
        if getattr(self, '_use_faster_whisper', False):
            return self._transcribe_faster_whisper(audio_path)
        else:
            return self._transcribe_whisper(audio_path)
    
    def _transcribe_faster_whisper(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe using faster-whisper with optimized settings."""
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,  # Voice activity detection - skips silence
            vad_parameters=dict(
                min_silence_duration_ms=500,  # Skip shorter silences
                speech_pad_ms=200,
            ),
            condition_on_previous_text=True,  # Better context
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
        )
        
        segments_list = []
        word_timestamps = []
        full_text_parts = []
        total_confidence = 0
        segment_count = 0
        
        for segment in segments:
            segments_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob,
            })
            
            full_text_parts.append(segment.text.strip())
            total_confidence += segment.avg_logprob
            segment_count += 1
            
            # Word-level timestamps
            if segment.words:
                for word in segment.words:
                    word_timestamps.append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.probability,
                    })
        
        avg_confidence = total_confidence / segment_count if segment_count > 0 else 0
        # Convert log probability to 0-1 scale
        confidence_score = min(1.0, max(0.0, 1.0 + avg_confidence / 4))
        
        return {
            "text": " ".join(full_text_parts),
            "language": info.language,
            "confidence": confidence_score,
            "segments": segments_list,
            "word_timestamps": word_timestamps,
            "duration": info.duration,
        }
    
    def _transcribe_whisper(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe using original whisper."""
        result = self.model.transcribe(
            audio_path,
            verbose=False,
            word_timestamps=True,
        )
        
        segments_list = []
        word_timestamps = []
        
        for segment in result.get("segments", []):
            segments_list.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
                "confidence": segment.get("avg_logprob", 0),
            })
            
            # Word-level timestamps
            for word in segment.get("words", []):
                word_timestamps.append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "confidence": word.get("probability", 0),
                })
        
        return {
            "text": result["text"],
            "language": result.get("language", "en"),
            "confidence": 0.85,  # Default confidence for original whisper
            "segments": segments_list,
            "word_timestamps": word_timestamps,
        }

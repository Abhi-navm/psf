"""
Speech content analysis using Ollama/Llama 3.
"""

import re
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.core.logging import logger


class ContentAnalyzer:
    """Analyze speech content for sales effectiveness."""
    
    # Common filler words to detect
    FILLER_WORDS = [
        "um", "uh", "er", "ah", "like", "you know", "basically", "actually",
        "literally", "okay", "yeah", "I mean",
        "sort of", "kind of", "stuff", "whatever"
    ]
    
    # Weak phrases that reduce persuasion
    WEAK_PHRASES = [
        ("I think", "State with confidence"),
        ("I guess", "Be more definitive"),
        ("maybe", "Use stronger language"),
        ("probably", "Show certainty"),
        ("I'm not sure", "Research and be confident"),
        ("I hope", "Express commitment instead"),
        ("sort of", "Be specific"),
        ("kind of", "Be precise"),
        ("might be", "State definitively"),
        ("could be", "Use assertive language"),
        ("just", "Remove hedging"),
        ("a little bit", "Be direct"),
        ("honestly", "Implies previous dishonesty"),
        ("to be honest", "May raise doubts"),
    ]
    
    # Negative language patterns
    NEGATIVE_PATTERNS = [
        (r"\bcan't\b", "Focus on what you CAN do"),
        (r"\bwon't\b", "Reframe positively"),
        (r"\bdon't\b", "Use positive framing"),
        (r"\bnever\b", "Avoid absolute negatives"),
        (r"\bproblem\b", "Use 'challenge' or 'opportunity'"),
        (r"\bfail\b", "Focus on success"),
        (r"\bimpossible\b", "Discuss possibilities"),
        (r"\bworry\b", "Use 'consider' instead"),
        (r"\bunfortunately\b", "Reframe the situation"),
        (r"\bbut\b", "Use 'and' for continuation"),
    ]
    
    def __init__(self):
        """Initialize the content analyzer."""
        self._llm_client = None
        self._groq_client = None
        self._llm_backend = None  # "ollama" or "groq"
    
    @property
    def llm_client(self):
        """Lazy load LLM client — try Ollama first, then Groq."""
        if self._llm_client is None and self._llm_backend is None:
            # Try Ollama first (local dev)
            try:
                import ollama
                client = ollama.Client(host=settings.ollama_base_url)
                client.list()  # Test connection
                self._llm_client = client
                self._llm_backend = "ollama"
                logger.info(f"Using Ollama at {settings.ollama_base_url}")
            except Exception:
                pass
            
            # Fall back to Groq
            if self._llm_client is None and settings.groq_api_key:
                try:
                    from groq import Groq
                    self._groq_client = Groq(api_key=settings.groq_api_key)
                    self._llm_backend = "groq"
                    logger.info("Using Groq API for LLM")
                except Exception as e:
                    logger.warning(f"Could not initialize Groq: {e}")
            
            if self._llm_backend is None:
                self._llm_backend = "none"
                logger.warning("No LLM backend available (no Ollama, no Groq API key)")
        
        return self._llm_client
    
    def _llm_generate(self, prompt: str, max_tokens: int = 300, temperature: float = 0.3) -> Optional[str]:
        """Generate text using whatever LLM backend is available."""
        # Ensure client is initialized
        _ = self.llm_client
        
        if self._llm_backend == "ollama" and self._llm_client:
            try:
                response = self._llm_client.generate(
                    model=settings.ollama_model,
                    prompt=prompt,
                    options={"temperature": temperature, "num_predict": max_tokens}
                )
                return response.get("response", "").strip()
            except Exception as e:
                logger.warning(f"Ollama generation failed: {e}")
                return None
        
        if self._llm_backend == "groq" and self._groq_client:
            try:
                response = self._groq_client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Groq generation failed: {e}")
                return None
        
        return None
    
    def analyze(
        self, 
        transcript: str, 
        segments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze speech content for sales effectiveness.
        
        Args:
            transcript: Full transcription text
            segments: Optional list of segments with timestamps
            
        Returns:
            Dict with content analysis results
        """
        logger.info("Analyzing speech content")
        
        if not transcript or not transcript.strip():
            return self._empty_result()
        
        segments = segments or []
        
        # Detect filler words
        filler_analysis = self._detect_filler_words(transcript, segments)
        
        # Detect weak phrases
        weak_phrase_analysis = self._detect_weak_phrases(transcript, segments)
        
        # Detect negative language
        negative_analysis = self._detect_negative_language(transcript, segments)
        
        # Extract key points (using LLM if available)
        key_points = self._extract_key_points(transcript)
        
        # Get LLM feedback
        llm_feedback = self._get_llm_feedback(transcript)
        
        # Calculate scores
        scores = self._calculate_scores(
            filler_analysis,
            weak_phrase_analysis,
            negative_analysis,
            len(transcript.split())
        )
        
        return {
            "overall_score": scores["overall"],
            "clarity_score": scores["clarity"],
            "persuasion_score": scores["persuasion"],
            "structure_score": scores["structure"],
            "filler_words": filler_analysis["details"],
            "filler_word_count": filler_analysis["total_count"],
            "weak_phrases": weak_phrase_analysis,
            "negative_language": negative_analysis,
            "key_points": key_points,
            "llm_feedback": llm_feedback,
        }
    
    def _detect_filler_words(
        self, 
        transcript: str, 
        segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect filler words in transcript."""
        transcript_lower = transcript.lower()
        
        filler_details = []
        total_count = 0
        
        for filler in self.FILLER_WORDS:
            # Find all occurrences
            pattern = r'\b' + re.escape(filler) + r'\b'
            matches = list(re.finditer(pattern, transcript_lower))
            
            if matches:
                count = len(matches)
                total_count += count
                
                # Try to find timestamps
                timestamps = []
                for match in matches[:5]:  # First 5 occurrences
                    position = match.start()
                    timestamp = self._find_timestamp_for_position(
                        position, transcript, segments
                    )
                    if timestamp is not None:
                        timestamps.append(timestamp)
                
                filler_details.append({
                    "word": filler,
                    "count": count,
                    "timestamps": timestamps,
                })
        
        # Sort by count (most frequent first)
        filler_details.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "details": filler_details[:10],  # Top 10
            "total_count": total_count,
        }
    
    def _detect_weak_phrases(
        self, 
        transcript: str, 
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect weak phrases that reduce persuasiveness."""
        transcript_lower = transcript.lower()
        weak_phrases_found = []
        
        for phrase, suggestion in self.WEAK_PHRASES:
            pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
            matches = list(re.finditer(pattern, transcript_lower))
            
            if matches:
                for match in matches[:3]:  # First 3 occurrences
                    position = match.start()
                    timestamp = self._find_timestamp_for_position(
                        position, transcript, segments
                    )
                    
                    weak_phrases_found.append({
                        "phrase": phrase,
                        "timestamp": timestamp,
                        "suggestion": suggestion,
                        "context": self._get_context(transcript, position, 50),
                    })
        
        return weak_phrases_found[:15]  # Top 15
    
    def _detect_negative_language(
        self, 
        transcript: str, 
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect negative language patterns."""
        transcript_lower = transcript.lower()
        negative_found = []
        
        for pattern, suggestion in self.NEGATIVE_PATTERNS:
            matches = list(re.finditer(pattern, transcript_lower))
            
            if matches:
                for match in matches[:3]:
                    position = match.start()
                    word = match.group()
                    timestamp = self._find_timestamp_for_position(
                        position, transcript, segments
                    )
                    
                    negative_found.append({
                        "phrase": word,
                        "timestamp": timestamp,
                        "suggestion": suggestion,
                        "context": self._get_context(transcript, position, 50),
                    })
        
        return negative_found[:15]
    
    def _find_timestamp_for_position(
        self, 
        char_position: int, 
        transcript: str,
        segments: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Find approximate timestamp for a character position."""
        if not segments:
            return None
        
        # Calculate word position
        words_before = len(transcript[:char_position].split())
        
        # Find segment containing this word position
        current_word_count = 0
        for segment in segments:
            segment_text = segment.get("text", "")
            segment_word_count = len(segment_text.split())
            
            if current_word_count + segment_word_count >= words_before:
                return segment.get("start")
            
            current_word_count += segment_word_count
        
        return None
    
    def _get_context(self, transcript: str, position: int, context_chars: int) -> str:
        """Get surrounding context for a position in transcript."""
        start = max(0, position - context_chars)
        end = min(len(transcript), position + context_chars)
        
        context = transcript[start:end]
        if start > 0:
            context = "..." + context
        if end < len(transcript):
            context = context + "..."
        
        return context
    
    def _extract_key_points(self, transcript: str) -> List[str]:
        """Extract key points from the transcript using LLM."""
        prompt = f"""Analyze this sales pitch transcript and extract the 3-5 key points or main messages being communicated. Be concise.

Transcript:
{transcript[:3000]}

Return only a JSON array of strings with the key points, like:
["Key point 1", "Key point 2", "Key point 3"]
"""
        
        response_text = self._llm_generate(prompt, max_tokens=200, temperature=0.3)
        
        if response_text:
            try:
                import json
                match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except Exception as e:
                logger.warning(f"LLM key point parsing failed: {e}")
        
        return self._extract_key_points_simple(transcript)
    
    def _extract_key_points_simple(self, transcript: str) -> List[str]:
        """Simple key point extraction without LLM."""
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Return first few substantial sentences as key points
        return sentences[:5]
    
    def _get_llm_feedback(self, transcript: str) -> Optional[str]:
        """Get comprehensive feedback from LLM."""
        prompt = f"""You are a sales presentation coach. Analyze this sales pitch transcript and provide constructive feedback.

Transcript:
{transcript[:4000]}

Provide brief feedback (max 200 words) covering:
1. Overall impression
2. Strengths
3. Top 2-3 areas for improvement
4. One specific actionable tip

Be encouraging but honest."""
        
        return self._llm_generate(prompt, max_tokens=300, temperature=0.5)
    
    def _calculate_scores(
        self,
        filler_analysis: Dict[str, Any],
        weak_phrases: List[Dict[str, Any]],
        negative_language: List[Dict[str, Any]],
        word_count: int,
    ) -> Dict[str, float]:
        """Calculate content scores."""
        
        if word_count == 0:
            return {
                "overall": 50.0,
                "clarity": 50.0,
                "persuasion": 50.0,
                "structure": 50.0,
            }
        
        # Filler word ratio
        filler_ratio = filler_analysis["total_count"] / word_count
        
        # Clarity score (penalized by fillers)
        if filler_ratio < 0.01:
            clarity_score = 95.0
        elif filler_ratio < 0.02:
            clarity_score = 85.0
        elif filler_ratio < 0.05:
            clarity_score = 70.0
        else:
            clarity_score = max(40, 100 - filler_ratio * 1000)
        
        # Persuasion score (penalized by weak phrases and negative language)
        weak_count = len(weak_phrases)
        negative_count = len(negative_language)
        
        persuasion_base = 90
        persuasion_penalty = (weak_count * 3) + (negative_count * 4)
        persuasion_score = max(30, persuasion_base - persuasion_penalty)
        
        # Structure score (basic heuristics)
        # Longer speeches typically have more structure
        if word_count > 500:
            structure_score = 75.0
        elif word_count > 200:
            structure_score = 70.0
        else:
            structure_score = 60.0
        
        # Adjust based on variety (not too repetitive filler words)
        filler_words = [f.get("word", "") for f in filler_analysis.get("details", [])]
        unique_fillers = len(set(filler_words))
        if unique_fillers < 5:
            structure_score += 10
        
        # Overall score
        overall = (clarity_score * 0.35 + persuasion_score * 0.4 + structure_score * 0.25)
        
        return {
            "overall": round(overall, 1),
            "clarity": round(clarity_score, 1),
            "persuasion": round(persuasion_score, 1),
            "structure": round(min(100, structure_score), 1),
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result for empty transcripts."""
        return {
            "overall_score": 0,
            "clarity_score": 0,
            "persuasion_score": 0,
            "structure_score": 0,
            "filler_words": [],
            "filler_word_count": 0,
            "weak_phrases": [],
            "negative_language": [],
            "key_points": [],
            "llm_feedback": None,
        }

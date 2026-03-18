"""
Comparison analyzer for comparing uploaded videos/audio against the golden pitch deck.
"""

import os
import re
from typing import Dict, Any, List, Optional
from collections import Counter
import math

# Allow HuggingFace to download models on first run, then use cache
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"

from app.core.logging import logger
from app.core.config import settings

# Module-level singleton for SentenceTransformer to avoid reloading
_sentence_transformer_instance = None
_sentence_transformer_device = None


def _get_sentence_transformer(device: str):
    """Get or create the singleton SentenceTransformer instance."""
    global _sentence_transformer_instance, _sentence_transformer_device
    if _sentence_transformer_instance is None or _sentence_transformer_device != device:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer_instance = SentenceTransformer('all-MiniLM-L6-v2', device=device)
            _sentence_transformer_device = device
            logger.info(f"Sentence transformer loaded on {device}")
        except Exception as e:
            logger.warning(f"Could not load sentence transformer: {e}")
            _sentence_transformer_instance = None
    return _sentence_transformer_instance


class ComparisonAnalyzer:
    """Compare uploaded pitch against golden pitch deck reference."""
    
    def __init__(self):
        """Initialize the comparison analyzer."""
        self._llm_client = None
        self._device = settings.embedding_device
    
    @property
    def llm_client(self):
        """Lazy load Ollama client for semantic comparison."""
        if self._llm_client is None:
            try:
                import ollama
                self._llm_client = ollama.Client(host=settings.ollama_base_url)
                logger.info(f"Ollama client connected for comparison")
            except Exception as e:
                logger.warning(f"Could not connect to Ollama for comparison: {e}")
                self._llm_client = None
        return self._llm_client
    
    @property
    def sentence_transformer(self):
        """Get the singleton sentence transformer instance."""
        return _get_sentence_transformer(self._device)
    
    def extract_reference_data(
        self,
        transcript: str,
        voice_analysis: Dict[str, Any],
        pose_analysis: Dict[str, Any],
        facial_analysis: Dict[str, Any],
        content_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract reference data from the golden pitch deck for later comparison.
        
        Args:
            transcript: Full transcription text
            voice_analysis: Voice analysis results
            pose_analysis: Pose analysis results
            facial_analysis: Facial analysis results
            content_analysis: Content analysis results
            
        Returns:
            Dict with extracted reference metrics
        """
        logger.info("Extracting reference data from golden pitch deck")
        
        # Extract keywords from transcript (also extracts key_phrases)
        keywords = self._extract_keywords(transcript)
        
        # Key phrases are now included in keywords extraction
        key_phrases = keywords.get("key_phrases", [])
        
        # Extract voice metrics reference
        voice_metrics = self._extract_voice_metrics(voice_analysis)
        
        # Extract pose metrics reference
        pose_metrics = self._extract_pose_metrics(pose_analysis)
        
        # Extract facial metrics reference
        facial_metrics = self._extract_facial_metrics(facial_analysis)
        
        # Extract content metrics (structure, key points)
        content_metrics = self._extract_content_metrics(content_analysis, transcript)
        
        return {
            "keywords": keywords,
            "key_phrases": key_phrases,
            "voice_metrics": voice_metrics,
            "pose_metrics": pose_metrics,
            "facial_metrics": facial_metrics,
            "content_metrics": content_metrics,
            "transcript": transcript,
        }
    
    def _extract_keywords(self, transcript: str) -> Dict[str, Any]:
        """Extract important keywords and key phrases from transcript."""
        if not transcript:
            return {"keywords": [], "keyword_weights": {}, "key_phrases": []}
        
        # Common stop words to filter out
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once", "here",
            "there", "when", "where", "why", "how", "all", "each", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "and", "but", "if", "or",
            "because", "until", "while", "this", "that", "these", "those", "i",
            "you", "he", "she", "it", "we", "they", "what", "which", "who", "whom",
            "your", "my", "his", "her", "its", "our", "their", "me", "him", "us",
            "them", "myself", "yourself", "himself", "herself", "itself", "ourselves",
            "themselves", "really", "actually", "basically", "like", "um", "uh",
            "going", "get", "got", "know", "think", "want", "see", "look", "come",
            "make", "take", "give", "say", "tell", "ask", "use", "find", "put",
            "let", "keep", "begin", "seem", "help", "show", "hear", "play", "run",
            "move", "live", "believe", "hold", "bring", "happen", "write", "provide",
            "sit", "stand", "lose", "pay", "meet", "include", "continue", "set",
            "learn", "change", "lead", "understand", "watch", "follow", "stop",
            "create", "speak", "read", "spend", "grow", "open", "walk", "win",
            "offer", "remember", "love", "consider", "appear", "buy", "wait",
            "serve", "die", "send", "expect", "build", "stay", "fall", "cut",
            "reach", "kill", "remain", "suggest", "raise", "pass", "sell", "require",
            "report", "decide", "pull", "today", "something", "everything", "nothing",
            "anything", "someone", "everyone", "anyone", "thing", "things", "way",
            "ways", "time", "times", "day", "days", "year", "years", "people",
            "person", "lot", "lots", "kind", "kinds", "type", "types", "part",
            "parts", "place", "places", "point", "points", "case", "cases",
            "fact", "facts", "number", "numbers", "group", "groups", "problem",
            "problems", "question", "questions", "area", "areas", "company",
            "companies", "system", "systems", "program", "programs", "right",
        }
        
        # Tokenize and clean - single words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', transcript.lower())
        filtered_words = [w for w in words if w not in stop_words and len(w) >= 4]
        
        # Count word frequencies
        word_counts = Counter(filtered_words)
        
        # Extract important bigrams and trigrams (compound terms)
        key_phrases = self._extract_key_phrases(transcript, stop_words)
        
        # Get top keywords by frequency - prioritize longer, more specific words
        scored_keywords = []
        for word, count in word_counts.items():
            # Score based on frequency + word length bonus (longer words often more specific)
            score = count * (1 + len(word) * 0.1)
            scored_keywords.append((word, score, count))
        
        scored_keywords.sort(key=lambda x: x[1], reverse=True)
        top_keywords = [(w, c) for w, s, c in scored_keywords[:20]]
        
        # Calculate TF weights
        total_words = len(filtered_words) if filtered_words else 1
        keyword_weights = {
            word: count / total_words for word, count in top_keywords
        }
        
        # Try to get semantic keywords using LLM if available
        semantic_keywords = self._get_semantic_keywords(transcript)
        
        # Combine single keywords with key phrases for final list
        final_keywords = [word for word, _ in top_keywords[:10]]
        
        return {
            "keywords": final_keywords,
            "keyword_weights": keyword_weights,
            "semantic_keywords": semantic_keywords,
            "key_phrases": key_phrases[:10],
        }
    
    def _extract_key_phrases(self, transcript: str, stop_words: set) -> List[str]:
        """Extract important multi-word phrases from transcript."""
        if not transcript:
            return []
        
        # Clean and tokenize
        words = transcript.lower().split()
        cleaned_words = []
        for w in words:
            # Remove punctuation from word boundaries
            clean = re.sub(r'^[^a-z]+|[^a-z]+$', '', w)
            if clean:
                cleaned_words.append(clean)
        
        # Generate bigrams and trigrams
        bigrams = []
        trigrams = []
        
        for i in range(len(cleaned_words) - 1):
            w1, w2 = cleaned_words[i], cleaned_words[i + 1]
            # Only include if neither word is a stop word and both are long enough
            if w1 not in stop_words and w2 not in stop_words and len(w1) >= 3 and len(w2) >= 3:
                bigrams.append(f"{w1} {w2}")
        
        for i in range(len(cleaned_words) - 2):
            w1, w2, w3 = cleaned_words[i], cleaned_words[i + 1], cleaned_words[i + 2]
            # Allow middle word to be stop word (e.g., "point of sale")
            if w1 not in stop_words and w3 not in stop_words and len(w1) >= 3 and len(w3) >= 3:
                trigrams.append(f"{w1} {w2} {w3}")
        
        # Count phrase frequencies
        bigram_counts = Counter(bigrams)
        trigram_counts = Counter(trigrams)
        
        # Get phrases that appear multiple times (important concepts)
        important_phrases = []
        
        # Prioritize trigrams (more specific)
        for phrase, count in trigram_counts.most_common(20):
            if count >= 2:  # Must appear at least twice
                important_phrases.append((phrase, count * 1.5))  # Bonus for trigrams
        
        # Add bigrams
        for phrase, count in bigram_counts.most_common(30):
            if count >= 2:
                important_phrases.append((phrase, count))
        
        # Sort by score and return unique phrases
        important_phrases.sort(key=lambda x: x[1], reverse=True)
        seen = set()
        result = []
        for phrase, _ in important_phrases:
            if phrase not in seen:
                seen.add(phrase)
                result.append(phrase)
                if len(result) >= 15:
                    break
        
        return result
    
    def _get_semantic_keywords(self, transcript: str) -> List[str]:
        """Extract semantic keywords using LLM."""
        if not self.llm_client or not transcript:
            return []
        
        try:
            prompt = f"""Analyze this sales pitch and extract the 10 most critical domain-specific terms.

IMPORTANT: Return ONLY a comma-separated list. No explanations, no numbering, no other text.

Extract terms like:
- Product names (e.g., "data resilience platform")
- Technical concepts (e.g., "zero-trust architecture")
- Industry terminology (e.g., "cyber recovery")
- Solution features (e.g., "air-gapped backup")
- Business metrics (e.g., "recovery time objective")

Transcript:
{transcript[:4000]}

Keywords (comma-separated only):"""
            response = self.llm_client.generate(
                model=settings.ollama_model,
                prompt=prompt,
            )
            
            # Parse keywords from response
            keywords_text = response.get("response", "")
            
            # Clean up LLM response - remove preamble text
            # If response contains ":" it might have preamble, take text after the last colon
            if ":" in keywords_text and len(keywords_text) > 100:
                keywords_text = keywords_text.split(":")[-1]
            
            # Remove common preamble phrases
            preamble_phrases = [
                "here are", "the following", "keywords are", "key concepts",
                "extracted from", "sales pitch", "transcript", "important",
            ]
            
            keywords = [kw.strip().lower() for kw in keywords_text.split(",")]
            
            # Filter out entries that look like preamble or are too long (likely sentences)
            filtered_keywords = []
            for kw in keywords:
                # Skip if too long (likely a sentence fragment)
                if len(kw) > 30:
                    continue
                # Skip if contains preamble phrases
                if any(phrase in kw for phrase in preamble_phrases):
                    continue
                # Skip if too short
                if len(kw) < 3:
                    continue
                filtered_keywords.append(kw)
            
            # Limit to top 10 semantic keywords
            return filtered_keywords[:10]
            
        except Exception as e:
            logger.warning(f"Failed to extract semantic keywords: {e}")
            return []
    
    def _extract_voice_metrics(self, voice_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract voice metrics for comparison."""
        if not voice_analysis or voice_analysis.get("skipped"):
            return {}
        
        return {
            "avg_pitch": voice_analysis.get("avg_pitch"),
            "pitch_variance": voice_analysis.get("pitch_variance"),
            "speaking_rate_wpm": voice_analysis.get("speaking_rate_wpm"),
            "energy_score": voice_analysis.get("energy_score"),
            "confidence_score": voice_analysis.get("confidence_score"),
            "pace_score": voice_analysis.get("pace_score"),
            "tone_score": voice_analysis.get("tone_score"),
        }
    
    def _extract_pose_metrics(self, pose_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract pose metrics for comparison."""
        if not pose_analysis or pose_analysis.get("skipped"):
            return {}
        
        return {
            "posture_score": pose_analysis.get("posture_score"),
            "gesture_score": pose_analysis.get("gesture_score"),
            "movement_score": pose_analysis.get("movement_score"),
            "avg_shoulder_alignment": pose_analysis.get("avg_shoulder_alignment"),
            "gesture_frequency": pose_analysis.get("gesture_frequency"),
        }
    
    def _extract_facial_metrics(self, facial_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facial metrics for comparison."""
        if not facial_analysis or facial_analysis.get("skipped"):
            return {}
        
        return {
            "positivity_score": facial_analysis.get("positivity_score"),
            "engagement_score": facial_analysis.get("engagement_score"),
            "confidence_score": facial_analysis.get("confidence_score"),
            "eye_contact_percentage": facial_analysis.get("eye_contact_percentage"),
            "emotion_distribution": facial_analysis.get("emotion_distribution"),
        }
    
    def _extract_content_metrics(
        self, 
        content_analysis: Dict[str, Any],
        transcript: str
    ) -> Dict[str, Any]:
        """Extract content structure metrics for comparison."""
        if not content_analysis or content_analysis.get("skipped"):
            return {"word_count": len(transcript.split()) if transcript else 0}
        
        return {
            "clarity_score": content_analysis.get("clarity_score"),
            "persuasion_score": content_analysis.get("persuasion_score"),
            "structure_score": content_analysis.get("structure_score"),
            "key_points": content_analysis.get("key_points", []),
            "filler_word_count": content_analysis.get("filler_word_count", 0),
            "word_count": len(transcript.split()) if transcript else 0,
        }
    
    def compare_content(
        self,
        reference_data: Dict[str, Any],
        uploaded_transcript: str,
        uploaded_content_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare uploaded content against golden pitch deck content.
        
        Args:
            reference_data: Extracted reference data from golden pitch deck
            uploaded_transcript: Transcript of uploaded video/audio
            uploaded_content_analysis: Content analysis of uploaded video/audio
            
        Returns:
            Dict with comparison results
        """
        logger.info("Comparing content against golden pitch deck")
        
        if not reference_data or not uploaded_transcript:
            return self._empty_content_comparison()
        
        # Keyword comparison
        keyword_comparison = self._compare_keywords(
            reference_data.get("keywords", {}),
            uploaded_transcript,
        )
        
        # Semantic similarity (using sentence transformers or LLM)
        semantic_similarity = self._compute_semantic_similarity(
            reference_data.get("transcript", ""),
            uploaded_transcript,
        )
        
        # Structure comparison
        structure_comparison = self._compare_structure(
            reference_data.get("content_metrics", {}),
            uploaded_content_analysis or {},
        )
        
        # Key phrase coverage
        phrase_coverage = self._compare_key_phrases(
            reference_data.get("key_phrases", []),
            uploaded_transcript,
        )
        
        # Calculate overall content similarity score
        scores = [
            keyword_comparison.get("coverage_score", 0) * 0.3,
            semantic_similarity * 0.4,
            structure_comparison.get("similarity_score", 0) * 0.15,
            phrase_coverage.get("coverage_score", 0) * 0.15,
        ]
        overall_score = sum(scores)
        
        return {
            "overall_similarity_score": round(overall_score, 1),
            "keyword_comparison": keyword_comparison,
            "semantic_similarity": round(semantic_similarity, 1),
            "structure_comparison": structure_comparison,
            "phrase_coverage": phrase_coverage,
        }
    
    def _compare_keywords(
        self,
        reference_keywords: Dict[str, Any],
        uploaded_transcript: str,
    ) -> Dict[str, Any]:
        """Compare keyword coverage with support for phrases."""
        if not reference_keywords or not uploaded_transcript:
            return {
                "matched_keywords": [],
                "missing_keywords": [],
                "extra_keywords": [],
                "coverage_score": 0,
            }
        
        ref_keywords = set(reference_keywords.get("keywords", []))
        ref_semantic = set(reference_keywords.get("semantic_keywords", []))
        ref_phrases = set(reference_keywords.get("key_phrases", []))
        
        uploaded_lower = uploaded_transcript.lower()
        uploaded_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', uploaded_lower))
        
        matched = []
        missing = []
        
        # Check single keywords
        for kw in ref_keywords:
            if kw.lower() in uploaded_words:
                matched.append(kw)
            else:
                missing.append(kw)
        
        # Check semantic keywords (may be phrases - use substring matching)
        for kw in ref_semantic:
            kw_lower = kw.lower()
            # For phrases, check if the phrase exists in transcript
            if " " in kw_lower:
                if kw_lower in uploaded_lower:
                    matched.append(kw)
                else:
                    missing.append(kw)
            else:
                if kw_lower in uploaded_words:
                    matched.append(kw)
                else:
                    missing.append(kw)
        
        # Check key phrases (use substring matching)
        for phrase in ref_phrases:
            phrase_lower = phrase.lower()
            if phrase_lower in uploaded_lower:
                matched.append(phrase)
            else:
                missing.append(phrase)
        
        # Remove duplicates
        matched = list(dict.fromkeys(matched))
        missing = list(dict.fromkeys(missing))
        
        total_ref = len(ref_keywords) + len(ref_semantic) + len(ref_phrases)
        
        # Calculate coverage score
        if total_ref > 0:
            coverage_score = (len(matched) / total_ref) * 100
        else:
            coverage_score = 0
        
        return {
            "matched_keywords": matched[:30],
            "missing_keywords": missing[:30],
            "total_reference_keywords": total_ref,
            "matched_count": len(matched),
            "coverage_score": round(coverage_score, 1),
        }
    
    def _compute_semantic_similarity(
        self,
        reference_transcript: str,
        uploaded_transcript: str,
    ) -> float:
        """Compute semantic similarity between transcripts."""
        if not reference_transcript or not uploaded_transcript:
            logger.warning("Missing transcript for semantic similarity")
            return 0.0
        
        logger.info(f"Computing semantic similarity: ref={len(reference_transcript)} chars, uploaded={len(uploaded_transcript)} chars")
        
        # Try sentence transformer first
        if self.sentence_transformer:
            try:
                # Encode both transcripts
                embeddings = self.sentence_transformer.encode([
                    reference_transcript[:5000],  # Limit length
                    uploaded_transcript[:5000],
                ])
                
                # Cosine similarity
                from numpy import dot
                from numpy.linalg import norm
                
                similarity = dot(embeddings[0], embeddings[1]) / (
                    norm(embeddings[0]) * norm(embeddings[1])
                )
                
                logger.info(f"Raw cosine similarity: {similarity:.4f}")
                
                # Cosine similarity typically ranges from 0 to 1 for text embeddings
                # Convert to 0-100 scale (similarity already 0-1 for similar texts)
                score = max(0, min(100, similarity * 100))
                
                logger.info(f"Semantic similarity score: {score:.1f}")
                return score
                
            except Exception as e:
                logger.warning(f"Sentence transformer similarity failed: {e}")
        else:
            logger.info("Sentence transformer not available, using word overlap fallback")
        
        # Fallback to simple word overlap
        ref_words = set(reference_transcript.lower().split())
        up_words = set(uploaded_transcript.lower().split())
        
        if not ref_words or not up_words:
            return 0.0
        
        intersection = len(ref_words & up_words)
        union = len(ref_words | up_words)
        
        # Jaccard similarity scaled to 0-100
        score = (intersection / union) * 100 if union > 0 else 0.0
        logger.info(f"Jaccard word overlap similarity: {score:.1f}%")
        return score
    
    def _compare_structure(
        self,
        reference_metrics: Dict[str, Any],
        uploaded_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare content structure metrics."""
        if not reference_metrics or not uploaded_metrics:
            return {"similarity_score": 50}
        
        # Compare various metrics
        comparisons = []
        
        # Word count comparison (penalize if too different)
        ref_wc = reference_metrics.get("word_count", 0)
        up_wc = uploaded_metrics.get("word_count", 0)
        if ref_wc > 0:
            wc_ratio = min(up_wc, ref_wc) / max(up_wc, ref_wc) if max(up_wc, ref_wc) > 0 else 0
            comparisons.append(("word_count", wc_ratio * 100))
        
        # Clarity score comparison
        ref_clarity = reference_metrics.get("clarity_score", 0)
        up_clarity = uploaded_metrics.get("clarity_score", 0)
        if ref_clarity > 0:
            clarity_diff = 100 - abs(ref_clarity - up_clarity)
            comparisons.append(("clarity", clarity_diff))
        
        # Filler word comparison (less = better match to ideal)
        ref_filler = reference_metrics.get("filler_word_count", 0)
        up_filler = uploaded_metrics.get("filler_word_count", 0)
        filler_diff = 100 - min(100, abs(ref_filler - up_filler) * 5)
        comparisons.append(("filler_words", filler_diff))
        
        # Calculate average
        if comparisons:
            avg_score = sum(score for _, score in comparisons) / len(comparisons)
        else:
            avg_score = 50
        
        return {
            "similarity_score": round(avg_score, 1),
            "details": {name: round(score, 1) for name, score in comparisons},
        }
    
    def _compare_key_phrases(
        self,
        reference_phrases: List[str],
        uploaded_transcript: str,
    ) -> Dict[str, Any]:
        """Compare key phrase coverage."""
        if not reference_phrases or not uploaded_transcript:
            return {"coverage_score": 0, "covered_phrases": [], "missing_phrases": []}
        
        uploaded_lower = uploaded_transcript.lower()
        covered = []
        missing = []
        
        for phrase in reference_phrases:
            # Check if key words from phrase appear in uploaded
            phrase_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', phrase.lower()))
            if len(phrase_words) == 0:
                continue
            
            # Count how many key words appear
            matched_words = sum(1 for w in phrase_words if w in uploaded_lower)
            coverage_ratio = matched_words / len(phrase_words)
            
            if coverage_ratio >= 0.6:  # 60% of words match
                covered.append(phrase)
            else:
                missing.append(phrase)
        
        total = len(covered) + len(missing)
        coverage_score = (len(covered) / total * 100) if total > 0 else 0
        
        return {
            "coverage_score": round(coverage_score, 1),
            "covered_phrases": covered[:10],
            "missing_phrases": missing[:10],
        }
    
    def compare_voice(
        self,
        reference_metrics: Dict[str, Any],
        uploaded_voice_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare voice metrics against golden pitch deck.
        
        Args:
            reference_metrics: Voice metrics from golden pitch deck
            uploaded_voice_analysis: Voice analysis of uploaded video/audio
            
        Returns:
            Dict with voice comparison results
        """
        logger.info("Comparing voice metrics against golden pitch deck")
        
        if not reference_metrics or not uploaded_voice_analysis:
            return self._empty_voice_comparison()
        
        if uploaded_voice_analysis.get("skipped"):
            return self._empty_voice_comparison()
        
        comparisons = {}
        
        # Speaking rate comparison
        ref_wpm = reference_metrics.get("speaking_rate_wpm")
        up_wpm = uploaded_voice_analysis.get("speaking_rate_wpm")
        if ref_wpm and up_wpm:
            wpm_diff = abs(ref_wpm - up_wpm)
            wpm_similarity = max(0, 100 - wpm_diff * 2)  # 2% penalty per WPM difference
            comparisons["speaking_rate"] = {
                "reference": ref_wpm,
                "uploaded": up_wpm,
                "difference": round(up_wpm - ref_wpm, 1),
                "similarity": round(wpm_similarity, 1),
                "feedback": self._get_wpm_feedback(ref_wpm, up_wpm),
            }
        
        # Pitch comparison
        ref_pitch = reference_metrics.get("avg_pitch")
        up_pitch = uploaded_voice_analysis.get("avg_pitch")
        if ref_pitch and up_pitch:
            pitch_diff = abs(ref_pitch - up_pitch)
            pitch_similarity = max(0, 100 - pitch_diff * 0.5)
            comparisons["pitch"] = {
                "reference": round(ref_pitch, 1),
                "uploaded": round(up_pitch, 1),
                "similarity": round(pitch_similarity, 1),
            }
        
        # Energy score comparison
        ref_energy = reference_metrics.get("energy_score")
        up_energy = uploaded_voice_analysis.get("energy_score")
        if ref_energy is not None and up_energy is not None:
            energy_diff = abs(ref_energy - up_energy)
            energy_similarity = max(0, 100 - energy_diff)
            comparisons["energy"] = {
                "reference": ref_energy,
                "uploaded": up_energy,
                "similarity": round(energy_similarity, 1),
            }
        
        # Confidence score comparison
        ref_conf = reference_metrics.get("confidence_score")
        up_conf = uploaded_voice_analysis.get("confidence_score")
        if ref_conf is not None and up_conf is not None:
            conf_diff = abs(ref_conf - up_conf)
            conf_similarity = max(0, 100 - conf_diff)
            comparisons["confidence"] = {
                "reference": ref_conf,
                "uploaded": up_conf,
                "similarity": round(conf_similarity, 1),
            }
        
        # Calculate overall voice similarity
        if comparisons:
            similarities = [c.get("similarity", 50) for c in comparisons.values()]
            overall_score = sum(similarities) / len(similarities)
        else:
            overall_score = 50
        
        return {
            "overall_similarity_score": round(overall_score, 1),
            "comparisons": comparisons,
        }
    
    def _get_wpm_feedback(self, ref_wpm: float, up_wpm: float) -> str:
        """Generate feedback for speaking rate difference."""
        diff = up_wpm - ref_wpm
        if abs(diff) < 10:
            return "Speaking rate matches the reference well"
        elif diff > 20:
            return "Speaking faster than the reference - consider slowing down for clarity"
        elif diff > 10:
            return "Speaking slightly faster than the reference"
        elif diff < -20:
            return "Speaking slower than the reference - consider increasing pace for energy"
        else:
            return "Speaking slightly slower than the reference"
    
    def compare_pose(
        self,
        reference_metrics: Dict[str, Any],
        uploaded_pose_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare pose/gesture metrics against golden pitch deck.
        
        Args:
            reference_metrics: Pose metrics from golden pitch deck
            uploaded_pose_analysis: Pose analysis of uploaded video
            
        Returns:
            Dict with pose comparison results
        """
        logger.info("Comparing pose metrics against golden pitch deck")
        
        if not reference_metrics or not uploaded_pose_analysis:
            return self._empty_pose_comparison()
        
        if uploaded_pose_analysis.get("skipped"):
            return self._empty_pose_comparison()
        
        comparisons = {}
        
        # Posture score comparison
        ref_posture = reference_metrics.get("posture_score")
        up_posture = uploaded_pose_analysis.get("posture_score")
        if ref_posture is not None and up_posture is not None:
            posture_similarity = max(0, 100 - abs(ref_posture - up_posture))
            comparisons["posture"] = {
                "reference": ref_posture,
                "uploaded": up_posture,
                "similarity": round(posture_similarity, 1),
            }
        
        # Gesture score comparison
        ref_gesture = reference_metrics.get("gesture_score")
        up_gesture = uploaded_pose_analysis.get("gesture_score")
        if ref_gesture is not None and up_gesture is not None:
            gesture_similarity = max(0, 100 - abs(ref_gesture - up_gesture))
            comparisons["gesture"] = {
                "reference": ref_gesture,
                "uploaded": up_gesture,
                "similarity": round(gesture_similarity, 1),
            }
        
        # Movement score comparison
        ref_movement = reference_metrics.get("movement_score")
        up_movement = uploaded_pose_analysis.get("movement_score")
        if ref_movement is not None and up_movement is not None:
            movement_similarity = max(0, 100 - abs(ref_movement - up_movement))
            comparisons["movement"] = {
                "reference": ref_movement,
                "uploaded": up_movement,
                "similarity": round(movement_similarity, 1),
            }
        
        # Gesture frequency comparison
        ref_freq = reference_metrics.get("gesture_frequency")
        up_freq = uploaded_pose_analysis.get("gesture_frequency")
        if ref_freq is not None and up_freq is not None:
            freq_diff = abs(ref_freq - up_freq)
            freq_similarity = max(0, 100 - freq_diff * 10)
            comparisons["gesture_frequency"] = {
                "reference": round(ref_freq, 2),
                "uploaded": round(up_freq, 2),
                "similarity": round(freq_similarity, 1),
            }
        
        # Calculate overall pose similarity
        if comparisons:
            similarities = [c.get("similarity", 50) for c in comparisons.values()]
            overall_score = sum(similarities) / len(similarities)
        else:
            overall_score = 50
        
        return {
            "overall_similarity_score": round(overall_score, 1),
            "comparisons": comparisons,
        }
    
    def compare_facial(
        self,
        reference_metrics: Dict[str, Any],
        uploaded_facial_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare facial expression metrics against golden pitch deck.

        Args:
            reference_metrics: Facial metrics from golden pitch deck
            uploaded_facial_analysis: Facial analysis of uploaded video

        Returns:
            Dict with facial comparison results
        """
        logger.info("Comparing facial metrics against golden pitch deck")

        if not reference_metrics or not uploaded_facial_analysis:
            return self._empty_facial_comparison()

        if uploaded_facial_analysis.get("skipped"):
            return self._empty_facial_comparison()

        comparisons = {}

        # Positivity score comparison
        ref_pos = reference_metrics.get("positivity_score")
        up_pos = uploaded_facial_analysis.get("positivity_score")
        if ref_pos is not None and up_pos is not None:
            pos_similarity = max(0, 100 - abs(ref_pos - up_pos))
            comparisons["positivity"] = {
                "reference": ref_pos,
                "uploaded": up_pos,
                "similarity": round(pos_similarity, 1),
            }

        # Engagement score comparison
        ref_eng = reference_metrics.get("engagement_score")
        up_eng = uploaded_facial_analysis.get("engagement_score")
        if ref_eng is not None and up_eng is not None:
            eng_similarity = max(0, 100 - abs(ref_eng - up_eng))
            comparisons["engagement"] = {
                "reference": ref_eng,
                "uploaded": up_eng,
                "similarity": round(eng_similarity, 1),
            }

        # Confidence score comparison
        ref_conf = reference_metrics.get("confidence_score")
        up_conf = uploaded_facial_analysis.get("confidence_score")
        if ref_conf is not None and up_conf is not None:
            conf_similarity = max(0, 100 - abs(ref_conf - up_conf))
            comparisons["confidence"] = {
                "reference": ref_conf,
                "uploaded": up_conf,
                "similarity": round(conf_similarity, 1),
            }

        # Emotion distribution similarity (cosine similarity between distributions)
        ref_emotions = reference_metrics.get("emotion_distribution", {})
        up_emotions = uploaded_facial_analysis.get("emotion_distribution", {})
        if ref_emotions and up_emotions:
            all_emotions = set(ref_emotions.keys()) | set(up_emotions.keys())
            ref_vec = [ref_emotions.get(e, 0) for e in all_emotions]
            up_vec = [up_emotions.get(e, 0) for e in all_emotions]
            dot_product = sum(a * b for a, b in zip(ref_vec, up_vec))
            norm_ref = math.sqrt(sum(a * a for a in ref_vec)) or 1
            norm_up = math.sqrt(sum(a * a for a in up_vec)) or 1
            cosine_sim = dot_product / (norm_ref * norm_up)
            emotion_similarity = max(0, min(100, cosine_sim * 100))
            comparisons["emotion_distribution"] = {
                "similarity": round(emotion_similarity, 1),
            }

        # Calculate overall facial similarity
        if comparisons:
            similarities = [c.get("similarity", 50) for c in comparisons.values()]
            overall_score = sum(similarities) / len(similarities)
        else:
            overall_score = 50

        return {
            "overall_similarity_score": round(overall_score, 1),
            "comparisons": comparisons,
        }

    def _empty_facial_comparison(self) -> Dict[str, Any]:
        """Return empty facial comparison result."""
        return {
            "overall_similarity_score": 0,
            "comparisons": {},
        }

    def _empty_content_comparison(self) -> Dict[str, Any]:
        """Return empty content comparison result."""
        return {
            "overall_similarity_score": 0,
            "keyword_comparison": {
                "matched_keywords": [],
                "missing_keywords": [],
                "coverage_score": 0,
            },
            "semantic_similarity": 0,
            "structure_comparison": {"similarity_score": 0},
            "phrase_coverage": {"coverage_score": 0, "covered_phrases": [], "missing_phrases": []},
        }
    
    def _empty_voice_comparison(self) -> Dict[str, Any]:
        """Return empty voice comparison result."""
        return {
            "overall_similarity_score": 0,
            "comparisons": {},
        }
    
    def _empty_pose_comparison(self) -> Dict[str, Any]:
        """Return empty pose comparison result."""
        return {
            "overall_similarity_score": 0,
            "comparisons": {},
        }
    
    def generate_comparison_summary(
        self,
        content_comparison: Dict[str, Any],
        voice_comparison: Dict[str, Any],
        pose_comparison: Dict[str, Any],
        facial_comparison: Dict[str, Any] = None,
        golden_name: str = "golden pitch deck",
    ) -> Dict[str, Any]:
        """
        Generate an overall comparison summary.
        
        Args:
            content_comparison: Content comparison results
            voice_comparison: Voice comparison results
            pose_comparison: Pose comparison results
            facial_comparison: Facial comparison results
            golden_name: Name of the golden pitch deck for display
            
        Returns:
            Dict with summary and recommendations
        """
        # Calculate overall comparison score
        scores = []
        
        content_score = content_comparison.get("overall_similarity_score", 0)
        voice_score = voice_comparison.get("overall_similarity_score", 0)
        pose_score = pose_comparison.get("overall_similarity_score", 0)
        facial_score = (facial_comparison or {}).get("overall_similarity_score", 0)
        
        # Check which comparisons have actual data (non-empty comparisons dict)
        # When facial/pose are skipped (no person detected), exclude them
        category_weights = {}
        if content_comparison.get("comparisons") or content_comparison.get("keyword_comparison") or content_score > 0:
            category_weights["content"] = (0.4, content_score)
        if voice_comparison.get("comparisons") or voice_score > 0:
            category_weights["voice"] = (0.25, voice_score)
        pose_has_data = pose_comparison.get("comparisons") and len(pose_comparison["comparisons"]) > 0
        if pose_has_data or pose_score > 0:
            category_weights["pose"] = (0.15, pose_score)
        facial_has_data = (facial_comparison or {}).get("comparisons") and len((facial_comparison or {}).get("comparisons", {})) > 0
        if facial_has_data or facial_score > 0:
            category_weights["facial"] = (0.2, facial_score)
        
        # Renormalize weights for available categories only
        if category_weights:
            total_weight = sum(w for w, _ in category_weights.values())
            weighted_score = sum(
                (w / total_weight) * s for w, s in category_weights.values()
            )
        else:
            weighted_score = 0
        
        # Generate recommendations based on comparison
        recommendations = []
        
        # Content recommendations
        keyword_coverage = content_comparison.get("keyword_comparison", {}).get("coverage_score", 0)
        if keyword_coverage < 70:
            missing = content_comparison.get("keyword_comparison", {}).get("missing_keywords", [])
            if missing:
                recommendations.append({
                    "category": "content",
                    "priority": "high",
                    "title": "Cover more key topics",
                    "description": f"Your pitch is missing some key topics from the {golden_name}. Consider including: {', '.join(missing[:5])}",
                })
        
        semantic_sim = content_comparison.get("semantic_similarity", 0)
        if semantic_sim < 60:
            recommendations.append({
                "category": "content",
                "priority": "medium",
                "title": "Align content with reference",
                "description": f"Your content differs significantly from the {golden_name}. Review the reference structure and key messages.",
            })
        
        # Voice recommendations
        voice_comps = voice_comparison.get("comparisons", {})
        speaking_rate = voice_comps.get("speaking_rate", {})
        if speaking_rate.get("similarity", 100) < 70:
            recommendations.append({
                "category": "voice",
                "priority": "medium",
                "title": "Adjust speaking pace",
                "description": speaking_rate.get("feedback", "Match the speaking pace of the reference"),
            })
        
        energy = voice_comps.get("energy", {})
        if energy.get("similarity", 100) < 70:
            ref_energy = energy.get("reference", 0)
            up_energy = energy.get("uploaded", 0)
            if up_energy < ref_energy:
                recommendations.append({
                    "category": "voice",
                    "priority": "high",
                    "title": "Increase energy",
                    "description": "Your energy level is lower than the reference. Increase enthusiasm and vocal variety.",
                })
        
        # Pose recommendations
        pose_comps = pose_comparison.get("comparisons", {})
        posture = pose_comps.get("posture", {})
        if posture.get("similarity", 100) < 70:
            recommendations.append({
                "category": "pose",
                "priority": "medium",
                "title": "Improve posture",
                "description": "Your posture differs from the reference. Focus on standing/sitting straight with shoulders back.",
            })
        
        gesture = pose_comps.get("gesture", {})
        if gesture.get("similarity", 100) < 70:
            ref_gesture = gesture.get("reference", 0)
            up_gesture = gesture.get("uploaded", 0)
            if up_gesture < ref_gesture:
                recommendations.append({
                    "category": "pose",
                    "priority": "low",
                    "title": "Use more gestures",
                    "description": "Consider using more hand gestures to emphasize key points like in the reference.",
                })
        
        # Generate summary
        summary_parts = []
        
        if weighted_score >= 80:
            summary_parts.append(f"Excellent match with the {golden_name}!")
        elif weighted_score >= 60:
            summary_parts.append(f"Good alignment with the {golden_name}, with room for improvement.")
        elif weighted_score >= 40:
            summary_parts.append(f"Moderate similarity to the {golden_name}. Focus on the recommendations below.")
        else:
            summary_parts.append(f"Significant differences from the {golden_name}. Review the reference and practice.")
        
        summary_parts.append(f"Content similarity: {content_score:.0f}%")
        summary_parts.append(f"Voice similarity: {voice_score:.0f}%")
        summary_parts.append(f"Facial similarity: {facial_score:.0f}%")
        summary_parts.append(f"Pose/gesture similarity: {pose_score:.0f}%")
        
        return {
            "overall_comparison_score": round(weighted_score, 1),
            "content_similarity_score": round(content_score, 1),
            "voice_similarity_score": round(voice_score, 1),
            "pose_similarity_score": round(pose_score, 1),
            "facial_similarity_score": round(facial_score, 1),
            "summary": " ".join(summary_parts),
            "recommendations": recommendations,
        }

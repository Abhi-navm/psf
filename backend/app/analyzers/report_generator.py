"""
Report generator that aggregates all analysis results.
"""

from typing import Dict, Any, List

from app.core.logging import logger


class ReportGenerator:
    """Generate comprehensive analysis reports."""
    
    # Score weights for overall calculation
    CATEGORY_WEIGHTS = {
        "voice": 0.25,
        "facial": 0.20,
        "pose": 0.20,
        "content": 0.35,
    }
    
    # Score thresholds
    EXCELLENT_THRESHOLD = 85
    GOOD_THRESHOLD = 70
    NEEDS_WORK_THRESHOLD = 50
    
    def generate(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive report from all analysis results.
        
        Args:
            analysis_results: Dict containing voice, facial, pose, content, and comparison results
            
        Returns:
            Dict with the complete report
        """
        logger.info("Generating analysis report")
        
        voice = analysis_results.get("voice", {})
        facial = analysis_results.get("facial", {})
        pose = analysis_results.get("pose", {})
        content = analysis_results.get("content", {})
        has_audio = analysis_results.get("has_audio", True)
        comparison = analysis_results.get("comparison")
        golden_pitch_deck_id = analysis_results.get("golden_pitch_deck_id")
        
        # Check which analyses were skipped
        voice_skipped = voice.get("skipped", False)
        content_skipped = content.get("skipped", False)
        facial_skipped = facial.get("skipped", False)
        pose_skipped = pose.get("skipped", False)
        
        # Extract scores (use None for skipped analyses)
        voice_score = None if voice_skipped else voice.get("overall_score", 50)
        facial_score = None if facial_skipped else facial.get("overall_score", 50)
        pose_score = None if pose_skipped else pose.get("overall_score", 50)
        content_score = None if content_skipped else content.get("overall_score", 50)
        
        # Calculate overall score from available (non-skipped) analyses only
        available_scores = {}
        if not voice_skipped and voice_score is not None:
            available_scores["voice"] = voice_score
        if not facial_skipped and facial_score is not None:
            available_scores["facial"] = facial_score
        if not pose_skipped and pose_score is not None:
            available_scores["pose"] = pose_score
        if not content_skipped and content_score is not None:
            available_scores["content"] = content_score
        
        if available_scores:
            total_weight = sum(self.CATEGORY_WEIGHTS[k] for k in available_scores)
            overall_score = sum(
                score * (self.CATEGORY_WEIGHTS[k] / total_weight)
                for k, score in available_scores.items()
            )
        else:
            overall_score = 0
        
        voice_score_display = voice_score or 0.0
        facial_score_display = facial_score or 0.0
        pose_score_display = pose_score or 0.0
        content_score_display = content_score or 0.0
        
        # Identify strengths
        strengths = self._identify_strengths(
            voice_score or 0, facial_score_display, pose_score_display, content_score or 0,
            voice, facial, pose, content,
            voice_skipped, content_skipped, facial_skipped, pose_skipped
        )
        
        # Identify improvements
        improvements = self._identify_improvements(
            voice_score or 0, facial_score_display, pose_score_display, content_score or 0,
            voice, facial, pose, content,
            voice_skipped, content_skipped, facial_skipped, pose_skipped
        )
        
        # Compile timestamped issues
        timestamped_issues = self._compile_timestamped_issues(
            voice, facial, pose, content
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            overall_score, voice, facial, pose, content,
            has_audio
        )
        
        # Add comparison-specific recommendations if comparison was done
        if comparison and comparison.get("summary"):
            comparison_recs = comparison["summary"].get("recommendations", [])
            recommendations.extend(comparison_recs)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            overall_score, voice_score_display, facial_score_display, pose_score_display, content_score_display,
            strengths, improvements,
            has_audio,
            comparison=comparison,
        )
        
        # Build response with comparison data
        result = {
            "overall_score": round(overall_score, 1),
            "voice_score": round(voice_score_display, 1),
            "facial_score": round(facial_score_display, 1),
            "pose_score": round(pose_score_display, 1),
            "content_score": round(content_score_display, 1),
            "executive_summary": executive_summary,
            "strengths": strengths,
            "improvements": improvements,
            "timestamped_issues": timestamped_issues,
            "recommendations": recommendations,
            "has_audio": has_audio,
        }
        
        # Add comparison data if available
        if comparison:
            summary = comparison.get("summary", {})
            result["golden_pitch_deck_id"] = golden_pitch_deck_id
            result["comparison_overall_score"] = summary.get("overall_comparison_score")
            result["content_similarity_score"] = summary.get("content_similarity_score")
            result["keyword_coverage_score"] = comparison.get("content_comparison", {}).get(
                "keyword_comparison", {}
            ).get("coverage_score")
            result["voice_similarity_score"] = summary.get("voice_similarity_score")
            result["pose_similarity_score"] = summary.get("pose_similarity_score")
            result["facial_similarity_score"] = summary.get("facial_similarity_score")
            result["keyword_comparison"] = comparison.get("content_comparison", {}).get("keyword_comparison")
            result["content_comparison"] = comparison.get("content_comparison")
            result["pose_comparison"] = comparison.get("pose_comparison")
            result["voice_comparison"] = comparison.get("voice_comparison")
            result["facial_comparison"] = comparison.get("facial_comparison")
        
        return result
    
    def _identify_strengths(
        self,
        voice_score: float,
        facial_score: float,
        pose_score: float,
        content_score: float,
        voice: Dict,
        facial: Dict,
        pose: Dict,
        content: Dict,
        voice_skipped: bool = False,
        content_skipped: bool = False,
        facial_skipped: bool = False,
        pose_skipped: bool = False,
    ) -> List[str]:
        """Identify strengths from the analysis."""
        strengths = []
        
        # Voice strengths (only if not skipped)
        if not voice_skipped and voice_score >= self.GOOD_THRESHOLD:
            if voice.get("pace_score", 0) >= 80:
                strengths.append("Excellent speaking pace - clear and easy to follow")
            if voice.get("energy_score", 0) >= 80:
                strengths.append("Strong vocal energy and projection")
            if not voice.get("issues") or len(voice.get("issues", [])) == 0:
                strengths.append("Clear and confident voice delivery")
        
        # Facial strengths (only if not skipped)
        if not facial_skipped and facial_score >= self.GOOD_THRESHOLD:
            if facial.get("positivity_score", 0) >= 80:
                strengths.append("Positive and engaging facial expressions")
            if facial.get("eye_contact_percentage", 0) >= 80:
                strengths.append("Excellent eye contact maintained throughout")
            if facial.get("engagement_score", 0) >= 80:
                strengths.append("Expressive and engaging demeanor")
        
        # Pose strengths (only if not skipped)
        if not pose_skipped and pose_score >= self.GOOD_THRESHOLD:
            if pose.get("posture_score", 0) >= 80:
                strengths.append("Professional and confident posture")
            if pose.get("gesture_score", 0) >= 80:
                strengths.append("Effective use of hand gestures")
            if pose.get("movement_score", 0) >= 85:
                strengths.append("Composed body language without nervous movements")
        
        # Content strengths (only if not skipped)
        if not content_skipped and content_score >= self.GOOD_THRESHOLD:
            if content.get("filler_word_count", 100) < 5:
                strengths.append("Minimal use of filler words - articulate speech")
            if content.get("clarity_score", 0) >= 85:
                strengths.append("Clear and well-articulated message")
            if content.get("persuasion_score", 0) >= 80:
                strengths.append("Strong persuasive language")
        
        # If no specific strengths, add generic ones for high scores
        if not strengths and (voice_score + facial_score + pose_score + content_score) / 4 >= 70:
            strengths.append("Solid overall presentation skills")
        
        return strengths[:5]  # Top 5 strengths
    
    def _identify_improvements(
        self,
        voice_score: float,
        facial_score: float,
        pose_score: float,
        content_score: float,
        voice: Dict,
        facial: Dict,
        pose: Dict,
        content: Dict,
        voice_skipped: bool = False,
        content_skipped: bool = False,
        facial_skipped: bool = False,
        pose_skipped: bool = False,
    ) -> List[Dict[str, Any]]:
        """Identify areas for improvement."""
        improvements = []
        
        # Voice improvements (only if not skipped)
        if not voice_skipped and voice_score < self.GOOD_THRESHOLD:
            for issue in voice.get("issues", [])[:2]:
                improvements.append({
                    "area": "Voice",
                    "description": issue.get("description", "Voice delivery needs work"),
                    "suggestion": issue.get("suggestion", "Practice voice projection"),
                    "priority": self._get_priority(voice_score),
                })
        
        # Facial improvements (only if not skipped)
        if not facial_skipped and facial_score < self.GOOD_THRESHOLD:
            for issue in facial.get("issues", [])[:2]:
                improvements.append({
                    "area": "Facial Expression",
                    "description": issue.get("description", "Facial expressions need work"),
                    "suggestion": issue.get("suggestion", "Practice smiling and engaging expressions"),
                    "priority": self._get_priority(facial_score),
                })
        
        # Pose improvements (only if not skipped)
        if not pose_skipped and pose_score < self.GOOD_THRESHOLD:
            for issue in pose.get("issues", [])[:2]:
                improvements.append({
                    "area": "Body Language",
                    "description": issue.get("description", "Body language needs work"),
                    "suggestion": issue.get("suggestion", "Practice open and confident posture"),
                    "priority": self._get_priority(pose_score),
                })
        
        # Content improvements (only if not skipped)
        if not content_skipped and content_score < self.GOOD_THRESHOLD:
            filler_count = content.get("filler_word_count", 0)
            if filler_count > 10:
                improvements.append({
                    "area": "Speech Content",
                    "description": f"Used {filler_count} filler words (um, uh, like, etc.)",
                    "suggestion": "Practice pausing instead of using filler words",
                    "priority": "high" if filler_count > 20 else "medium",
                })
            
            weak_phrases = content.get("weak_phrases", [])
            if len(weak_phrases) > 3:
                improvements.append({
                    "area": "Speech Content",
                    "description": "Multiple weak phrases that reduce persuasiveness",
                    "suggestion": "Replace hedging language with confident statements",
                    "priority": "medium",
                })
        
        # Add improvement suggestions for any score below near-perfect (95%)
        # Even "good" scores (70-85%) can benefit from refinement tips
        REFINEMENT_THRESHOLD = 95
        
        # Detailed voice improvement tips
        voice_tips_low = [
            "Practice the 'Rule of Three' — vary your pitch, pace, and volume every 30 seconds",
            "Record yourself and listen back to identify monotone sections",
            "Use strategic 2-3 second pauses before key points to build anticipation",
            "Warm up your voice before presenting with humming exercises",
        ]
        voice_tips_good = [
            "Add vocal emphasis on power words like 'transform', 'accelerate', 'guarantee'",
            "Practice the 'pyramid technique' — start low energy, build to key points, then pause",
            "Use downward inflection at the end of statements to sound more confident",
        ]
        
        # Detailed facial expression tips
        facial_tips_low = [
            "Practice 'mirror exercises' — rehearse your pitch while watching your expressions",
            "Smile genuinely when discussing benefits and solutions",
            "Raise eyebrows slightly when making important points to show emphasis",
            "Maintain eye contact with the camera as if speaking to a friend",
        ]
        facial_tips_good = [
            "Match expressions to content — look concerned when discussing problems, excited for solutions",
            "Practice 'micro-expressions' — subtle nods and raised eyebrows to show engagement",
            "Record and review — identify moments where your face doesn't match your message",
        ]
        
        # Detailed body language tips
        pose_tips_low = [
            "Stand with feet shoulder-width apart in a 'power stance' for confidence",
            "Keep shoulders back and chest open — avoid crossing arms or hunching",
            "Use purposeful hand gestures within your 'gesture box' (chest to waist level)",
            "Avoid fidgeting, swaying, or touching your face during the presentation",
        ]
        pose_tips_good = [
            "Use the 'steeple' hand gesture when making authoritative points",
            "Add 'open palm' gestures when presenting options or welcoming ideas",
            "Practice 'stillness' during key moments — stop moving to emphasize important points",
        ]
        
        # Detailed content tips
        content_tips_low = [
            "Structure with the AIDA framework: Attention, Interest, Desire, Action",
            "Lead with the customer's problem, not your product features",
            "Replace filler words (um, uh, like) with confident pauses",
            "Add specific numbers, percentages, or case studies for credibility",
            "End with a clear, single call-to-action",
        ]
        content_tips_good = [
            "Tighten your opening hook — you have 10 seconds to capture attention",
            "Add a 'before/after' comparison to make benefits tangible",
            "Use the 'feel, felt, found' technique to handle objections",
            "Close with urgency — give a reason to act now",
        ]
        
        if not voice_skipped and voice_score is not None and voice_score < REFINEMENT_THRESHOLD and not any(i["area"] == "Voice" for i in improvements):
            if voice_score < self.GOOD_THRESHOLD:
                tips = voice_tips_low
                desc = f"Voice delivery score is {voice_score:.0f}% — needs improvement"
                priority = self._get_priority(voice_score)
            elif voice_score < self.EXCELLENT_THRESHOLD:
                tips = voice_tips_good
                desc = f"Voice delivery score is {voice_score:.0f}% — good, but can be refined"
                priority = "low"
            else:
                tips = voice_tips_good[:1]
                desc = f"Voice delivery score is {voice_score:.0f}% — nearly perfect"
                priority = "low"
            
            improvements.append({
                "area": "Voice",
                "description": desc,
                "suggestion": " | ".join(tips),
                "tips": tips,
                "priority": priority,
            })
        
        if not facial_skipped and facial_score < REFINEMENT_THRESHOLD and not any(i["area"] == "Facial Expression" for i in improvements):
            if facial_score < self.GOOD_THRESHOLD:
                tips = facial_tips_low
                desc = f"Facial expression score is {facial_score:.0f}% — needs more engagement"
                priority = self._get_priority(facial_score)
            elif facial_score < self.EXCELLENT_THRESHOLD:
                tips = facial_tips_good
                desc = f"Facial expression score is {facial_score:.0f}% — good, room to polish"
                priority = "low"
            else:
                tips = facial_tips_good[:1]
                desc = f"Facial expression score is {facial_score:.0f}% — nearly perfect"
                priority = "low"
            
            improvements.append({
                "area": "Facial Expression",
                "description": desc,
                "suggestion": " | ".join(tips),
                "tips": tips,
                "priority": priority,
            })
        
        if not pose_skipped and pose_score < REFINEMENT_THRESHOLD and not any(i["area"] == "Body Language" for i in improvements):
            if pose_score < self.GOOD_THRESHOLD:
                tips = pose_tips_low
                desc = f"Body language score is {pose_score:.0f}% — posture needs work"
                priority = self._get_priority(pose_score)
            elif pose_score < self.EXCELLENT_THRESHOLD:
                tips = pose_tips_good
                desc = f"Body language score is {pose_score:.0f}% — good, can be more dynamic"
                priority = "low"
            else:
                tips = pose_tips_good[:1]
                desc = f"Body language score is {pose_score:.0f}% — nearly perfect"
                priority = "low"
            
            improvements.append({
                "area": "Body Language",
                "description": desc,
                "suggestion": " | ".join(tips),
                "tips": tips,
                "priority": priority,
            })
        
        if content_skipped:
            improvements.append({
                "area": "Content Analysis",
                "description": "Content analysis could not be completed (Ollama/LLM not available)",
                "suggestion": "Ensure Ollama is running with 'ollama serve' and model is pulled with 'ollama pull llama3'",
                "tips": ["Run 'ollama serve' in a terminal", "Pull the model with 'ollama pull llama3'", "Restart the analysis"],
                "priority": "medium",
            })
        elif not content_skipped and content_score is not None and content_score < REFINEMENT_THRESHOLD and not any(i["area"] == "Speech Content" for i in improvements):
            if content_score < self.GOOD_THRESHOLD:
                tips = content_tips_low
                desc = f"Content score is {content_score:.0f}% — message could be stronger"
                priority = self._get_priority(content_score)
            else:
                tips = content_tips_good
                desc = f"Content score is {content_score:.0f}% — refine your messaging"
                priority = "low"
            
            improvements.append({
                "area": "Speech Content",
                "description": desc,
                "suggestion": " | ".join(tips),
                "tips": tips,
                "priority": priority,
            })
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        improvements.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return improvements[:6]  # Top 6 improvements
    
    def _get_priority(self, score: float) -> str:
        """Get priority based on score."""
        if score < self.NEEDS_WORK_THRESHOLD:
            return "high"
        elif score < self.GOOD_THRESHOLD:
            return "medium"
        return "low"
    
    def _compile_timestamped_issues(
        self,
        voice: Dict,
        facial: Dict,
        pose: Dict,
        content: Dict,
    ) -> List[Dict[str, Any]]:
        """Compile all issues with timestamps."""
        issues = []
        
        # Voice issues
        for issue in voice.get("issues", []):
            issues.append({
                "timestamp": issue.get("timestamp"),
                "category": "voice",
                "issue": issue.get("type", "voice_issue"),
                "description": issue.get("description"),
                "severity": issue.get("severity", "medium"),
                "suggestion": issue.get("suggestion"),
            })
        
        # Facial issues
        for issue in facial.get("issues", []):
            for ts in issue.get("timestamps", [None])[:10]:
                issues.append({
                    "timestamp": ts,
                    "category": "facial",
                    "issue": issue.get("type", "facial_issue"),
                    "description": issue.get("description"),
                    "severity": issue.get("severity", "medium"),
                    "suggestion": issue.get("suggestion"),
                })
        
        # Pose issues
        for issue in pose.get("issues", []):
            for ts in issue.get("timestamps", [None])[:10]:
                issues.append({
                    "timestamp": ts,
                    "category": "pose",
                    "issue": issue.get("type", "pose_issue"),
                    "description": issue.get("description"),
                    "severity": issue.get("severity", "medium"),
                    "suggestion": issue.get("suggestion"),
                })
        
        # Content issues (filler words, weak phrases)
        for filler in content.get("filler_words", [])[:10]:
            for ts in filler.get("timestamps", [])[:5]:
                issues.append({
                    "timestamp": ts,
                    "category": "content",
                    "issue": "filler_word",
                    "description": f"Filler word '{filler['word']}' detected",
                    "severity": "low",
                    "suggestion": "Pause instead of using filler words",
                })
        
        for phrase in content.get("weak_phrases", [])[:5]:
            issues.append({
                "timestamp": phrase.get("timestamp"),
                "category": "content",
                "issue": "weak_phrase",
                "description": f"Weak phrase: '{phrase['phrase']}'",
                "severity": "medium",
                "suggestion": phrase.get("suggestion"),
            })
        
        # Sort by timestamp
        issues.sort(key=lambda x: x.get("timestamp") or 0)
        
        return issues
    
    def _generate_recommendations(
        self,
        overall_score: float,
        voice: Dict,
        facial: Dict,
        pose: Dict,
        content: Dict,
        has_audio: bool = True,
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Practice recommendations based on lowest scores
        # Skip voice and content if no audio
        scores = []
        if has_audio and not voice.get("skipped"):
            scores.append(("voice", voice.get("overall_score", 50)))
        if not facial.get("skipped"):
            scores.append(("facial", facial.get("overall_score", 50)))
        if not pose.get("skipped"):
            scores.append(("pose", pose.get("overall_score", 50)))
        if has_audio and not content.get("skipped"):
            scores.append(("content", content.get("overall_score", 50)))
        
        scores.sort(key=lambda x: x[1])
        
        # Recommendations for lowest scoring areas
        recommendation_templates = {
            "voice": {
                "title": "Voice Training",
                "description": "Practice vocal exercises to improve projection and variation",
                "exercises": [
                    "Record yourself and listen for monotone patterns",
                    "Practice breathing exercises before presenting",
                    "Use a metronome to maintain consistent pace",
                ],
            },
            "facial": {
                "title": "Expression Practice",
                "description": "Work on facial expressions to appear more engaging",
                "exercises": [
                    "Practice in front of a mirror",
                    "Record video selfies while presenting",
                    "Focus on natural smiling during key points",
                ],
            },
            "pose": {
                "title": "Body Language Training",
                "description": "Improve posture and reduce nervous movements",
                "exercises": [
                    "Practice power poses before presenting",
                    "Record full-body video to identify habits",
                    "Use hand gestures intentionally to emphasize points",
                ],
            },
            "content": {
                "title": "Speech Content Refinement",
                "description": "Eliminate filler words and strengthen language",
                "exercises": [
                    "Write out key points and practice transitions",
                    "Replace 'I think' with confident statements",
                    "Practice pausing instead of using filler words",
                ],
            },
        }
        
        # Add recommendations for 2 lowest scoring areas
        for category, score in scores[:2]:
            if score < self.GOOD_THRESHOLD:
                template = recommendation_templates.get(category, {})
                recommendations.append({
                    "category": category,
                    "title": template.get("title", f"Improve {category}"),
                    "description": template.get("description", ""),
                    "exercises": template.get("exercises", []),
                    "priority": self._get_priority(score),
                })
        
        # General recommendation based on overall score
        if overall_score < self.NEEDS_WORK_THRESHOLD:
            recommendations.append({
                "category": "general",
                "title": "Comprehensive Practice",
                "description": "Consider working with a presentation coach",
                "exercises": [
                    "Practice your full presentation 10+ times",
                    "Get feedback from colleagues",
                    "Record and review each practice session",
                ],
                "priority": "high",
            })
        elif overall_score < self.GOOD_THRESHOLD:
            recommendations.append({
                "category": "general",
                "title": "Targeted Improvement",
                "description": "Focus on specific areas for maximum impact",
                "exercises": [
                    "Identify your top 3 issues and address them",
                    "Practice with the timestamps noted in this report",
                    "Re-record and compare improvement",
                ],
                "priority": "medium",
            })
        
        return recommendations
    
    def _generate_executive_summary(
        self,
        overall_score: float,
        voice_score: float,
        facial_score: float,
        pose_score: float,
        content_score: float,
        strengths: List[str],
        improvements: List[Dict],
        has_audio: bool = True,
        comparison: Dict = None,
    ) -> str:
        """Generate an executive summary of the analysis."""
        
        # Overall assessment
        if overall_score >= self.EXCELLENT_THRESHOLD:
            assessment = "Excellent sales pitch with strong delivery across all areas."
        elif overall_score >= self.GOOD_THRESHOLD:
            assessment = "Good sales pitch with room for improvement in specific areas."
        elif overall_score >= self.NEEDS_WORK_THRESHOLD:
            assessment = "Average presentation that needs focused practice to improve."
        else:
            assessment = "This presentation needs significant work before client-facing delivery."
        
        # Add note if no audio
        if not has_audio:
            assessment += " Note: Video had no audio track - analysis is based on visual elements only."
        
        # Build summary
        summary_parts = [assessment]
        
        # Add comparison summary if available
        if comparison and comparison.get("summary"):
            comp_summary = comparison["summary"]
            comp_score = comp_summary.get("overall_comparison_score", 0)
            
            if comp_score >= 80:
                summary_parts.append(f"Your pitch closely matches the golden reference (similarity: {comp_score:.0f}%).")
            elif comp_score >= 60:
                summary_parts.append(f"Your pitch shows good alignment with the golden reference (similarity: {comp_score:.0f}%).")
            elif comp_score >= 40:
                summary_parts.append(f"Your pitch differs moderately from the golden reference (similarity: {comp_score:.0f}%).")
            else:
                summary_parts.append(f"Your pitch differs significantly from the golden reference (similarity: {comp_score:.0f}%).")
        
        # Highlight strongest area (only include areas that were actually analyzed)
        scores = {}
        if facial_score and facial_score > 0:
            scores["facial expressions"] = facial_score
        if pose_score and pose_score > 0:
            scores["body language"] = pose_score
        if has_audio and voice_score > 0:
            scores["voice delivery"] = voice_score
        if has_audio and content_score > 0:
            scores["speech content"] = content_score
        
        if scores:
            best_area = max(scores, key=scores.get)
            worst_area = min(scores, key=scores.get)
            
            if scores[best_area] >= self.GOOD_THRESHOLD:
                summary_parts.append(f"Your {best_area} is a strength (score: {scores[best_area]:.0f}/100).")
            
            if scores[worst_area] < self.GOOD_THRESHOLD:
                summary_parts.append(f"Focus improvement on {worst_area} (score: {scores[worst_area]:.0f}/100).")
        
        # Add top strength and improvement
        if strengths:
            summary_parts.append(f"Key strength: {strengths[0]}")
        
        if improvements:
            top_improvement = improvements[0]
            summary_parts.append(
                f"Top priority: {top_improvement['description']}"
            )
        
        return " ".join(summary_parts)

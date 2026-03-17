# PSF Frontend — Field Mapping Fixes Required

**Date:** March 17, 2026  
**From:** Pitch Analyzer Team  
**To:** PSF Backend/Frontend Team  

---

## Issues to Fix

### 1. "Confidence & Delivery" — Wrong mapping
- **Current behavior:** Shows 3.8 (mapped from `facial_analysis.confidence_score` = 89.8)
- **Should map to:** `voice_analysis.confidence_score` (0–100 scale, divide by 20 for 5-point scale)
- **Reason:** "Confidence & Delivery" is about vocal confidence, not facial confidence

### 2. "Visual & Slide Effectiveness" — No metric available
- **Current behavior:** Maps to `facial_analysis.overall_score`, which is facial expression quality — not slide/visual analysis
- **Problem:** We do **not** analyze slides or visual content. This metric does not exist in our pipeline.
- **Options:**
  - **Remove** this field from the UI entirely
  - **Rename** to "Facial Expression" or "Non-Verbal Communication" if you want to keep using `facial_analysis.overall_score`
  - **Map** to `content_analysis.structure_score` (0–100) as a proxy for presentation structure

### 3. "Executive Tone" in Pitch Analysis Radar — Verify mapping
- **Should map to:** `voice_analysis.tone_score` (0–100, divide by 20 for 5-point scale)
- **Our value:** 50 → should show 2.5 on 5-point scale

### 4. "Confidence" in Pitch Analysis Radar — Wrong mapping
- **Current behavior:** Shows 3.8 (same as facial confidence)
- **Should map to:** `voice_analysis.confidence_score` (0–100, divide by 20 for 5-point scale)
- **Our value:** 20 → should show 1.0 on 5-point scale

### 5. Handle `skipped` flag on facial & pose analyses
- **When:** `facial_analysis.skipped == true` or `pose_analysis.skipped == true`
- **Current behavior:** Shows 0.0 scores, which looks broken to the user
- **Should:** Display "N/A — No person detected" or hide those sections entirely
- **Affected fields:** Visual & Slide Effectiveness, Confidence & Delivery (if mapped to facial), Gesture Analysis, any pose/facial related UI elements
- **When this happens:** Videos that are screen recordings, slide presentations, or any video without a visible person

### 6. "Adherence to Standard" — Verify mapping
- **Should map to:** `report.comparison_overall_score`
- **Note:** This field is only populated when a golden pitch deck or skillset comparison is performed. If no comparison was done, it will be `null`.

### 7. "Confidence Index" in Overall Summary — Clarify source
- **Currently shows:** 76% (doesn't match any single field we provide)
- **Our data:** `voice_analysis.confidence_score` = 20, `facial_analysis.confidence_score` = 89.8
- **Action:** Clarify what this is meant to represent and map accordingly

---

## Correct Field Mapping Table

### Overall Summary Section

| PSF UI Field | Our API Field | Scale | Notes |
|---|---|---|---|
| Overall Summary score | `report.overall_score` | 0–100 | Main score |
| Confidence Index | `voice_analysis.confidence_score` | 0–100 (%) | Vocal confidence |
| Adherence to Standard | `report.comparison_overall_score` | 0–100 (%) | Only present with comparison |
| Vocal Delivery | `report.voice_score` | 0–100 (%) | Overall voice quality |

### Performance Against Skillset Section (5-point scale = value ÷ 20)

| PSF UI Field | Our API Field | Raw Scale | 5-Point |
|---|---|---|---|
| Confidence & Delivery | `voice_analysis.confidence_score` | 0–100 | ÷ 20 |
| Visual & Slide Effectiveness | **REMOVE** or `content_analysis.structure_score` | 0–100 | ÷ 20 |
| Persuasiveness & Call-to-Action | `content_analysis.persuasion_score` | 0–100 | ÷ 20 |
| Clarity of Message | `content_analysis.clarity_score` | 0–100 | ÷ 20 |

### Pitch Analysis Radar (5-point scale = value ÷ 20)

| Radar Axis | Our API Field | Raw Scale | 5-Point |
|---|---|---|---|
| Confidence | `voice_analysis.confidence_score` | 0–100 | ÷ 20 |
| Clarity | `content_analysis.clarity_score` | 0–100 | ÷ 20 |
| Pace Control | `voice_analysis.pace_score` | 0–100 | ÷ 20 |
| Executive Tone | `voice_analysis.tone_score` | 0–100 | ÷ 20 |
| Energy | `voice_analysis.energy_score` | 0–100 | ÷ 20 |

### Critical Variance Analysis & Recommendations

| PSF UI Field | Our API Field | Type |
|---|---|---|
| Winning Moments | `report.strengths` | `string[]` |
| The Gap | `report.improvements` | `[{area, description, priority, suggestion}]` |
| Recommended AI Corrections | `report.recommendations` | `[{title, category, priority, description, exercises}]` |
| Gesture Analysis / Key Issues | `report.timestamped_issues` | `[{timestamp, category, issue, description, severity, suggestion}]` |

---

## Complete List of Fields We Provide

### API Endpoint
```
GET /api/v1/analyses/{analysis_id}
```

### `voice_analysis` (all scores 0–100)
| Field | Type | Description |
|---|---|---|
| `overall_score` | float | Overall voice quality |
| `energy_score` | float | Vocal energy / projection |
| `clarity_score` | float | Speech clarity |
| `pace_score` | float | Speaking pace quality |
| `confidence_score` | float | Vocal confidence |
| `tone_score` | float | Executive tone quality |
| `avg_pitch` | float | Average pitch (Hz) |
| `pitch_variance` | float | Pitch variation |
| `speaking_rate_wpm` | float | Words per minute |
| `pause_frequency` | float | Frequency of pauses |
| `emotion_timeline` | array | `[{timestamp, emotion, confidence, emotions}]` |
| `issues` | array | `[{type, description, severity, suggestion}]` |

### `facial_analysis` (all scores 0–100)
| Field | Type | Description |
|---|---|---|
| `overall_score` | float | Overall facial expression quality |
| `positivity_score` | float | Positive expressions |
| `engagement_score` | float | Facial engagement |
| `confidence_score` | float | Facial confidence |
| `eye_contact_percentage` | float | % of time with eye contact |
| `emotion_distribution` | object | `{happy: 0.3, neutral: 0.5, ...}` |
| `emotion_timeline` | array | `[{timestamp, dominant_emotion, emotions, confidence}]` |
| `issues` | array | `[{type, description, severity, suggestion, timestamps}]` |
| `skipped` | bool | **`true` when no face detected — check this!** |
| `reason` | string | Why it was skipped |

### `pose_analysis` (all scores 0–100)
| Field | Type | Description |
|---|---|---|
| `overall_score` | float | Overall body language quality |
| `posture_score` | float | Posture quality |
| `gesture_score` | float | Hand gesture effectiveness |
| `movement_score` | float | Body movement quality |
| `avg_shoulder_alignment` | float | Shoulder alignment metric |
| `fidgeting_frequency` | float | Fidgeting rate |
| `gesture_frequency` | float | Gesture rate |
| `pose_timeline` | array | `[{timestamp, pose_type, shoulder_alignment, confidence}]` |
| `issues` | array | `[{type, description, severity, suggestion, timestamps}]` |
| `skipped` | bool | **`true` when no person detected — check this!** |
| `reason` | string | Why it was skipped |

### `content_analysis` (all scores 0–100)
| Field | Type | Description |
|---|---|---|
| `overall_score` | float | Overall content quality |
| `clarity_score` | float | Message clarity |
| `persuasion_score` | float | Persuasiveness |
| `structure_score` | float | Presentation structure |
| `filler_word_count` | int | Total filler words |
| `filler_words` | array | `[{word, count, timestamps}]` |
| `weak_phrases` | array | `[{phrase, context, suggestion, timestamp}]` |
| `negative_language` | array | Negative phrases detected |
| `key_points` | array | Key points extracted (strings) |
| `llm_feedback` | string | AI-generated detailed feedback |

### `report` (summary + insights)
| Field | Type | Description |
|---|---|---|
| `overall_score` | float | Weighted overall score (0–100) |
| `voice_score` | float | Voice summary score |
| `facial_score` | float | Facial summary score |
| `pose_score` | float | Pose summary score |
| `content_score` | float | Content summary score |
| `executive_summary` | string | Text summary of performance |
| `strengths` | array | List of strength strings |
| `improvements` | array | `[{area, description, priority, suggestion, tips}]` |
| `recommendations` | array | `[{title, category, priority, description, exercises}]` |
| `timestamped_issues` | array | `[{timestamp, category, issue, description, severity, suggestion}]` |

### `report` — Comparison Fields (only present when compared against golden pitch deck / skillset)
| Field | Type | Description |
|---|---|---|
| `golden_pitch_deck_id` | string | ID of reference pitch deck |
| `comparison_overall_score` | float | Overall similarity (0–100) |
| `content_similarity_score` | float | Content match % |
| `keyword_coverage_score` | float | Keyword coverage % |
| `voice_similarity_score` | float | Voice similarity % |
| `pose_similarity_score` | float | Pose similarity % |
| `facial_similarity_score` | float | Facial similarity % |
| `keyword_comparison` | object | Detailed keyword comparison |
| `content_comparison` | object | Detailed content comparison |
| `voice_comparison` | object | Detailed voice comparison |
| `pose_comparison` | object | Detailed pose comparison |
| `facial_comparison` | object | Detailed facial comparison |

### `transcription`
| Field | Type | Description |
|---|---|---|
| `full_text` | string | Complete transcript |
| `language` | string | Detected language code |
| `confidence` | float | Overall transcription confidence |
| `segments` | array | `[{text, start, end, confidence}]` |

---

## Important Notes

1. **All scores are 0–100.** Divide by 20 to convert to a 5-point scale.
2. **Check `skipped` flag** on `facial_analysis` and `pose_analysis` before displaying those sections. When `skipped == true`, scores are 0 and should not be shown.
3. **Comparison fields** are only populated when the analysis was run with a golden pitch deck or skillset reference. They will be `null` otherwise.
4. **`timestamped_issues`** contains ALL issues across all categories (voice, facial, pose, content) in chronological order by timestamp.

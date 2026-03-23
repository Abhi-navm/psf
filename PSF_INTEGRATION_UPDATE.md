# PSF Integration Update — March 19, 2026

## Summary

This document covers:
1. **Bug fixes deployed** — What changed in scoring and how it affects your display
2. **New API endpoint** — Worker-level aggregated recommendations
3. **Field mapping reminders** — Ensure your frontend reads the right fields

---

## 2. New Endpoint: Worker Aggregate Recommendations

### Purpose

Given all analysis IDs for a single worker, returns averaged scores and **recurring patterns** — the issues that appear across multiple videos, ranked by frequency.

### Endpoint

```
POST /api/v1/analyses/aggregate
```

### Request Body

```json
{
  "analysis_ids": [
    "c71b7c72-b03b-4551-ac76-b4080de4b2ef",
    "82ab1126-62d3-4155-8b2f-83a8ad7f8c4c",
    "9435237c-557d-4e65-9a22-f3db2ee68ee2"
  ]
}
```

- Pass all completed analysis IDs for one worker
- Maximum 100 IDs per request
- Only `completed` analyses are included

### Response

```json
{
  "total_analyses": 3,
  "avg_overall_score": 71.1,
  "avg_voice_score": 65.7,
  "avg_facial_score": 36.7,
  "avg_pose_score": 57.8,
  "avg_content_score": 75.5,
  "avg_comparison_score": 54.5,

  "recurring_issues": [
    {
      "category": "Voice",
      "issue": "Speaking volume is consistently low",
      "description": "Speaking volume is consistently low",
      "suggestion": "Speak with more projection and energy",
      "severity": "medium",
      "occurrence_count": 2,
      "total_analyses": 3,
      "frequency_percent": 66.7
    },
    {
      "category": "Facial Expression",
      "issue": "Sad expression detected",
      "description": "Sad expression detected",
      "suggestion": "Maintain a positive, upbeat demeanor",
      "severity": "medium",
      "occurrence_count": 2,
      "total_analyses": 3,
      "frequency_percent": 66.7
    }
  ],

  "aggregated_recommendations": [
    {
      "category": "voice",
      "title": "Voice Training",
      "description": "Practice vocal exercises to improve projection and variation",
      "priority": "medium",
      "occurrence_count": 3,
      "frequency_percent": 100.0
    },
    {
      "category": "voice",
      "title": "Adjust speaking pace",
      "description": "Speaking faster than the reference - consider slowing down for clarity",
      "priority": "medium",
      "occurrence_count": 3,
      "frequency_percent": 100.0
    },
    {
      "category": "facial",
      "title": "Expression Practice",
      "description": "Work on facial expressions to appear more engaging",
      "priority": "medium",
      "occurrence_count": 2,
      "frequency_percent": 66.7
    }
  ],

  "common_filler_words": [
    { "word": "basically", "total_count": 6, "avg_per_video": 2.0 },
    { "word": "actually", "total_count": 3, "avg_per_video": 1.0 }
  ],

  "score_trend": [
    { "analysis_id": "9435237c-...", "date": "2026-03-18T19:28:25", "overall_score": 75.0 },
    { "analysis_id": "c71b7c72-...", "date": "2026-03-18T19:41:01", "overall_score": 68.2 },
    { "analysis_id": "82ab1126-...", "date": "2026-03-18T19:48:32", "overall_score": 70.1 }
  ]
}
```

### Response Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `total_analyses` | int | Number of completed analyses found |
| `avg_overall_score` | float | Average overall score across all analyses |
| `avg_voice_score` | float | Average voice score |
| `avg_facial_score` | float | Average facial score |
| `avg_pose_score` | float | Average pose score |
| `avg_content_score` | float | Average content score |
| `avg_comparison_score` | float or null | Average comparison score (null if no comparisons) |
| `recurring_issues` | array | Issues from `report.improvements`, sorted by frequency |
| `recurring_issues[].category` | string | "Voice", "Facial Expression", "Body Language", "Speech Content" |
| `recurring_issues[].issue` | string | Issue description |
| `recurring_issues[].suggestion` | string | Actionable suggestion |
| `recurring_issues[].severity` | string | "high", "medium", "low" |
| `recurring_issues[].occurrence_count` | int | How many analyses had this issue |
| `recurring_issues[].frequency_percent` | float | Percentage of analyses with this issue |
| `aggregated_recommendations` | array | From `report.recommendations`, sorted by frequency |
| `aggregated_recommendations[].category` | string | "voice", "facial", "pose", "content", "general" |
| `aggregated_recommendations[].title` | string | Recommendation title |
| `aggregated_recommendations[].description` | string | Full recommendation text |
| `aggregated_recommendations[].priority` | string | "high", "medium", "low" |
| `aggregated_recommendations[].occurrence_count` | int | How many analyses generated this |
| `aggregated_recommendations[].frequency_percent` | float | Percentage of analyses |
| `common_filler_words` | array | Top 10 filler words across all videos |
| `score_trend` | array | Scores over time, sorted chronologically |

### How to Use for "Worker AI Corrections"

To show a **worker-level summary** of common issues:

```
1. Collect all analysis_ids for the worker
2. POST /api/v1/analyses/aggregate with those IDs
3. Display recurring_issues where frequency_percent > 50% as "common patterns"
4. Display aggregated_recommendations sorted by occurrence_count as "focus areas"
5. Use score_trend to show improvement over time
```

### Suggested UI Display

**Common Patterns** (from `recurring_issues` where `frequency_percent >= 50`):
- "Speaking volume is consistently low" — appears in 67% of pitches
- "Sad expression detected" — appears in 67% of pitches

**Focus Areas** (from `aggregated_recommendations` top 3):
- Action 1: Practice vocal exercises to improve projection and variation (100% of pitches)
- Action 2: Speaking faster than the reference (100% of pitches)
- Action 3: Work on facial expressions (67% of pitches)

**Filler Word Habits** (from `common_filler_words`):
- "basically" — avg 2.0 per video
- "actually" — avg 1.0 per video

---

## 3. Existing Field Mapping Reminders

### Per-Analysis AI Corrections

Your screenshot shows "Recommended AI Corrections" — these come from TWO fields:

| Source Field | What It Contains |
|---|---|
| `report.recommendations[]` | Comparison-based recs + category-based training tips. Each has: `category`, `title`, `description`, `priority`, `exercises` |
| `report.improvements[]` | Specific issues found in this video. Each has: `area`, `description`, `suggestion`, `priority`, `tips` |

**Current PSF behavior:** Reads `report.recommendations` → displays as Action 1-6. This is correct and working.

**Optional enhancement:** Merge both fields for richer corrections:
```javascript
const corrections = [
  ...report.recommendations.map(r => r.description),
  ...report.improvements.map(i => i.description),
].slice(0, 8);
```

### Fields That Changed

| Field | Change |
|---|---|
| `voice_analysis.speaking_rate_wpm` | Now always the transcript-corrected WPM (not acoustic estimate) |
| `content_analysis.filler_word_count` | Lower counts now (removed right/so/well/things) |
| `report.comparison_overall_score` | Higher for slide-only videos (no longer penalized for missing face) |
| `voice_analysis.avg_pitch` | Now in 75-400Hz range (was 300-1200Hz before) |

---

## 4. Base URL

```
Production: http://187.124.99.79:8000
Docs: http://187.124.99.79:8000/docs
```

The `/aggregate` endpoint is live now on the API server. RunPod serverless workers will have the scoring fixes after the auto-build completes (~10-15 min).

# Sales Pitch Analyzer — API Documentation

**Base URL**: `http://<host>:8000`  
**Content-Type**: `application/json` (unless noted otherwise)

---

## Table of Contents

1. [Health Check](#1-health-check)
2. [Video Upload & Management](#2-video-upload--management)
3. [Golden Pitch Deck](#3-golden-pitch-deck)
4. [Analysis](#4-analysis)
5. [Integration Workflow](#5-integration-workflow)
6. [Error Format](#6-error-format)

---

## 1. Health Check

### `GET /health`

Returns service health status.

**Response** `200 OK`
```json
{
  "status": "ok",
  "environment": "development",
  "version": "0.1.0",
  "services": {
    "redis": "healthy",
    "database": "healthy",
    "ollama": "healthy"
  }
}
```

### `POST /warm`

Pre-warm ML models (background, 30-60s).

**Response** `200 OK`
```json
{
  "status": "warming",
  "message": "Model warming started in background. Check /warm/status for progress."
}
```

### `GET /warm/status`

Check model warming progress.

**Response** `200 OK`
```json
{
  "status": "ready",
  "models": {
    "whisper": true,
    "sentence_transformer": true,
    "deepface": true,
    "ollama": true
  }
}
```

---

## 2. Video Upload & Management

### `POST /api/v1/videos/upload`

Upload a video or audio file for analysis.

**Request**: `multipart/form-data`

| Field  | Type   | Required | Description |
|--------|--------|----------|-------------|
| `file` | binary | Yes      | Video/audio file |

**Allowed formats**:
- **Video**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`
- **Audio**: `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac`, `.wma`
- **Max size**: 500 MB

**Response** `200 OK`
```json
{
  "id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
  "original_filename": "pitch_video.mp4",
  "filename": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876.mp4",
  "file_path": "/data/uploads/videos/78cb50e8-6c24-41a2-a91a-7e8ec3abd876.mp4",
  "file_size": 38608042,
  "mime_type": "video/mp4",
  "duration": 384.19,
  "width": 640,
  "height": 360,
  "fps": 25.0,
  "is_audio_only": false,
  "created_at": "2026-03-10T08:38:30.288414"
}
```

**Errors**: `400` invalid format, `413` file too large

---

### `GET /api/v1/videos`

List all uploaded videos with analysis status.

| Query Param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page`      | int  | 1       | Page number (≥ 1) |
| `page_size` | int  | 20      | Items per page (1-100) |

**Response** `200 OK`
```json
{
  "videos": [
    {
      "id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
      "original_filename": "pitch_video.mp4",
      "filename": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876.mp4",
      "file_path": "/data/uploads/videos/78cb50e8-...",
      "file_size": 38608042,
      "mime_type": "video/mp4",
      "duration": 384.19,
      "width": 640,
      "height": 360,
      "fps": 25.0,
      "is_audio_only": false,
      "created_at": "2026-03-10T08:38:30.288414",
      "analysis_id": "35232ced-cbbf-4733-94f1-263549eb75cf",
      "analysis_status": "completed",
      "overall_score": 66.0,
      "comparison_score": 96.4
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

---

### `GET /api/v1/videos/{video_id}`

Get a single video by ID.

**Response** `200 OK` — Same as single item in upload response.  
**Errors**: `404` not found

---

### `DELETE /api/v1/videos/{video_id}`

Delete video and all associated analyses.

**Response** `200 OK`
```json
{ "message": "Video deleted successfully" }
```

---

### `GET /api/v1/videos/{video_id}/stream`

Stream video file for playback.

**Response**: Binary stream with appropriate `Content-Type` header.

---

## 3. Golden Pitch Deck

The golden pitch deck is a **reference video** that test videos are compared against.

### `POST /api/v1/golden-pitch-decks`

Create a golden pitch deck from an already-uploaded video. The video must be uploaded first via `/api/v1/videos/upload`.

**Request Body**
```json
{
  "video_id": "94c89cbd-3364-45b8-879d-2d6e409c6c15",
  "name": "Q1 Sales Pitch Reference",
  "description": "Best performing pitch from Q1 2026",
  "set_as_active": true
}
```

| Field           | Type    | Required | Default | Description |
|-----------------|---------|----------|---------|-------------|
| `video_id`      | string  | Yes      | —       | UUID of uploaded video |
| `name`          | string  | Yes      | —       | Display name (1-255 chars) |
| `description`   | string  | No       | null    | Optional description |
| `set_as_active` | boolean | No       | true    | Set as active reference |

**Response** `200 OK`
```json
{
  "id": "4617a6de-9741-4cd8-b3a2-bafce10fd0f9",
  "name": "Q1 Sales Pitch Reference",
  "description": "Best performing pitch from Q1 2026",
  "video_id": "94c89cbd-3364-45b8-879d-2d6e409c6c15",
  "is_active": true,
  "is_processed": false,
  "processing_error": null,
  "created_at": "2026-03-10T08:01:08.000000",
  "updated_at": "2026-03-10T08:01:08.000000",
  "keywords": null,
  "key_phrases": null,
  "voice_metrics": null,
  "pose_metrics": null,
  "facial_metrics": null,
  "content_metrics": null
}
```

> **Note**: Processing happens asynchronously. Poll the GET endpoint until `is_processed` becomes `true`. Once processed, the `keywords`, `voice_metrics`, etc. fields will be populated.

**Processed golden pitch deck example** (after `is_processed: true`):
```json
{
  "id": "4617a6de-9741-4cd8-b3a2-bafce10fd0f9",
  "name": "Q1 Sales Pitch Reference",
  "description": null,
  "video_id": "94c89cbd-3364-45b8-879d-2d6e409c6c15",
  "is_active": true,
  "is_processed": true,
  "processing_error": null,
  "created_at": "2026-03-10T08:01:08.000000",
  "updated_at": "2026-03-10T08:05:32.000000",
  "keywords": {
    "keywords": ["transformation", "cyber", "resilience", "data", "security"],
    "semantic_keywords": ["data resilience", "zero-trust architecture", "recovery time objective"],
    "key_phrases": ["rubrik security cloud", "data protection", "cyber recovery"]
  },
  "key_phrases": ["rubrik security cloud", "data protection", "cyber recovery"],
  "voice_metrics": {
    "overall_score": 72.0,
    "energy_score": 88.1,
    "clarity_score": 80.0,
    "pace_score": 60.0,
    "confidence_score": 20.0,
    "tone_score": 50.0,
    "avg_pitch": 824.3,
    "speaking_rate_wpm": 65.12
  },
  "pose_metrics": {
    "overall_score": 66.4,
    "posture_score": 69.1,
    "gesture_score": 100.0,
    "movement_score": 30.0,
    "gesture_frequency": 0.62
  },
  "facial_metrics": {
    "overall_score": 55.2,
    "positivity_score": 36.7,
    "engagement_score": 70.7,
    "confidence_score": 90.0
  },
  "content_metrics": {
    "overall_score": 73.7,
    "clarity_score": 70.0,
    "persuasion_score": 66.0,
    "structure_score": 85.0
  }
}
```

**Errors**: `404` video not found, `409` golden pitch already exists for this video

---

### `GET /api/v1/golden-pitch-decks`

List all golden pitch decks.

| Query Param   | Type    | Default | Description |
|---------------|---------|---------|-------------|
| `active_only` | boolean | false   | Only return active decks |

**Response** `200 OK`
```json
{
  "items": [ /* array of GoldenPitchDeck objects */ ],
  "total": 1
}
```

---

### `GET /api/v1/golden-pitch-decks/active`

Get the currently active golden pitch deck.

**Response** `200 OK` — Single `GoldenPitchDeck` object.  
**Errors**: `404` no active deck

---

### `GET /api/v1/golden-pitch-decks/{id}`

Get a specific golden pitch deck.

**Errors**: `404` not found

---

### `PATCH /api/v1/golden-pitch-decks/{id}`

Update name, description, or active status.

**Request Body** (all fields optional)
```json
{
  "name": "Updated Name",
  "description": "New description",
  "is_active": true
}
```

---

### `DELETE /api/v1/golden-pitch-decks/{id}`

Delete a golden pitch deck.

**Response** `204 No Content`

---

### `POST /api/v1/golden-pitch-decks/{id}/reprocess`

Re-extract reference metrics from the video.

**Response** `200 OK` — Updated `GoldenPitchDeck` object with `is_processed: false`.

---

### `POST /api/v1/golden-pitch-decks/{id}/set-active`

Set this deck as the active reference (deactivates all others).

**Response** `200 OK` — Updated `GoldenPitchDeck` object.

---

## 4. Analysis

### `POST /api/v1/analyses`

Start analyzing a test video. Automatically compares against the active golden pitch deck.

**Request Body**
```json
{
  "video_id": "9192dacf-40c9-4b7a-bd21-3938bc7ccc4b",
  "golden_pitch_deck_id": null,
  "skip_comparison": false
}
```

| Field                  | Type    | Required | Default | Description |
|------------------------|---------|----------|---------|-------------|
| `video_id`             | string  | Yes      | —       | UUID of uploaded video |
| `golden_pitch_deck_id` | string  | No       | null    | Specific golden deck ID (uses active if null) |
| `skip_comparison`      | boolean | No       | false   | Skip golden pitch comparison |

**Response** `200 OK`
```json
{
  "id": "35232ced-cbbf-4733-94f1-263549eb75cf",
  "video_id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
  "status": "pending",
  "progress": 0,
  "error_message": null,
  "started_at": "2026-03-10T08:38:30.300000",
  "completed_at": null,
  "created_at": "2026-03-10T08:38:30.300000"
}
```

**Status progression**: `pending` → `processing` → `extracting_audio` → `transcribing` → `analyzing_voice` → `analyzing_facial` → `analyzing_pose` → `analyzing_content` → `generating_report` → `completed`

**Errors**: `404` video not found, `409` analysis already in progress

---

### `GET /api/v1/analyses/{analysis_id}/status`

Poll analysis progress. Use this to check when analysis is done.

**Response** `200 OK`
```json
{
  "id": "35232ced-cbbf-4733-94f1-263549eb75cf",
  "video_id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
  "status": "completed",
  "progress": 100,
  "error_message": null,
  "started_at": "2026-03-10T08:38:30.300000",
  "completed_at": "2026-03-10T08:42:10.500000",
  "created_at": "2026-03-10T08:38:30.300000"
}
```

---

### `GET /api/v1/analyses/{analysis_id}`

Get **complete analysis results** (all sub-analyses + report + comparison).

**Response** `200 OK`
```json
{
  "id": "35232ced-cbbf-4733-94f1-263549eb75cf",
  "video_id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
  "status": "completed",
  "progress": 100,

  "video": {
    "id": "78cb50e8-6c24-41a2-a91a-7e8ec3abd876",
    "original_filename": "pitch_video.mp4",
    "filename": "78cb50e8-...",
    "file_path": "/data/uploads/videos/78cb50e8-...",
    "file_size": 38608042,
    "mime_type": "video/mp4",
    "duration": 384.19,
    "width": 640,
    "height": 360,
    "fps": 25.0,
    "is_audio_only": false,
    "created_at": "2026-03-10T08:38:30.288414"
  },

  "transcription": {
    "full_text": "Hi everyone, welcome to our presentation on data resilience...",
    "language": "en",
    "confidence": 0.95,
    "segments": [
      { "text": "Hi everyone,", "start": 0.0, "end": 1.2 },
      { "text": " welcome to our presentation", "start": 1.2, "end": 3.5 }
    ],
    "word_timestamps": null
  },

  "voice_analysis": {
    "overall_score": 66.0,
    "energy_score": 75.0,
    "clarity_score": 80.0,
    "pace_score": 55.0,
    "confidence_score": 45.0,
    "tone_score": 60.0,
    "avg_pitch": 245.5,
    "pitch_variance": 180.3,
    "speaking_rate_wpm": 128.5,
    "pause_frequency": 0.15,
    "emotion_timeline": [
      { "timestamp": 0, "emotion": "neutral", "confidence": 0.8, "emotions": { "neutral": 0.8 } },
      { "timestamp": 15, "emotion": "happy", "confidence": 0.6, "emotions": { "happy": 0.6, "neutral": 0.4 } }
    ],
    "issues": [
      {
        "type": "low_energy",
        "severity": "medium",
        "description": "Speaking volume is consistently low",
        "suggestion": "Speak with more projection and energy"
      }
    ]
  },

  "facial_analysis": {
    "overall_score": 57.5,
    "positivity_score": 40.0,
    "engagement_score": 67.3,
    "confidence_score": 85.0,
    "emotion_distribution": {
      "happy": 20.0,
      "neutral": 40.0,
      "angry": 10.0,
      "sad": 5.0,
      "surprise": 10.0,
      "fear": 10.0,
      "disgust": 5.0
    },
    "emotion_timeline": [
      {
        "timestamp": 5.0,
        "dominant_emotion": "neutral",
        "confidence": 81.5,
        "emotions": { "neutral": 81.5, "happy": 10.0 }
      }
    ],
    "eye_contact_percentage": null,
    "issues": []
  },

  "pose_analysis": {
    "overall_score": 72.0,
    "posture_score": 75.0,
    "gesture_score": 80.0,
    "movement_score": 60.0,
    "avg_shoulder_alignment": 0.95,
    "fidgeting_frequency": 0.1,
    "gesture_frequency": 0.5,
    "pose_timeline": [],
    "issues": [
      {
        "type": "limited_gestures",
        "severity": "low",
        "description": "Limited hand gestures detected",
        "suggestion": "Use more purposeful hand movements to emphasize key points"
      }
    ]
  },

  "content_analysis": {
    "overall_score": 70.0,
    "clarity_score": 72.0,
    "persuasion_score": 65.0,
    "structure_score": 75.0,
    "filler_words": [
      { "word": "um", "count": 5, "timestamps": [12.3, 45.6, 78.9] }
    ],
    "filler_word_count": 8,
    "weak_phrases": [],
    "negative_language": [],
    "key_points": ["data resilience", "cyber recovery", "zero-trust"],
    "llm_feedback": "The pitch covers key topics but could be more concise..."
  },

  "report": {
    "overall_score": 66.0,
    "voice_score": 66.0,
    "facial_score": 57.5,
    "pose_score": 72.0,
    "content_score": 70.0,
    "executive_summary": "The pitch demonstrates solid content knowledge but needs improvement in vocal delivery...",
    "strengths": [
      "Clear structure and logical flow",
      "Good posture throughout presentation"
    ],
    "improvements": [
      {
        "area": "Voice",
        "description": "Increase vocal energy and vary tone",
        "priority": "high"
      }
    ],
    "timestamped_issues": [
      {
        "timestamp": 45.0,
        "category": "voice",
        "issue": "Speaking too slowly",
        "severity": "medium",
        "suggestion": "Pick up the pace slightly"
      }
    ],
    "recommendations": [
      {
        "recommendation": "Practice with more vocal variety",
        "priority": "high"
      }
    ],
    "golden_pitch_deck_id": "4617a6de-9741-4cd8-b3a2-bafce10fd0f9",
    "comparison_overall_score": 96.4,
    "content_similarity_score": 85.0,
    "keyword_coverage_score": 78.5,
    "voice_similarity_score": 72.0,
    "pose_similarity_score": 95.0,
    "facial_similarity_score": 90.0,
    "keyword_comparison": {
      "matched_keywords": ["resilience", "cyber", "data", "security"],
      "missing_keywords": ["transformation"],
      "coverage_score": 78.5
    },
    "content_comparison": {
      "overall_similarity_score": 85.0,
      "keyword_comparison": {
        "matched_keywords": ["resilience", "cyber", "data"],
        "missing_keywords": ["transformation"],
        "coverage_score": 78.5
      },
      "semantic_similarity": 88.2,
      "structure_comparison": { "similarity_score": 75.0 },
      "phrase_coverage": {
        "coverage_score": 70.0,
        "covered_phrases": ["data protection", "cyber recovery"],
        "missing_phrases": ["rubrik security cloud"]
      }
    },
    "voice_comparison": {
      "overall_similarity_score": 72.0,
      "comparisons": {
        "speaking_rate": {
          "reference": 65.12,
          "uploaded": 128.5,
          "similarity": 60.0,
          "feedback": "Speaking faster than reference"
        },
        "pitch": { "reference": 824.3, "uploaded": 245.5, "similarity": 50.0 },
        "energy": { "reference": 88.1, "uploaded": 75.0, "similarity": 85.0 },
        "confidence": { "reference": 20.0, "uploaded": 45.0, "similarity": 75.0 }
      }
    },
    "pose_comparison": {
      "overall_similarity_score": 95.0,
      "comparisons": {
        "posture": { "reference": 69.1, "uploaded": 75.0, "similarity": 94.1 },
        "gesture": { "reference": 100.0, "uploaded": 80.0, "similarity": 80.0 },
        "movement": { "reference": 30.0, "uploaded": 60.0, "similarity": 70.0 },
        "gesture_frequency": { "reference": 0.62, "uploaded": 0.5, "similarity": 80.6 }
      }
    },
    "facial_comparison": {
      "overall_similarity_score": 90.0,
      "comparisons": {
        "positivity": { "reference": 36.7, "uploaded": 40.0, "similarity": 96.7 },
        "engagement": { "reference": 70.7, "uploaded": 67.3, "similarity": 96.6 },
        "confidence": { "reference": 90.0, "uploaded": 85.0, "similarity": 95.0 },
        "emotion_distribution": { "similarity": 88.0 }
      }
    }
  },

  "created_at": "2026-03-10T08:38:30.300000",
  "completed_at": "2026-03-10T08:42:10.500000"
}
```

---

### `GET /api/v1/analyses/{analysis_id}/transcription`

Get only the transcription data.

---

### `GET /api/v1/analyses/{analysis_id}/voice`

Get only voice analysis data.

---

### `GET /api/v1/analyses/{analysis_id}/facial`

Get only facial expression analysis data.

---

### `GET /api/v1/analyses/{analysis_id}/pose`

Get only body pose analysis data.

---

### `GET /api/v1/analyses/{analysis_id}/content`

Get only content analysis data.

---

### `GET /api/v1/analyses/{analysis_id}/report`

Get only the final report (includes comparison scores).

---

### `GET /api/v1/analyses/video/{video_id}`

List all analyses for a specific video.

**Response** `200 OK`
```json
[
  {
    "id": "35232ced-cbbf-4733-94f1-263549eb75cf",
    "video_id": "78cb50e8-...",
    "status": "completed",
    "progress": 100,
    "error_message": null,
    "started_at": "2026-03-10T08:38:30.300000",
    "completed_at": "2026-03-10T08:42:10.500000",
    "created_at": "2026-03-10T08:38:30.300000"
  }
]
```

---

### `DELETE /api/v1/analyses/{analysis_id}`

Cancel a pending/in-progress analysis.

**Response** `200 OK`
```json
{ "message": "Analysis cancelled" }
```

---

## 5. Integration Workflow

### Step-by-step to analyze a pitch video:

```
1. Upload golden pitch video
   POST /api/v1/videos/upload  (multipart, file=golden.mp4)
   → get video_id

2. Create golden pitch deck
   POST /api/v1/golden-pitch-decks
   { "video_id": "<video_id>", "name": "Reference Pitch", "set_as_active": true }
   → get golden_pitch_deck_id

3. Poll golden pitch until processed
   GET /api/v1/golden-pitch-decks/<golden_pitch_deck_id>
   → wait until is_processed == true

4. Upload test video
   POST /api/v1/videos/upload  (multipart, file=test.mp4)
   → get test_video_id

5. Start analysis
   POST /api/v1/analyses
   { "video_id": "<test_video_id>" }
   → get analysis_id

6. Poll analysis status
   GET /api/v1/analyses/<analysis_id>/status
   → repeat every 5s until status == "completed"

7. Get full results
   GET /api/v1/analyses/<analysis_id>
   → complete results with comparison scores
```

### Key scores to display:

| Score | Location in response | Description |
|-------|---------------------|-------------|
| Overall Score | `report.overall_score` | Overall pitch quality (0-100) |
| Comparison Score | `report.comparison_overall_score` | How close to golden pitch (0-100) |
| Voice Quality | `report.voice_similarity_score` | Voice similarity to reference |
| Facial Expression | `report.facial_similarity_score` | Facial expression similarity |
| Keyword Match | `report.keyword_coverage_score` | % of reference keywords covered |
| Context Alignment | `report.content_comparison.semantic_similarity` | Semantic content similarity |
| Confidence / Pose | `report.pose_similarity_score` | Body language similarity |
| Content Score | `content_analysis.overall_score` | Content quality score |

---

## 6. Error Format

All errors return:
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

| Code | Status | Description |
|------|--------|-------------|
| `VIDEO_NOT_FOUND` | 404 | Video ID doesn't exist |
| `VIDEO_TOO_LARGE` | 413 | File exceeds 500MB limit |
| `INVALID_VIDEO_FORMAT` | 400 | Unsupported file format |
| `ANALYSIS_IN_PROGRESS` | 409 | Analysis already running for this video |
| `ANALYSIS_NOT_FOUND` | 404 | Analysis ID doesn't exist |

### Analysis status values:

| Status | Description |
|--------|-------------|
| `pending` | Queued, not yet started |
| `processing` | Initial processing |
| `extracting_audio` | Extracting audio track |
| `transcribing` | Speech-to-text (Whisper) |
| `analyzing_voice` | Voice tone/pace analysis |
| `analyzing_facial` | Facial expression analysis |
| `analyzing_pose` | Body language analysis |
| `analyzing_content` | Content/keyword analysis (LLM) |
| `generating_report` | Building final report |
| `completed` | Done — results available |
| `failed` | Error occurred (check `error_message`) |

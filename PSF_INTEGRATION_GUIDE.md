# Pitch Analyzer API — Integration Guide for PSF Team

## What Changed

The Pitch Analyzer backend now supports **multi-tenant isolation** and **explicit deck-based comparison**.

---

## Key Behavior Changes

### 1. User/Tenant scoping via `X-User-Id` header
- All API calls can include an `X-User-Id` header to scope data to a specific user/tenant.
- Without the header, all data is visible (backward-compatible).
- Videos, golden pitch decks, and analyses are all filtered by this header when present.

### 2. No automatic comparison fallback
- **Previously**: if no `golden_pitch_deck_id` was sent with an analysis, the system would auto-pick an "active" deck and compare against it.
- **Now**: if no `golden_pitch_deck_id` is provided → **analysis only, no comparison**.
- To get comparison, you **must** explicitly send the deck ID.

### 3. Celery / RunPod bug fixed
- `golden_pitch_deck_id` and `skip_comparison` were being dropped in the RunPod code path — now correctly passed through.

---

## API Reference

**Base URL**: `http://<host>:8000/api/v1`

All endpoints accept an optional `X-User-Id` header for tenant scoping.

---

### 1. Upload Video

```
POST /videos/upload
Content-Type: multipart/form-data
X-User-Id: <tenant_or_user_id>    (optional)

Body: file=<video_file>
```

**Response:**
```json
{
  "id": "<video_uuid>",
  "filename": "...",
  "file_path": "...",
  "file_size": 12345,
  "mime_type": "video/mp4",
  "user_id": "<tenant_or_user_id>",
  "duration": 120.5,
  "created_at": "..."
}
```

Use the returned `id` as `video_id` in subsequent calls.

---

### 2. Create Golden Pitch Deck (Admin uploads reference)

Used for **both golden pitch decks and skillsets** — they use the same endpoint. PSF manages the type distinction on its side.

```
POST /golden-pitch-decks
Content-Type: application/json
X-User-Id: <tenant_or_user_id>    (optional)

{
  "video_id": "<uploaded_video_id>",
  "name": "Objection Handling",
  "description": "...",            // optional
  "user_id": "<tenant_id>",       // optional, overrides header
  "set_as_active": false           // recommended: false
}
```

**Response:**
```json
{
  "id": "<deck_uuid>",
  "name": "Objection Handling",
  "video_id": "<video_id>",
  "user_id": "<tenant_id>",
  "is_active": false,
  "is_processed": false,
  "processing_error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

> **Important:** Save the returned `id` as `analyzer_deck_id` in the PSF `reference_videos` table.

**Processing** happens asynchronously. Poll the deck to check status:

```
GET /golden-pitch-decks/<deck_id>
X-User-Id: <tenant_id>            (optional)
```

Wait until `is_processed == true` before using for comparison.

---

### 3. Start Analysis

#### With comparison (user video compared against admin's reference):

```
POST /analyses
Content-Type: application/json
X-User-Id: <user_id>              (optional)

{
  "video_id": "<uploaded_sales_video_id>",
  "golden_pitch_deck_id": "<admin_deck_id>",
  "skip_comparison": false,
  "user_id": "<user_id>"
}
```

#### Without comparison (admin uploads reference, just analyze):

```
POST /analyses
Content-Type: application/json
X-User-Id: <user_id>              (optional)

{
  "video_id": "<uploaded_reference_video_id>"
}
```

No `golden_pitch_deck_id` → no comparison performed.

**Response:**
```json
{
  "id": "<analysis_uuid>",
  "video_id": "...",
  "status": "pending",
  "progress": 0,
  "started_at": "...",
  "created_at": "..."
}
```

---

### 4. Poll Analysis Status

```
GET /analyses/<analysis_id>/status
```

**Response:**
```json
{
  "id": "<analysis_id>",
  "video_id": "...",
  "status": "pending | processing | extracting_audio | transcribing | analyzing_voice | analyzing_facial | analyzing_pose | analyzing_content | generating_report | completed | failed",
  "progress": 0-100,
  "error_message": null,
  "started_at": "...",
  "completed_at": null,
  "created_at": "..."
}
```

Poll until `status == "completed"` or `status == "failed"`.

---

### 5. Get Full Analysis Result

```
GET /analyses/<analysis_id>
```

**Response** (when completed):
```json
{
  "id": "<analysis_id>",
  "video_id": "...",
  "status": "completed",
  "progress": 100,
  "video": { ... },
  "transcription": {
    "full_text": "...",
    "language": "en",
    "confidence": 0.95,
    "segments": [...]
  },
  "voice_analysis": {
    "overall_score": 72.5,
    "energy_score": 65.0,
    "clarity_score": 80.0,
    "pace_score": 70.0,
    "confidence_score": 75.0,
    "tone_score": 68.0,
    ...
  },
  "facial_analysis": {
    "overall_score": 68.0,
    "positivity_score": 60.0,
    "engagement_score": 75.0,
    "confidence_score": 70.0,
    ...
  },
  "pose_analysis": {
    "overall_score": 74.0,
    "posture_score": 80.0,
    "gesture_score": 70.0,
    "movement_score": 72.0,
    ...
  },
  "content_analysis": {
    "overall_score": 71.0,
    "clarity_score": 75.0,
    "persuasion_score": 68.0,
    "structure_score": 70.0,
    ...
  },
  "report": {
    "overall_score": 71.4,
    "voice_score": 72.5,
    "facial_score": 68.0,
    "pose_score": 74.0,
    "content_score": 71.0,
    "executive_summary": "...",
    "strengths": ["..."],
    "improvements": [{"area": "...", "description": "...", "priority": "..."}],
    "recommendations": [...],

    // Comparison fields — ONLY present when golden_pitch_deck_id was provided
    "golden_pitch_deck_id": "<deck_id>",
    "comparison_overall_score": 78.5,
    "content_similarity_score": 82.0,
    "keyword_coverage_score": 75.0,
    "voice_similarity_score": 70.0,
    "pose_similarity_score": 80.0,
    "facial_similarity_score": 76.0,
    "keyword_comparison": {
      "matched_keywords": ["..."],
      "missing_keywords": ["..."],
      "coverage_score": 75.0
    },
    "content_comparison": { ... },
    "voice_comparison": { ... },
    "pose_comparison": { ... },
    "facial_comparison": { ... }
  }
}
```

> **Note:** If `golden_pitch_deck_id` was not provided in the analysis request, comparison fields (`comparison_overall_score`, etc.) will be `null`.

---

### 6. List Decks (per tenant)

```
GET /golden-pitch-decks
X-User-Id: <tenant_id>            (optional)
```

**Query params:**
- `active_only` (bool, default: false) — only return active decks

**Response:**
```json
{
  "items": [
    {
      "id": "<deck_id>",
      "name": "...",
      "user_id": "<tenant_id>",
      "is_active": true,
      "is_processed": true,
      ...
    }
  ],
  "total": 1
}
```

---

### 7. Other Deck Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/golden-pitch-decks/<deck_id>` | Get specific deck |
| `GET` | `/golden-pitch-decks/active` | Get the active deck (for this user/tenant) |
| `PATCH` | `/golden-pitch-decks/<deck_id>` | Update name/description/is_active |
| `DELETE` | `/golden-pitch-decks/<deck_id>` | Delete a deck |
| `POST` | `/golden-pitch-decks/<deck_id>/reprocess` | Reprocess a deck |
| `POST` | `/golden-pitch-decks/<deck_id>/set-active` | Set as active (deactivates others for same user) |

---

## Flow Summary

### Admin Flow (upload references)

```
1. POST /videos/upload (with X-User-Id: <tenant_id>)
   → get video_id

2. POST /golden-pitch-decks
   body: { video_id, name, set_as_active: false, user_id: <tenant_id> }
   → get deck_id (save as analyzer_deck_id)

3. Poll GET /golden-pitch-decks/<deck_id>
   → wait until is_processed == true
```

Repeat for each reference: one golden pitch + N skillsets per tenant.

### User Flow (upload and compare)

```
1. POST /videos/upload (with X-User-Id: <user_id>)
   → get video_id

2. POST /analyses
   body: {
     video_id: <video_id>,
     golden_pitch_deck_id: <admin's deck_id>,
     skip_comparison: false
   }
   → get analysis_id

3. Poll GET /analyses/<analysis_id>/status
   → wait until status == "completed"

4. GET /analyses/<analysis_id>
   → get full result with comparison scores
```

### Admin Analysis (no comparison)

```
1. POST /videos/upload
   → get video_id

2. POST /analyses
   body: { video_id: <video_id> }
   → analysis only, no comparison
```

---

## Important Notes

1. **PSF must store `deck_id`** returned by `POST /golden-pitch-decks` as `analyzer_deck_id` in the `reference_videos` table.

2. **PSF must always send `golden_pitch_deck_id`** when creating an analysis that requires comparison. There is **no auto-fallback** to any "active" deck.

3. **Tenant isolation** is enforced when `X-User-Id` header is sent. One tenant cannot see another's videos, decks, or analyses.

4. **Skillsets use the same API** as golden pitch decks (`POST /golden-pitch-decks`). PSF controls the type distinction (GOLDEN_PITCH vs SKILLSET) on its side. Each skillset gets its own unique `deck_id`.

5. **`comparison_overall_score`** is present in the report only when comparison was requested. If it is `null` despite comparison being requested, treat it as a failure.

6. **`is_processed`** on a deck means reference data (keywords, voice metrics, etc.) has been extracted and the deck is ready for comparison. Do not use a deck for comparison until this is `true`.

---

## Webhook Support (Optional)

If configured, the analyzer can call back into PSF when analysis completes:

```
POST /api/v1/webhooks/pitch-analysis
body: {
  "analysisId": "...",
  "status": "completed | failed",
  "overall_score": 71.4,
  "comparison_score": 78.5,
  "error_message": null
}
```

The webhook expects the same semantics: if `status == "completed"`, either include `comparison_score` or ensure `GET /analyses/<id>` returns it in the report.

# PSF Pitch Analyzer: Validation Gates + Relevance Check Handoff

## Purpose
This document summarizes backend changes introduced for pitch validation and relevance classification, and what the backend/frontend integration team should expect.

## Scope of Changes

### 1) New Validation/Error Types
Added in `backend/app/core/exceptions.py`:
- `VIDEO_TOO_SHORT`
- `UNSUPPORTED_LANGUAGE`
- `TRANSCRIPT_TOO_SHORT`
- `CONTENT_NOT_RELEVANT`

### 2) New Configuration Flags
Added in `backend/app/core/config.py`:
- `min_video_duration_seconds` (current default in code: `25`)
- `min_transcript_words` (default: `20`)
- `supported_languages` (comma-separated language codes, empty means allow all)
- `relevance_check_enabled` (default: `False`)
- `anthropic_api_key`
- `anthropic_model`
- Helper property: `supported_language_list`

### 3) Content Relevance Classifier
Updated in `backend/app/analyzers/content.py`:
- Added LLM-based relevance classification for transcript content.
- Added hard gate behavior: if content is irrelevant and relevance check is enabled, raise `CONTENT_NOT_RELEVANT`.
- LLM backend order is now:
  1. Ollama
  2. Anthropic (Claude)
  3. Groq

### 4) Gate Enforcement in Pipelines
- Local/Celery pipeline: `backend/app/tasks/analysis_tasks.py`
- Serverless pipeline: `serverless/handler.py`

Enforced checks:
- Minimum duration gate
- Minimum transcript word count gate
- Supported language gate
- Relevance gate (when enabled)

### 5) Dependency Updates
- `backend/requirements.txt`: added `anthropic`
- `backend/requirements-prod.txt`: added `anthropic`

### 6) Smoke Tests
`backend/tests/smoke_test_relevance.py` covers:
- relevance pass/fail
- malformed LLM output fallback
- gate enabled/disabled behavior
- live LLM checks

Result observed: all tests passing locally.

---

## Failure Response Contract
Known failures return structured payload:

```json
{
  "error": "Human-readable message",
  "code": "MACHINE_READABLE_ERROR_CODE",
  "details": {}
}
```

### Sample Error Codes
- `VIDEO_TOO_SHORT`
- `UNSUPPORTED_LANGUAGE`
- `TRANSCRIPT_TOO_SHORT`
- `CONTENT_NOT_RELEVANT`

---

## Integration Impact

### Potential behavior changes (if new image is deployed)
- More requests may fail early due to new gates.
- Short clips can be rejected by duration threshold.
- Non-allowed language uploads can be rejected when allowlist is configured.
- Non-business/non-pitch content can be rejected when relevance check is enabled.

### Safe defaults
- `relevance_check_enabled` is `False` by default.
- With defaults, relevance hard-blocking is inactive unless explicitly enabled.

---

## Frontend Handling Recommendation
Map response `code` to UI behavior:
- `VIDEO_TOO_SHORT`: show upload validation with minimum seconds.
- `TRANSCRIPT_TOO_SHORT`: show retry guidance (clearer/louder/longer speech).
- `UNSUPPORTED_LANGUAGE`: show supported language list.
- `CONTENT_NOT_RELEVANT`: show reason from `details.reason` and prompt re-upload.

Unknown codes should fall back to generic error handling.

---

## Deployment Notes
- Versioned image tags are recommended for coordinated rollout.
- Do not promote to shared `latest` without cross-team sign-off.
- Current environment should set only required env vars (do not commit secrets).

---

## Team Checklist
- [ ] Confirm expected gate thresholds
- [ ] Confirm supported languages list (if any)
- [ ] Confirm whether relevance gate should be enabled in production
- [ ] Validate frontend error mapping by `code`
- [ ] Validate one end-to-end run for each failure scenario

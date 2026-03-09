# AI Sales Pitch Analyzer - Technology Stack

## Product Overview
**Two core services:**

1. **Video Analysis** - Evaluates sales pitch videos for speech, voice tone, facial expressions, and body language

2. **Presentation Analysis** - Evaluates PPT/PDF presentations for content quality, design, structure, and effectiveness

---

## Service 1: Video Analysis

### Recommended Technology Stack

#### Backend Infrastructure
| Component | Technology | Purpose |
|-----------|------------|---------|
| API Framework | **FastAPI** | High-performance REST API |
| Task Queue | **Celery + Redis** | Async video processing |
| Database | **PostgreSQL** | Production data storage |
| Hosting | **AWS / GCP** | Cloud infrastructure |

#### AI/ML Components

| Analysis Type | Recommended Provider | Accuracy | Cost |
|---------------|---------------------|----------|------|
| **Speech Transcription** | Deepgram | 96% | $0.0043/min |
| **Voice Analysis** | Librosa (Open Source) | Good | $0 |
| **Facial Expression** | DeepFace (Open Source) | 7 emotions | $0 |
| **Body Pose** | MediaPipe (Google, Open Source) | 33 landmarks | $0 |
| **Content Analysis** | OpenAI GPT-4o Mini | Excellent | $0.15/1M tokens |

---

## Service 2: Presentation Analysis (PPT/PDF)

### What It Analyzes

| Category | Checks |
|----------|--------|
| **Content Quality** | Clarity, persuasiveness, key message strength |
| **Structure** | Logical flow, intro/body/conclusion, transitions |
| **Text Issues** | Grammar, spelling, filler words, jargon overuse |
| **Design** | Font consistency, color contrast, slide density |
| **Data Visualization** | Chart clarity, data presentation |
| **Call-to-Action** | Presence and strength of CTA |

### Recommended Technology Stack

| Component | Technology | Purpose | Cost |
|-----------|------------|---------|------|
| **PDF Parsing** | PyMuPDF (fitz) | Extract text & images from PDF | $0 |
| **PPT Parsing** | python-pptx | Extract text & layout from PPTX | $0 |
| **OCR (if needed)** | Tesseract / EasyOCR | Extract text from images | $0 |
| **Text Analysis** | GPT-4o Mini | Content scoring & suggestions | $0.15/1M tokens |
| **Grammar Check** | LanguageTool API | Grammar & spelling | Free tier / $0.002/request |
| **Design Analysis** | Custom + GPT-4o Vision | Layout & visual scoring | $0.01/image |


### Scoring Categories

| Category | Weight | What's Evaluated |
|----------|--------|------------------|
| **Content Clarity** | 25% | Message clarity, jargon level, readability |
| **Persuasiveness** | 20% | Call-to-action, benefit statements, urgency |
| **Structure** | 20% | Logical flow, section organization |
| **Design Quality** | 20% | Visual consistency, readability, whitespace |
| **Data & Evidence** | 15% | Charts, statistics, proof points |

## Combined Cost Estimation

### Per 100 Analyses

| Service | Component | Cost |
|---------|-----------|------|
| **Video Analysis** | Deepgram + GPT-4o Mini | ~$13.30 |
| **Presentation Analysis** | GPT-4o Mini + Vision | ~$5.00 |
| **Grammar Check** | LanguageTool | ~$0.50 |
| **Subtotal (AI)** | | **~$19/100 analyses** |

### Monthly Infrastructure

| Component | Provider | Cost |
|-----------|----------|------|
| Cloud Hosting | AWS/Render | $50-100 |
| Redis | Managed | $10-20 |
| Database | PostgreSQL | $15-25 |
| Storage (files) | S3/Cloudflare R2 | $5-15 |
| **Subtotal (Infra)** | | **~$80-160** |

### Total Monthly Cost (Both Services)

| Volume | AI Costs | Infrastructure | **Total** |
|--------|----------|----------------|-----------|
| 100 each/mo | ~$19 | ~$80 | **~$100/mo** |
| 500 each/mo | ~$95 | ~$120 | **~$215/mo** |
| 1000 each/mo | ~$190 | ~$160 | **~$350/mo** |

---

## Why This Stack?

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Deepgram** | Transcription | Fastest, best price-to-accuracy ratio |
| **DeepFace** | Facial | Production-quality, zero cost |
| **MediaPipe** | Pose | Google-backed, industry standard |
| **GPT-4o Mini** | NLP | Best quality-to-cost for content analysis |

---

## Future Scale Options

| When | Upgrade | Benefit | Added Cost |
|------|---------|---------|------------|
| Premium tier | Hume AI | 48 voice emotions | +$0.14/min |
| Enterprise | AssemblyAI | Speaker diarization | +$0.01/min |
| High accuracy | GPT-4o | Better content analysis | +$2.35/1M tokens |

---

## Summary

### Two Services

| Service | Input | Output | Cost/Analysis |
|---------|-------|--------|---------------|
| **Video Analysis** | MP4, MOV, etc. | Voice, face, pose, content scores | ~$0.13 |
| **Presentation Analysis** | PPT, PDF | Content, design, structure scores | ~$0.05 |

### Key Metrics

| Metric | Video | Presentation |
|--------|-------|--------------|
| **Processing Time** | 30-60 sec | 5-15 sec |
| **Accuracy** | 90-96% | 85-95% |
| **Monthly Cost (500 each)** | ~$215 combined | |

### Technology Summary

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Celery, Redis, PostgreSQL |
| **Video AI** | Deepgram, DeepFace, MediaPipe, GPT-4o Mini |
| **Document AI** | PyMuPDF, python-pptx, GPT-4o Mini/Vision |
| **Hosting** | AWS / GCP / Render |

---

*January 2026*

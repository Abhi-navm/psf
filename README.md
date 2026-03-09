# Sales Pitch Analyzer

AI-powered sales pitch video analyzer that detects negative patterns in gestures, voice, and content.

## Features

- **Speech Transcription**: Whisper-based speech-to-text with timestamps
- **Voice Analysis**: Detect monotone voice, uncertain tone, speaking pace issues
- **Facial Expression Analysis**: Detect frowning, lack of smile, anxiety
- **Body Language Analysis**: Detect crossed arms, fidgeting, poor posture
- **Content Analysis**: Detect filler words, weak phrases, negative language
- **Comprehensive Reports**: Timestamped feedback with improvement suggestions

## Tech Stack

### Backend
- Python 3.11 + FastAPI + Celery + Redis
- SQLite (development) / Supabase (production)
- Local storage / Cloudflare R2

### AI Models (100% Free/Local)
- **Whisper** (OpenAI) - Speech transcription
- **Ollama + Llama 3 8B** - Content analysis
- **SpeechBrain + Librosa** - Voice/emotion analysis
- **DeepFace** - Facial expression detection
- **MediaPipe** - Body pose detection

### Frontend (Coming Soon)
- Next.js 14 + TypeScript + Tailwind CSS

### Desktop (Coming Soon)
- Electron

## Quick Start

### Prerequisites

1. **Python 3.11+**
2. **Redis** (for task queue)
3. **FFmpeg** (for video processing)
4. **Ollama** (for LLM analysis)

### Installation

```bash
# Clone the repository
cd response_detection

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
cd backend
pip install -r requirements.txt

# Copy environment file
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# Edit .env with your settings
```

### Setup Ollama (for content analysis)

```bash
# Install Ollama from https://ollama.ai
# Then pull the Llama 3 model:
ollama pull llama3:8b
```

### Quick Start (Single Command)

```powershell
cd response_detection
.\start.ps1
```

This starts Redis, Backend, Celery, and Frontend automatically in separate windows.

### Manual Start

1. **Start Redis** (required for Celery):
```bash
# Using Docker:
docker run -d -p 6379:6379 redis:alpine

# Or install Redis locally
```

2. **Start the API server**:
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. **Start Celery worker** (in a new terminal):
```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info -Q default,video,analysis
```

4. **Access the API**:
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## API Endpoints

### Videos
- `POST /api/v1/videos/upload` - Upload a video
- `GET /api/v1/videos` - List all videos
- `GET /api/v1/videos/{id}` - Get video details
- `DELETE /api/v1/videos/{id}` - Delete a video

### Analyses
- `POST /api/v1/analyses` - Start analysis for a video
- `GET /api/v1/analyses/{id}` - Get full analysis results
- `GET /api/v1/analyses/{id}/status` - Get analysis status
- `GET /api/v1/analyses/{id}/transcription` - Get transcription
- `GET /api/v1/analyses/{id}/voice` - Get voice analysis
- `GET /api/v1/analyses/{id}/facial` - Get facial analysis
- `GET /api/v1/analyses/{id}/pose` - Get pose analysis
- `GET /api/v1/analyses/{id}/content` - Get content analysis
- `GET /api/v1/analyses/{id}/report` - Get final report
- `DELETE /api/v1/analyses/{id}` - Cancel analysis

## Project Structure

```
response_detection/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── videos.py      # Video upload endpoints
│   │   │   │   ├── analyses.py    # Analysis endpoints
│   │   │   │   └── health.py      # Health check
│   │   │   └── schemas.py         # Pydantic models
│   │   ├── analyzers/
│   │   │   ├── transcription.py   # Whisper transcription
│   │   │   ├── voice.py           # Voice/emotion analysis
│   │   │   ├── facial.py          # Facial expression analysis
│   │   │   ├── pose.py            # Body pose analysis
│   │   │   ├── content.py         # Content/LLM analysis
│   │   │   └── report_generator.py
│   │   ├── core/
│   │   │   ├── config.py          # Settings
│   │   │   ├── logging.py         # Logging setup
│   │   │   └── exceptions.py      # Custom exceptions
│   │   ├── db/
│   │   │   ├── database.py        # SQLAlchemy setup
│   │   │   └── models.py          # Database models
│   │   ├── tasks/
│   │   │   ├── celery_app.py      # Celery configuration
│   │   │   ├── video_tasks.py     # Video processing tasks
│   │   │   └── analysis_tasks.py  # Analysis tasks
│   │   └── main.py                # FastAPI app
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.example
├── frontend/                       # Coming soon
├── desktop/                        # Coming soon
└── README.md
```

## Development

```bash
# Run tests
pytest

# Format code
black app/
ruff check app/ --fix

# Type checking
mypy app/
```

## License

MIT License

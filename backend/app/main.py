"""
Sales Pitch Analyzer - FastAPI Application
Main application entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.exceptions import SalesPitchAnalyzerError
from app.db.database import init_db, close_db
from app.api.routes import videos_router, analyses_router, health_router, golden_pitch_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging()
    logger.info("Starting Sales Pitch Analyzer API...")
    
    # Create data directories
    data_dir = Path(settings.local_storage_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "videos").mkdir(exist_ok=True)
    (data_dir / "analyses").mkdir(exist_ok=True)
    (data_dir / "temp").mkdir(exist_ok=True)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    logger.info(f"API ready. Environment: {settings.environment}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Sales Pitch Analyzer API",
    description="""
    AI-powered sales pitch video analyzer for detecting negative patterns.
    
    ## Features
    
    - **Video Upload**: Upload sales pitch videos for analysis
    - **Speech Transcription**: Whisper-based speech-to-text
    - **Voice Analysis**: Detect monotone, pace issues, uncertainty
    - **Facial Analysis**: Detect negative expressions, lack of engagement
    - **Body Language**: Detect crossed arms, fidgeting, poor posture
    - **Content Analysis**: Detect filler words, weak phrases, negative language
    - **Comprehensive Reports**: Timestamped feedback with improvement suggestions
    
    ## Tech Stack
    
    - FastAPI + Celery + Redis (async processing)
    - Whisper (transcription)
    - SpeechBrain + Librosa (voice analysis)
    - DeepFace (facial expressions)
    - MediaPipe (body pose)
    - Ollama + Llama 3 (content analysis)
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(SalesPitchAnalyzerError)
async def sales_pitch_error_handler(request: Request, exc: SalesPitchAnalyzerError):
    """Handle custom application errors."""
    logger.error(f"Application error: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.message,
            "code": exc.code,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred",
            "code": "INTERNAL_ERROR",
            "details": {"message": str(exc)} if settings.debug else {},
        },
    )


# Include routers
app.include_router(health_router)
app.include_router(videos_router, prefix="/api/v1")
app.include_router(analyses_router, prefix="/api/v1")
app.include_router(golden_pitch_router, prefix="/api/v1")


# Development server entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )

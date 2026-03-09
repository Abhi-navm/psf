"""
Health check and system status endpoints.
"""

from fastapi import APIRouter, BackgroundTasks
import redis.asyncio as redis

from app.core.config import settings
from app.api.schemas import HealthResponse

router = APIRouter(tags=["health"])

# Track warming status
_warming_status = {
    "whisper": False,
    "sentence_transformer": False,
    "deepface": False,
    "ollama": False,
}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of all services.
    """
    services = {}
    
    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        services["redis"] = "healthy"
        await r.close()
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    # Check database
    try:
        from app.db.database import async_session_maker
        from sqlalchemy import text
        
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)}"
    
    # Check Ollama
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                services["ollama"] = "healthy"
            else:
                services["ollama"] = f"unhealthy: status {response.status_code}"
    except Exception as e:
        services["ollama"] = f"unavailable: {str(e)}"
    
    return HealthResponse(
        status="ok" if services.get("database") == "healthy" else "degraded",
        environment=settings.environment,
        version="0.1.0",
        services=services,
    )


@router.post("/warm")
async def warm_models(background_tasks: BackgroundTasks):
    """
    Pre-warm ML models to eliminate cold start latency.
    
    Call this endpoint after deployment to load models into GPU memory.
    Warming happens in the background and typically takes 30-60 seconds.
    """
    background_tasks.add_task(_warm_all_models)
    return {
        "status": "warming",
        "message": "Model warming started in background. Check /warm/status for progress.",
    }


@router.get("/warm/status")
async def warm_status():
    """Check the status of model warming."""
    all_warmed = all(_warming_status.values())
    return {
        "status": "ready" if all_warmed else "warming",
        "models": _warming_status,
    }


def _warm_all_models():
    """Load all ML models into memory."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Warm Whisper (faster-whisper)
    try:
        logger.info("Warming Whisper model...")
        from app.analyzers.transcription import WhisperTranscriber
        transcriber = WhisperTranscriber()
        _ = transcriber.model  # Force load
        _warming_status["whisper"] = True
        logger.info("Whisper model warmed")
    except Exception as e:
        logger.error(f"Failed to warm Whisper: {e}")
    
    # Warm sentence transformer on GPU
    try:
        logger.info("Warming Sentence Transformer on GPU...")
        from sentence_transformers import SentenceTransformer
        device = settings.embedding_device
        model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
        # Do a test encoding
        model.encode(["test sentence"])
        _warming_status["sentence_transformer"] = True
        logger.info(f"Sentence Transformer warmed on {device}")
    except Exception as e:
        logger.error(f"Failed to warm Sentence Transformer: {e}")
    
    # Warm DeepFace
    try:
        logger.info("Warming DeepFace...")
        from deepface import DeepFace
        import numpy as np
        # Create a dummy image and run analysis to load models
        dummy_img = np.zeros((224, 224, 3), dtype=np.uint8)
        try:
            DeepFace.analyze(dummy_img, actions=['emotion'], enforce_detection=False, silent=True)
        except:
            pass  # Expected to fail on dummy image, but models are loaded
        _warming_status["deepface"] = True
        logger.info("DeepFace warmed")
    except Exception as e:
        logger.error(f"Failed to warm DeepFace: {e}")
    
    # Warm Ollama (pull model if needed)
    try:
        logger.info("Warming Ollama...")
        import httpx
        with httpx.Client(timeout=30) as client:
            # Check if model exists
            response = client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": "Hello", "stream": False},
            )
            if response.status_code == 200:
                _warming_status["ollama"] = True
                logger.info("Ollama warmed")
    except Exception as e:
        logger.error(f"Failed to warm Ollama: {e}")


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Sales Pitch Analyzer API",
        "version": "0.1.0",
        "docs": "/docs",
    }

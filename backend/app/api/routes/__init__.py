"""API routes module."""

from app.api.routes.videos import router as videos_router
from app.api.routes.analyses import router as analyses_router
from app.api.routes.health import router as health_router
from app.api.routes.golden_pitch import router as golden_pitch_router

__all__ = ["videos_router", "analyses_router", "health_router", "golden_pitch_router"]

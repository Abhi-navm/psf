"""
Golden Pitch Deck endpoints for managing and processing reference videos.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.logging import logger
from app.db.database import get_db
from app.db.models import Video, GoldenPitchDeck
from app.api.schemas import (
    GoldenPitchDeckCreate,
    GoldenPitchDeckUpdate,
    GoldenPitchDeckResponse,
    GoldenPitchDeckListResponse,
    ErrorResponse,
)
from app.tasks.golden_pitch_tasks import process_golden_pitch_deck

router = APIRouter(prefix="/golden-pitch-decks", tags=["golden-pitch-decks"])


@router.post(
    "",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_golden_pitch_deck(
    request: GoldenPitchDeckCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new golden pitch deck from an uploaded video.
    
    This will:
    1. Create the golden pitch deck record
    2. Queue it for processing (extract reference metrics)
    3. Optionally set it as the active reference
    """
    # Verify video exists
    video_query = select(Video).where(Video.id == request.video_id)
    result = await db.execute(video_query)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Video {request.video_id} not found",
                "code": "VIDEO_NOT_FOUND",
            },
        )
    
    # If setting as active, deactivate other golden pitch decks
    if request.set_as_active:
        await db.execute(
            update(GoldenPitchDeck).values(is_active=False)
        )
    
    # Create golden pitch deck record
    golden_deck = GoldenPitchDeck(
        video_id=request.video_id,
        name=request.name,
        description=request.description,
        is_active=request.set_as_active,
        is_processed=False,
    )
    db.add(golden_deck)
    await db.commit()
    await db.refresh(golden_deck)
    
    logger.info(f"Created golden pitch deck {golden_deck.id} from video {request.video_id}")
    
    # Queue for processing
    process_golden_pitch_deck.delay(
        golden_pitch_deck_id=golden_deck.id,
        video_id=request.video_id,
        video_path=video.file_path,
    )
    
    return golden_deck


@router.get(
    "",
    response_model=GoldenPitchDeckListResponse,
)
async def list_golden_pitch_decks(
    active_only: bool = Query(False, description="Only return active golden pitch decks"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all golden pitch decks.
    """
    query = select(GoldenPitchDeck).order_by(GoldenPitchDeck.created_at.desc())
    
    if active_only:
        query = query.where(GoldenPitchDeck.is_active == True)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return GoldenPitchDeckListResponse(
        items=list(items),
        total=len(items),
    )


@router.get(
    "/active",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_active_golden_pitch_deck(
    db: AsyncSession = Depends(get_db),
):
    """
    Get the currently active golden pitch deck.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.is_active == True)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No active golden pitch deck found",
                "code": "NO_ACTIVE_GOLDEN_DECK",
            },
        )
    
    return golden_deck


@router.get(
    "/{golden_pitch_deck_id}",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_golden_pitch_deck(
    golden_pitch_deck_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific golden pitch deck by ID.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.id == golden_pitch_deck_id)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Golden pitch deck {golden_pitch_deck_id} not found",
                "code": "GOLDEN_DECK_NOT_FOUND",
            },
        )
    
    return golden_deck


@router.patch(
    "/{golden_pitch_deck_id}",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def update_golden_pitch_deck(
    golden_pitch_deck_id: str,
    request: GoldenPitchDeckUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a golden pitch deck.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.id == golden_pitch_deck_id)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Golden pitch deck {golden_pitch_deck_id} not found",
                "code": "GOLDEN_DECK_NOT_FOUND",
            },
        )
    
    # If setting as active, deactivate others
    if request.is_active is True:
        await db.execute(
            update(GoldenPitchDeck).where(
                GoldenPitchDeck.id != golden_pitch_deck_id
            ).values(is_active=False)
        )
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(golden_deck, field, value)
    
    golden_deck.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(golden_deck)
    
    return golden_deck


@router.delete(
    "/{golden_pitch_deck_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def delete_golden_pitch_deck(
    golden_pitch_deck_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a golden pitch deck.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.id == golden_pitch_deck_id)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Golden pitch deck {golden_pitch_deck_id} not found",
                "code": "GOLDEN_DECK_NOT_FOUND",
            },
        )
    
    await db.delete(golden_deck)
    await db.commit()
    
    logger.info(f"Deleted golden pitch deck {golden_pitch_deck_id}")


@router.post(
    "/{golden_pitch_deck_id}/reprocess",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def reprocess_golden_pitch_deck(
    golden_pitch_deck_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Reprocess a golden pitch deck to extract reference metrics.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.id == golden_pitch_deck_id)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Golden pitch deck {golden_pitch_deck_id} not found",
                "code": "GOLDEN_DECK_NOT_FOUND",
            },
        )
    
    # Get video
    video_query = select(Video).where(Video.id == golden_deck.video_id)
    video_result = await db.execute(video_query)
    video = video_result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Video {golden_deck.video_id} not found",
                "code": "VIDEO_NOT_FOUND",
            },
        )
    
    # Reset processing status
    golden_deck.is_processed = False
    golden_deck.processing_error = None
    golden_deck.updated_at = datetime.utcnow()
    await db.commit()
    
    # Queue for reprocessing
    process_golden_pitch_deck.delay(
        golden_pitch_deck_id=golden_deck.id,
        video_id=golden_deck.video_id,
        video_path=video.file_path,
    )
    
    await db.refresh(golden_deck)
    
    logger.info(f"Queued golden pitch deck {golden_pitch_deck_id} for reprocessing")
    
    return golden_deck


@router.post(
    "/{golden_pitch_deck_id}/set-active",
    response_model=GoldenPitchDeckResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def set_active_golden_pitch_deck(
    golden_pitch_deck_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Set a golden pitch deck as the active reference.
    """
    query = select(GoldenPitchDeck).where(GoldenPitchDeck.id == golden_pitch_deck_id)
    result = await db.execute(query)
    golden_deck = result.scalar_one_or_none()
    
    if not golden_deck:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Golden pitch deck {golden_pitch_deck_id} not found",
                "code": "GOLDEN_DECK_NOT_FOUND",
            },
        )
    
    # Deactivate all other golden pitch decks
    await db.execute(
        update(GoldenPitchDeck).where(
            GoldenPitchDeck.id != golden_pitch_deck_id
        ).values(is_active=False)
    )
    
    # Activate this one
    golden_deck.is_active = True
    golden_deck.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(golden_deck)
    
    logger.info(f"Set golden pitch deck {golden_pitch_deck_id} as active")
    
    return golden_deck

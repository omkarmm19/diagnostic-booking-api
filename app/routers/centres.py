import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticCentre, DiagnosticTest, User
from app.db.session import get_db
from app.schemas.centres import (
    CentreCreate,
    CentreOut,
    PaginatedCentres,
    PaginatedTests,
    TestCreate,
    TestOut,
)
from app.services.auth import get_current_user
from app.services.cache import get_cached, set_cached

logger = logging.getLogger(__name__)
router = APIRouter()

CENTRE_CACHE_TTL = 60  # seconds


@router.get("/", response_model=PaginatedCentres)
async def list_centres(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"centres:page:{page}:size:{page_size}"
    cached = await get_cached(cache_key)
    if cached:
        return PaginatedCentres(**json.loads(cached))

    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(DiagnosticCentre))
    total = total_result.scalar_one()

    result = await db.execute(select(DiagnosticCentre).offset(offset).limit(page_size))
    centres = result.scalars().all()

    out = PaginatedCentres(
        total=total,
        page=page,
        page_size=page_size,
        items=[CentreOut.model_validate(c) for c in centres],
    )
    await set_cached(cache_key, out.model_dump_json(), ttl=CENTRE_CACHE_TTL)
    return out


@router.get("/{centre_id}", response_model=CentreOut)
async def get_centre(centre_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cache_key = f"centre:{centre_id}"
    cached = await get_cached(cache_key)
    if cached:
        return CentreOut(**json.loads(cached))

    result = await db.execute(select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id))
    centre = result.scalar_one_or_none()
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    out = CentreOut.model_validate(centre)
    await set_cached(cache_key, out.model_dump_json(), ttl=CENTRE_CACHE_TTL)
    return out


@router.get("/{centre_id}/tests", response_model=PaginatedTests)
async def list_tests_for_centre(
    centre_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # verify centre exists
    c_result = await db.execute(select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id))
    if not c_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    offset = (page - 1) * page_size
    total_result = await db.execute(
        select(func.count()).select_from(DiagnosticTest).where(DiagnosticTest.centre_id == centre_id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(DiagnosticTest).where(DiagnosticTest.centre_id == centre_id).offset(offset).limit(page_size)
    )
    tests = result.scalars().all()

    return PaginatedTests(
        total=total,
        page=page,
        page_size=page_size,
        items=[TestOut.model_validate(t) for t in tests],
    )


@router.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
async def create_centre(
    body: CentreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    centre = DiagnosticCentre(name=body.name, location=body.location)
    db.add(centre)
    await db.commit()
    await db.refresh(centre)
    logger.info("centre created", extra={"centre_id": str(centre.id), "by": str(current_user.id)})
    return centre


@router.post("/{centre_id}/tests", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_test(
    centre_id: uuid.UUID,
    body: TestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c_result = await db.execute(select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id))
    if not c_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    test = DiagnosticTest(name=body.name, price=body.price, centre_id=centre_id)
    db.add(test)
    await db.commit()
    await db.refresh(test)
    logger.info("test created", extra={"test_id": str(test.id), "centre_id": str(centre_id)})
    return test

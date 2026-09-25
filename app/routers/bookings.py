import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, BookingStatus, DiagnosticCentre, DiagnosticTest, User
from app.db.session import get_db
from app.schemas.bookings import BookingCreate, BookingOut, PaginatedBookings
from app.services.auth import get_current_user
from app.services.booking import assert_transition

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify test exists
    test_result = await db.execute(select(DiagnosticTest).where(DiagnosticTest.id == body.test_id))
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic test not found")

    # Verify the test belongs to the requested centre
    if test.centre_id != body.centre_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested test is not offered at the specified centre",
        )

    # Verify centre exists (belt-and-suspenders after the FK check above)
    centre_result = await db.execute(select(DiagnosticCentre).where(DiagnosticCentre.id == body.centre_id))
    if not centre_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")

    booking = Booking(
        user_id=current_user.id,
        test_id=body.test_id,
        centre_id=body.centre_id,
        appointment_datetime=body.appointment_datetime,
        amount=test.price,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    logger.info("booking created", extra={"booking_id": str(booking.id), "user_id": str(current_user.id)})
    return booking


@router.get("/", response_model=PaginatedBookings)
async def list_bookings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    base_q = select(Booking).where(Booking.user_id == current_user.id)

    total_result = await db.execute(
        select(func.count()).select_from(Booking).where(Booking.user_id == current_user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(base_q.order_by(Booking.created_at.desc()).offset(offset).limit(page_size))
    bookings = result.scalars().all()

    return PaginatedBookings(
        total=total,
        page=page,
        page_size=page_size,
        items=[BookingOut.model_validate(b) for b in bookings],
    )


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    return booking


@router.patch("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    assert_transition(booking.status, BookingStatus.CANCELLED)

    booking.status = BookingStatus.CANCELLED
    await db.commit()
    await db.refresh(booking)
    logger.info("booking cancelled", extra={"booking_id": str(booking_id)})
    return booking

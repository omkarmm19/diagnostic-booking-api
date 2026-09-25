import logging
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, BookingStatus, Payment, PaymentStatus, WebhookEvent
from app.db.session import get_db
from app.limiter import limiter
from app.schemas.payments import PaymentCreate, PaymentOut, WebhookPayload, WebhookResponse
from app.services.auth import get_current_user
from app.services.booking import assert_transition

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=PaymentOut)
@limiter.limit("30/minute")
async def process_payment(
    request: Request,
    body: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == body.booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    # Guard against re-processing an already-settled booking
    assert_transition(booking.status, BookingStatus.CONFIRMED)  # raises 400 if not PENDING

    # Simulate payment outcome — controllable via force_result for deterministic tests
    if body.force_result == "success":
        success = True
    elif body.force_result == "fail":
        success = False
    else:
        success = random.random() < 0.8  # 80% success rate by default

    payment_status = PaymentStatus.SUCCESS if success else PaymentStatus.FAILED
    new_booking_status = BookingStatus.CONFIRMED if success else BookingStatus.FAILED
    provider_ref = f"sim-{uuid.uuid4().hex[:12]}"

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=payment_status,
        provider_ref=provider_ref,
    )
    booking.status = new_booking_status
    db.add(payment)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A payment already exists for this booking",
        )

    await db.refresh(payment)
    logger.info(
        "payment processed",
        extra={
            "payment_id": str(payment.id),
            "booking_id": str(booking.id),
            "status": payment_status,
        },
    )
    return payment


@router.post("/webhook/", response_model=WebhookResponse)
@limiter.limit("60/minute")
async def payment_webhook(
    request: Request,
    body: WebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Idempotent webhook handler. The UNIQUE constraint on webhook_events.event_id
    is our source of truth — we INSERT first and catch the IntegrityError rather
    than doing a SELECT-then-INSERT (which has a TOCTOU race).
    """
    if body.status not in ("SUCCESS", "FAILED"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status must be SUCCESS or FAILED")

    result = await db.execute(select(Booking).where(Booking.id == body.booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    new_booking_status = BookingStatus.CONFIRMED if body.status == "SUCCESS" else BookingStatus.FAILED

    event = WebhookEvent(
        event_id=body.event_id,
        booking_id=body.booking_id,
        status=body.status,
    )
    db.add(event)

    # Only apply the state change if the booking is still in PENDING — a
    # webhook arriving after the booking was already settled just records
    # the event without changing anything further.
    if booking.status == BookingStatus.PENDING:
        booking.status = new_booking_status

    try:
        await db.commit()
    except IntegrityError:
        # The unique constraint fired — this event_id was already processed.
        await db.rollback()
        logger.info("duplicate webhook ignored", extra={"event_id": body.event_id})
        return WebhookResponse(event_id=body.event_id, result="duplicate_ignored")

    logger.info(
        "webhook processed",
        extra={"event_id": body.event_id, "booking_id": str(body.booking_id), "status": body.status},
    )
    return WebhookResponse(event_id=body.event_id, result="processed")

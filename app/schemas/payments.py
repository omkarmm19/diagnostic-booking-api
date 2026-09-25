import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.db.models import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: uuid.UUID
    # Optional: pass force_result="success"/"fail" in tests to control outcome
    force_result: str | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    provider_ref: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    event_id: str
    booking_id: uuid.UUID
    status: str  # "SUCCESS" or "FAILED"


class WebhookResponse(BaseModel):
    event_id: str
    result: str  # "processed" or "duplicate_ignored"

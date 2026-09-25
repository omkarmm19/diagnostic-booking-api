import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.db.models import BookingStatus


class BookingCreate(BaseModel):
    test_id: uuid.UUID
    centre_id: uuid.UUID
    appointment_datetime: datetime

    @field_validator("appointment_datetime")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        # Make naive datetimes UTC for comparison
        if v.tzinfo is None:
            from datetime import timezone as tz
            v = v.replace(tzinfo=tz.utc)
        if v <= now:
            raise ValueError("appointment_datetime must be in the future")
        return v


class BookingOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    test_id: uuid.UUID
    centre_id: uuid.UUID
    appointment_datetime: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedBookings(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[BookingOut]

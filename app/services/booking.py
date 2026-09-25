from fastapi import HTTPException, status

from app.db.models import BookingStatus

# Allowed state transitions: {current_status: [allowed_next_statuses]}
VALID_TRANSITIONS: dict[BookingStatus, list[BookingStatus]] = {
    BookingStatus.PENDING: [BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED],
    BookingStatus.CONFIRMED: [],
    BookingStatus.FAILED: [],
    BookingStatus.CANCELLED: [],
}


def assert_transition(current: BookingStatus, target: BookingStatus) -> None:
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition booking from {current} to {target}",
        )

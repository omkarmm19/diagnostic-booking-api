"""
Booking, payment, and webhook integration tests.

Helper functions at the top keep the test bodies focused on assertions
rather than setup boilerplate.
"""

import uuid

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/auth/signup", json={
        "email": email, "password": "testpass123", "full_name": "Test User"
    })
    resp = await client.post("/auth/login", json={"email": email, "password": "testpass123"})
    return resp.json()["access_token"]


async def _create_centre_and_test(client: AsyncClient, token: str) -> tuple[str, str, float]:
    centre_resp = await client.post(
        "/centres/",
        json={"name": "City Lab", "location": "Mumbai"},
        headers={"Authorization": f"Bearer {token}"},
    )
    centre_id = centre_resp.json()["id"]

    test_resp = await client.post(
        f"/centres/{centre_id}/tests",
        json={"name": "CBC", "price": 350.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    test_id = test_resp.json()["id"]
    price = test_resp.json()["price"]
    return centre_id, test_id, float(price)


# ---- Booking flow ----

@pytest.mark.asyncio
async def test_create_booking(client: AsyncClient):
    token = await _register_and_login(client, "booking1@example.com")
    centre_id, test_id, price = await _create_centre_and_test(client, token)

    resp = await client.post(
        "/bookings/",
        json={
            "test_id": test_id,
            "centre_id": centre_id,
            "appointment_datetime": "2030-01-15T10:00:00Z",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert float(data["amount"]) == price


@pytest.mark.asyncio
async def test_booking_nonexistent_test(client: AsyncClient):
    token = await _register_and_login(client, "booking2@example.com")
    centre_resp = await client.post(
        "/centres/",
        json={"name": "Lab X", "location": "Delhi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    centre_id = centre_resp.json()["id"]

    resp = await client.post(
        "/bookings/",
        json={
            "test_id": str(uuid.uuid4()),
            "centre_id": centre_id,
            "appointment_datetime": "2030-02-01T09:00:00Z",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_booking_past_datetime(client: AsyncClient):
    token = await _register_and_login(client, "booking3@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    resp = await client.post(
        "/bookings/",
        json={
            "test_id": test_id,
            "centre_id": centre_id,
            "appointment_datetime": "2020-01-01T10:00:00Z",  # in the past
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cannot_view_other_users_booking(client: AsyncClient):
    token_a = await _register_and_login(client, "usera@example.com")
    token_b = await _register_and_login(client, "userb@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token_a)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-03-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    booking_id = booking_resp.json()["id"]

    resp = await client.get(f"/bookings/{booking_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_booking(client: AsyncClient):
    token = await _register_and_login(client, "cancel1@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-04-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    resp = await client.patch(f"/bookings/{booking_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cannot_cancel_already_cancelled(client: AsyncClient):
    token = await _register_and_login(client, "cancel2@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-05-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    await client.patch(f"/bookings/{booking_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    # second cancel should fail
    resp = await client.patch(f"/bookings/{booking_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_booking_not_found(client: AsyncClient):
    token = await _register_and_login(client, "notfound@example.com")
    resp = await client.get(f"/bookings/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


# ---- Payment flow ----

@pytest.mark.asyncio
async def test_payment_success(client: AsyncClient):
    token = await _register_and_login(client, "pay1@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-06-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    resp = await client.post(
        "/payments/",
        json={"booking_id": booking_id, "force_result": "success"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_payment_failure(client: AsyncClient):
    token = await _register_and_login(client, "pay2@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-07-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    resp = await client.post(
        "/payments/",
        json={"booking_id": booking_id, "force_result": "fail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"


@pytest.mark.asyncio
async def test_payment_on_confirmed_booking(client: AsyncClient):
    """Paying a booking that's already CONFIRMED should 400."""
    token = await _register_and_login(client, "pay3@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-08-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    await client.post(
        "/payments/",
        json={"booking_id": booking_id, "force_result": "success"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # try again
    resp = await client.post(
        "/payments/",
        json={"booking_id": booking_id, "force_result": "success"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_payment_on_cancelled_booking(client: AsyncClient):
    token = await _register_and_login(client, "pay4@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-09-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    await client.patch(f"/bookings/{booking_id}/cancel", headers={"Authorization": f"Bearer {token}"})

    resp = await client.post(
        "/payments/",
        json={"booking_id": booking_id, "force_result": "success"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_payment_invalid_booking_id(client: AsyncClient):
    token = await _register_and_login(client, "pay5@example.com")
    resp = await client.post(
        "/payments/",
        json={"booking_id": str(uuid.uuid4()), "force_result": "success"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---- Webhook idempotency ----

@pytest.mark.asyncio
async def test_webhook_idempotency(client: AsyncClient):
    """
    Sending the same event_id twice must:
    - Process state change only once
    - Return 200 with result=duplicate_ignored on the second call
    """
    token = await _register_and_login(client, "webhook1@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]
    event_id = "evt-unique-001"

    payload = {"event_id": event_id, "booking_id": booking_id, "status": "SUCCESS"}

    resp1 = await client.post("/payments/webhook/", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["result"] == "processed"

    resp2 = await client.post("/payments/webhook/", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["result"] == "duplicate_ignored"

    # Booking should still be CONFIRMED, not double-applied
    booking_status_resp = await client.get(
        f"/bookings/{booking_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert booking_status_resp.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_webhook_invalid_status(client: AsyncClient):
    token = await _register_and_login(client, "webhook2@example.com")
    centre_id, test_id, _ = await _create_centre_and_test(client, token)

    booking_resp = await client.post(
        "/bookings/",
        json={"test_id": test_id, "centre_id": centre_id, "appointment_datetime": "2030-11-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = booking_resp.json()["id"]

    resp = await client.post(
        "/payments/webhook/",
        json={"event_id": "evt-bad-status", "booking_id": booking_id, "status": "PENDING"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_webhook_invalid_booking_id(client: AsyncClient):
    resp = await client.post(
        "/payments/webhook/",
        json={"event_id": "evt-bad-booking", "booking_id": str(uuid.uuid4()), "status": "SUCCESS"},
    )
    assert resp.status_code == 404

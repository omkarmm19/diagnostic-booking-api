import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup(client: AsyncClient):
    resp = await client.post("/auth/signup", json={
        "email": "alice@example.com",
        "password": "securepass1",
        "full_name": "Alice",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    payload = {"email": "bob@example.com", "password": "password123", "full_name": "Bob"}
    await client.post("/auth/signup", json=payload)
    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient):
    resp = await client.post("/auth/signup", json={
        "email": "c@example.com",
        "password": "short",
        "full_name": "C",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/signup", json={
        "email": "dave@example.com", "password": "password123", "full_name": "Dave"
    })
    resp = await client.post("/auth/login", json={
        "email": "dave@example.com", "password": "password123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/signup", json={
        "email": "eve@example.com", "password": "password123", "full_name": "Eve"
    })
    resp = await client.post("/auth/login", json={
        "email": "eve@example.com", "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_without_token(client: AsyncClient):
    resp = await client.get("/bookings/")
    assert resp.status_code == 403  # HTTPBearer returns 403 if no credentials


@pytest.mark.asyncio
async def test_invalid_token(client: AsyncClient):
    resp = await client.get("/bookings/", headers={"Authorization": "Bearer notavalidtoken"})
    assert resp.status_code == 401

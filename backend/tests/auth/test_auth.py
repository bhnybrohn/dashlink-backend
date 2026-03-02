"""Auth module tests — registration, login, token refresh, MFA."""

import pytest
from httpx import AsyncClient


class TestRegistration:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_seller_success(self, client: AsyncClient):
        """Seller registration creates user + seller profile + returns tokens."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "amina@test.com",
                "password": "securepassword123",
                "role": "seller",
                "store_name": "Amina Beauty",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_buyer_success(self, client: AsyncClient):
        """Buyer registration creates user + returns tokens."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "kemi@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data

    async def test_register_seller_without_store_name_fails(self, client: AsyncClient):
        """Seller registration without store_name returns 400."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "seller2@test.com",
                "password": "securepassword123",
                "role": "seller",
            },
        )
        assert response.status_code == 400

    async def test_register_duplicate_email_fails(self, client: AsyncClient):
        """Duplicate email returns 409."""
        payload = {
            "email": "dup@test.com",
            "password": "securepassword123",
            "role": "buyer",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    async def test_register_weak_password_fails(self, client: AsyncClient):
        """Password shorter than 8 characters returns 422 (validation)."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@test.com",
                "password": "short",
                "role": "buyer",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(self, client: AsyncClient):
        """Correct credentials return token pair."""
        # First register
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        # Then login
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "securepassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password returns 401."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@test.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        """Non-existent email returns 401 (identical to wrong password — no enumeration)."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "noone@test.com", "password": "anypassword"},
        )
        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_success(self, client: AsyncClient):
        """Valid refresh token returns new token pair."""
        # Register to get tokens
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        refresh_token = reg.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        # New refresh token should be different (rotated)
        assert data["refresh_token"] != refresh_token

    async def test_refresh_revoked_token_fails(self, client: AsyncClient):
        """Used refresh token cannot be reused (revocation)."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "revoke@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        refresh_token = reg.json()["refresh_token"]

        # Use it once
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # Try to reuse
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401


class TestHealthCheck:
    """Test the health endpoint."""

    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

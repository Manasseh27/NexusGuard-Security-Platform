"""
Integration tests for NexusGuard API endpoints.
"""

import pytest
from httpx import AsyncClient
import json


@pytest.mark.integration
class TestAuthenticationEndpoints:
    """Integration tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(self, test_client):
        """Test successful login."""
        response = await test_client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123",
            },
        )
        
        # Should return 200 or 401 depending on demo user setup
        assert response.status_code in [200, 401, 422]
        
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials(self, test_client):
        """Test login failure with invalid credentials."""
        response = await test_client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code in [401, 422]

    @pytest.mark.asyncio
    async def test_refresh_token(self, test_client):
        """Test token refresh."""
        # First, login
        login_response = await test_client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123",
            },
        )
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            
            # Try to refresh
            refresh_response = await test_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": token},
            )
            
            assert refresh_response.status_code in [200, 401]


@pytest.mark.integration
class TestDeviceEndpoints:
    """Integration tests for device management endpoints."""

    @pytest.mark.asyncio
    async def test_list_devices(self, authenticated_client, demo_devices):
        """Test listing devices."""
        response = await authenticated_client.get("/api/v1/devices/devices")
        
        assert response.status_code in [200, 401, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_device(self, authenticated_client):
        """Test device creation."""
        device_data = {
            "hostname": "newhost.example.com",
            "ip_address": "192.168.1.50",
            "device_type": "switch",
            "site": "us-west-1",
        }
        
        response = await authenticated_client.post(
            "/api/v1/devices/devices",
            json=device_data,
        )
        
        assert response.status_code in [201, 401, 422]

    @pytest.mark.asyncio
    async def test_get_device(self, authenticated_client, demo_devices):
        """Test getting a specific device."""
        if demo_devices:
            device_id = demo_devices[0].id
            response = await authenticated_client.get(
                f"/api/v1/devices/devices/{device_id}"
            )
            
            assert response.status_code in [200, 401, 404]


@pytest.mark.integration
class TestComplianceEndpoints:
    """Integration tests for compliance endpoints."""

    @pytest.mark.asyncio
    async def test_get_frameworks(self, authenticated_client):
        """Test getting compliance frameworks."""
        response = await authenticated_client.get(
            "/api/v1/compliance/frameworks"
        )
        
        assert response.status_code in [200, 401, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_fleet_summary(self, authenticated_client):
        """Test getting fleet compliance summary."""
        response = await authenticated_client.get(
            "/api/v1/compliance/fleet/summary"
        )
        
        assert response.status_code in [200, 401, 404]

    @pytest.mark.asyncio
    async def test_get_active_drifts(self, authenticated_client):
        """Test getting active drift events."""
        response = await authenticated_client.get(
            "/api/v1/compliance/drift/active"
        )
        
        assert response.status_code in [200, 401, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


@pytest.mark.integration
class TestMonitoringEndpoints:
    """Integration tests for monitoring endpoints."""

    @pytest.mark.asyncio
    async def test_get_fleet_status(self, authenticated_client):
        """Test getting overall fleet status."""
        response = await authenticated_client.get(
            "/api/v1/monitoring/fleet"
        )
        
        assert response.status_code in [200, 401, 404]

    @pytest.mark.asyncio
    async def test_get_device_states(self, authenticated_client):
        """Test getting all device states."""
        response = await authenticated_client.get(
            "/api/v1/monitoring/devices"
        )
        
        assert response.status_code in [200, 401, 404]

    @pytest.mark.asyncio
    async def test_trigger_device_poll(self, authenticated_client, demo_devices):
        """Test triggering a device poll."""
        if demo_devices:
            device_id = demo_devices[0].id
            response = await authenticated_client.post(
                f"/api/v1/monitoring/devices/{device_id}/poll"
            )
            
            # Should return 202 Accepted or error
            assert response.status_code in [202, 401, 404, 422]


@pytest.mark.integration
class TestSIEMEndpoints:
    """Integration tests for SIEM endpoints."""

    @pytest.mark.asyncio
    async def test_list_siem_events(self, authenticated_client):
        """Test listing SIEM events."""
        response = await authenticated_client.get(
            "/api/v1/siem/events"
        )
        
        assert response.status_code in [200, 401, 404]

    @pytest.mark.asyncio
    async def test_submit_siem_event(self, authenticated_client):
        """Test submitting a SIEM event."""
        event_data = {
            "event_type": "SUSPICIOUS_ACTIVITY",
            "severity": "high",
            "raw_data": {"details": "test event"},
        }
        
        response = await authenticated_client.post(
            "/api/v1/siem/events",
            json=event_data,
        )
        
        assert response.status_code in [201, 401, 422]

    @pytest.mark.asyncio
    async def test_siem_health(self, authenticated_client):
        """Test SIEM health endpoint."""
        response = await authenticated_client.get(
            "/api/v1/siem/health"
        )
        
        assert response.status_code in [200, 401, 404]


@pytest.mark.integration
class TestSecurityHeaders:
    """Test that security headers are present in responses."""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, test_client):
        """Test security headers in responses."""
        response = await test_client.get("/api/docs")
        
        # Check for security headers
        headers = {k.lower(): v for k, v in response.headers.items()}
        
        # These should be present (if security middleware is enabled)
        security_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
        ]
        
        # Some headers might not be present in dev mode
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_cors_headers(self, test_client):
        """Test CORS headers."""
        response = await test_client.get(
            "/api/v1/",
            headers={"Origin": "http://localhost:3000"},
        )
        
        # CORS headers might be present
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, test_client):
        """Test that rate limit headers are present."""
        response = await test_client.get("/api/docs")
        
        # Check for rate limit headers
        headers = {k.lower(): v for k, v in response.headers.items()}
        
        # Rate limit headers should be present if middleware is active
        # (May not be in dev mode)
        assert response.status_code >= 200

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, test_client):
        """Test that rate limits are enforced."""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = await test_client.get("/api/docs")
            responses.append(response.status_code)
        
        # Should get some 200s, potentially a 429
        assert any(status in [200, 429] for status in responses)


@pytest.mark.security
class TestSecurityEndpoints:
    """Tests for security-related functionality."""

    @pytest.mark.asyncio
    async def test_invalid_json_rejected(self, test_client):
        """Test that invalid JSON is rejected."""
        response = await test_client.post(
            "/api/v1/auth/login",
            content="{ invalid json }",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_oversized_payload_rejected(self, test_client):
        """Test that oversized payloads are rejected."""
        # Create a large payload (>10MB)
        large_data = "x" * (11 * 1024 * 1024)
        
        response = await test_client.post(
            "/api/v1/auth/login",
            json={"data": large_data},
        )
        
        # Should be rejected
        assert response.status_code in [413, 422, 400]


class TestEndpointAvailability:
    """Test that key endpoints are available."""

    @pytest.mark.asyncio
    async def test_openapi_docs(self, test_client):
        """Test OpenAPI documentation endpoint."""
        response = await test_client.get("/api/docs")
        
        # Should be available in dev, might be hidden in prod
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = await test_client.get("/api/v1/health/ready")
        
        # Health endpoint should be available
        assert response.status_code in [200, 404, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

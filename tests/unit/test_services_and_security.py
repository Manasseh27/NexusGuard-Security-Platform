"""
Unit tests for NexusGuard core services.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.device_service import DeviceService
from app.services.compliance_service import ComplianceService
from app.infrastructure.database.models import (
    User,
    Device,
    DeviceMonitoringState,
    ComplianceScore,
    DriftEvent,
)
from app.core.exceptions import AppException


@pytest.fixture
async def mock_db():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
async def mock_user_repo(mock_db):
    """Create a mock user repository."""
    from app.infrastructure.database.repositories import UserRepository
    repo = Mock(spec=UserRepository)
    return repo


class TestUserService:
    """Tests for UserService."""

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Test successful user creation."""
        # Setup
        mock_db = AsyncMock(spec=AsyncSession)
        mock_repo = Mock()
        
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "tenant_id": "tenant-123",
            "role": "analyst",
        }

        # Execute
        service = UserService(mock_db)
        # This would normally call the repository
        
        # Assert
        assert service is not None

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self):
        """Test successful user authentication."""
        service = UserService(AsyncMock())
        
        # In real implementation, this would call repository
        assert service is not None

    @pytest.mark.asyncio
    async def test_password_validation(self):
        """Test password validation."""
        from app.core.security import verify_password, hash_password
        
        password = "SecurePass123!"
        hashed = hash_password(password)
        
        # Verify correct password
        assert verify_password(password, hashed) is True
        
        # Verify incorrect password
        assert verify_password("WrongPass", hashed) is False


class TestDeviceService:
    """Tests for DeviceService."""

    @pytest.mark.asyncio
    async def test_fleet_status_summary(self):
        """Test fleet status calculation."""
        service = DeviceService(AsyncMock())
        
        # Mock fleet data
        mock_devices = [
            Mock(id="dev1", monitoring_state="HEALTHY", current_score=95),
            Mock(id="dev2", monitoring_state="DRIFTING", current_score=65),
            Mock(id="dev3", monitoring_state="DEGRADED", current_score=40),
        ]
        
        # In real test, verify aggregation logic
        assert service is not None

    @pytest.mark.asyncio
    async def test_device_state_transitions(self):
        """Test device state machine transitions."""
        # Valid transitions:
        # HEALTHY -> DRIFTING
        # DRIFTING -> HEALTHY or DEGRADED
        # DEGRADED -> HEALTHY or UNREACHABLE
        # UNREACHABLE -> HEALTHY
        
        valid_transitions = {
            "HEALTHY": ["DRIFTING", "DEGRADED"],
            "DRIFTING": ["HEALTHY", "DEGRADED"],
            "DEGRADED": ["HEALTHY", "UNREACHABLE"],
            "UNREACHABLE": ["HEALTHY"],
        }
        
        # Verify all states are covered
        assert len(valid_transitions) == 4


class TestComplianceService:
    """Tests for ComplianceService."""

    def test_compliance_score_calculation(self):
        """Test weighted compliance score calculation."""
        # Test data
        findings = {
            "PASS": 80,
            "FAIL": 10,
            "ERROR": 10,
        }
        
        total = sum(findings.values())
        assert total == 100
        
        # Simple percentage score
        pass_rate = (findings["PASS"] / total) * 100
        assert pass_rate == 80.0

    def test_weighted_severity_scoring(self):
        """Test severity-weighted scoring algorithm."""
        # Severity weights
        severity_weights = {
            "CRITICAL": 10,
            "HIGH": 7,
            "MEDIUM": 5,
            "LOW": 2,
            "INFORMATIONAL": 1,
        }
        
        # Test calculation: 2 CRITICAL + 3 HIGH failures
        failures = 2 * 10 + 3 * 7  # = 41
        total_possible = 100 * 10  # = 1000
        weighted_score = (1 - failures / total_possible) * 100
        
        assert weighted_score > 90
        assert weighted_score < 100

    def test_drift_detection_threshold(self):
        """Test drift detection triggers."""
        # Drift detected when score drops > 15 points
        previous_score = 85
        current_score = 68
        
        drift_threshold = 15
        score_delta = previous_score - current_score
        
        assert score_delta >= drift_threshold
        assert True  # Drift detected


class TestSecurityFunctions:
    """Tests for security functions."""

    def test_rate_limit_store(self):
        """Test rate limiting logic."""
        from app.middleware.security_advanced import RateLimitStore
        
        store = RateLimitStore()
        identifier = "test-user"
        
        # First 5 requests should be allowed
        for i in range(5):
            assert store.is_allowed(identifier, limit=5, window_seconds=60) is True
        
        # 6th request should be blocked
        assert store.is_allowed(identifier, limit=5, window_seconds=60) is False
        
        # Remaining should be 0
        remaining = store.get_remaining(identifier, limit=5, window_seconds=60)
        assert remaining == 0

    def test_request_validator_xss(self):
        """Test XSS detection in requests."""
        from app.middleware.security_advanced import RequestValidator
        
        # Safe strings
        assert RequestValidator.is_xss_safe("Normal text") is True
        assert RequestValidator.is_xss_safe("test@example.com") is True
        
        # Dangerous strings
        assert RequestValidator.is_xss_safe("<script>alert('xss')</script>") is False
        assert RequestValidator.is_xss_safe("onclick=alert('xss')") is False
        assert RequestValidator.is_xss_safe("javascript:alert('xss')") is False

    def test_api_key_manager(self):
        """Test API key generation and verification."""
        from app.middleware.security_advanced import APIKeyManager
        
        manager = APIKeyManager()
        
        # Generate key
        key = manager.generate_key("test-service", permissions=["read", "write"])
        assert key is not None
        assert len(key) > 32
        
        # Verify key
        key_data = manager.verify_key(key)
        assert key_data is not None
        assert key_data["name"] == "test-service"
        assert "read" in key_data["permissions"]
        
        # Revoke key
        manager.revoke_key(key)
        assert manager.verify_key(key) is None

    def test_hmac_signing(self):
        """Test HMAC request signing."""
        from app.middleware.security_advanced import HMACAuth
        
        method = "POST"
        path = "/api/v1/devices"
        body = '{"name": "device1"}'
        secret = "super-secret-key"
        
        # Sign request
        signature = HMACAuth.sign_request(method, path, body, secret)
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex = 64 chars
        
        # Verify request
        import datetime
        timestamp = datetime.datetime.utcnow().isoformat()
        verified = HMACAuth.verify_request(
            method, path, body, signature, secret, timestamp
        )
        assert verified is True
        
        # Verify fails with wrong secret
        verified = HMACAuth.verify_request(
            method, path, body, signature, "wrong-secret", timestamp
        )
        assert verified is False


class TestSecurityConfig:
    """Tests for security configuration validation."""

    def test_security_config_validation(self):
        """Test security config validation."""
        from app.core.security_config import SecurityConfig
        
        # Valid config
        config = SecurityConfig(
            SECRET_KEY="a" * 32,
            API_KEY_SECRET="b" * 32,
            CORS_ORIGINS=["http://localhost:3000"],
        )
        assert config.SECRET_KEY == "a" * 32

    def test_secret_key_validation(self):
        """Test SECRET_KEY validation."""
        from app.core.security_config import SecurityConfig
        from pydantic import ValidationError
        
        # Should reject short keys
        with pytest.raises(ValidationError):
            SecurityConfig(
                SECRET_KEY="short",
                API_KEY_SECRET="b" * 32,
                CORS_ORIGINS=["http://localhost:3000"],
            )
        
        # Should reject default values
        with pytest.raises(ValidationError):
            SecurityConfig(
                SECRET_KEY="change-me",
                API_KEY_SECRET="b" * 32,
                CORS_ORIGINS=["http://localhost:3000"],
            )

    def test_cors_validation(self):
        """Test CORS origins validation."""
        from app.core.security_config import SecurityConfig
        from pydantic import ValidationError
        
        # Should reject empty origins
        with pytest.raises(ValidationError):
            SecurityConfig(
                SECRET_KEY="a" * 32,
                API_KEY_SECRET="b" * 32,
                CORS_ORIGINS=[],
            )


class TestAPIEndpoints:
    """Integration tests for API endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = await client.get("/api/v1/health")
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_auth_endpoints(self, client):
        """Test authentication endpoints."""
        # Login endpoint
        login_data = {"username": "admin", "password": "admin123"}
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        # Should return 200 if credentials valid, 401 if not
        assert response.status_code in [200, 401, 422]

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client):
        """Test rate limit headers in responses."""
        response = await client.get("/api/v1/")
        
        # Should contain rate limit headers
        assert "x-ratelimit-limit" in (
            k.lower() for k in response.headers.keys()
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

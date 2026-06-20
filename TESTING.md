# Testing Guide for NexusGuard Security Platform

## Overview

NexusGuard includes comprehensive testing coverage across unit tests, integration tests, and security tests.

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual components
│   ├── test_services_and_security.py    # Service and security function tests
│   └── test_compliance_engine.py        # Compliance engine tests
├── integration/                    # Integration tests
│   ├── test_api_endpoints.py           # API endpoint tests
│   └── test_database.py                # Database integration tests
└── conftest.py                     # Shared fixtures and configuration
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/unit/test_services_and_security.py
```

### Run specific test class
```bash
pytest tests/unit/test_services_and_security.py::TestUserService
```

### Run specific test
```bash
pytest tests/unit/test_services_and_security.py::TestUserService::test_create_user_success
```

### Run only integration tests
```bash
pytest -m integration
```

### Run only security tests
```bash
pytest -m security
```

### Skip slow tests
```bash
pytest -m "not slow"
```

### Run with coverage report
```bash
pytest --cov=app --cov-report=html
```

### Run with verbose output
```bash
pytest -v
```

### Run with detailed output on failures
```bash
pytest -vv --tb=long
```

## Test Categories

### Unit Tests (`tests/unit/`)

**TestUserService**
- User creation and authentication
- Password validation and hashing
- User lookup and retrieval

**TestDeviceService**
- Device lifecycle management
- Fleet status aggregation
- Device state transitions
- Health score calculations

**TestComplianceService**
- Compliance score calculation
- Weighted severity scoring
- Drift detection and thresholds
- Remediation job management

**TestSecurityFunctions**
- Rate limit enforcement
- XSS protection validation
- API key management
- HMAC signing and verification
- Security header validation

**TestSecurityConfig**
- Security configuration validation
- Secret key strength requirements
- CORS origins validation
- Password policy configuration

### Integration Tests (`tests/integration/`)

**TestAuthenticationEndpoints**
- Login with valid/invalid credentials
- Token refresh
- Session management

**TestDeviceEndpoints**
- List devices with filtering
- Create new devices
- Update device configuration
- Delete devices

**TestComplianceEndpoints**
- List compliance frameworks
- Get fleet compliance summary
- Retrieve active drift events
- Acknowledge drifts
- Create exceptions

**TestMonitoringEndpoints**
- Get fleet status overview
- Get individual device states
- Trigger device polls
- Get trend data

**TestSIEMEndpoints**
- List SIEM events
- Submit new events
- Correlate events
- Check SIEM health

**TestSecurityEndpoints**
- Security header presence
- CORS header validation
- Rate limit header presence
- Invalid JSON rejection
- Oversized payload rejection

## Test Fixtures

### Database Fixtures
- `test_engine`: In-memory SQLite database
- `test_db_session`: Async database session
- `demo_user`: Pre-created test user
- `demo_devices`: Pre-created test devices

### Client Fixtures
- `test_client`: Unauthenticated HTTP client
- `authenticated_client`: HTTP client with auth token

## Test Dependencies

Install test dependencies:
```bash
pip install -r requirements-test.txt
```

Key testing libraries:
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-timeout**: Test timeout enforcement
- **httpx**: Async HTTP client for testing
- **sqlalchemy**: Database ORM

## Continuous Integration

Tests should be run:
1. **Locally**: Before committing code
2. **Pre-commit**: Via git hooks
3. **CI/CD**: On every push to repository

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    pip install -r requirements.txt -r requirements-test.txt
    pytest --cov=app --cov-report=xml
```

## Coverage Goals

- **Overall Coverage**: >= 80%
- **Core Services**: >= 90%
- **API Endpoints**: >= 85%
- **Security Functions**: >= 95%

Check coverage:
```bash
pytest --cov=app --cov-report=term-missing
```

## Security Test Guidelines

Security tests should verify:
- ✅ Authentication is enforced
- ✅ Authorization is checked
- ✅ Rate limits are applied
- ✅ XSS attacks are prevented
- ✅ SQL injection is prevented
- ✅ CSRF protection is present
- ✅ Security headers are set
- ✅ Sensitive data is not logged

Run security tests:
```bash
pytest -m security -v
```

## Debugging Tests

### Enable debug logging
```bash
pytest --log-cli-level=DEBUG
```

### Run with Python debugger
```bash
pytest --pdb
```

### Stop on first failure
```bash
pytest -x
```

### Show print statements
```bash
pytest -s
```

## Performance Testing

### Identify slow tests
```bash
pytest --durations=10
```

### Run only fast tests
```bash
pytest -m "not slow"
```

### Stress test with repeated runs
```bash
pytest --count=100
```

## Database Testing

### Test migrations
```bash
alembic upgrade head
pytest tests/integration/
alembic downgrade base
```

### Use different database
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test_db"
pytest
```

## Adding New Tests

1. Create test file in appropriate directory
2. Follow naming convention: `test_*.py`
3. Use appropriate fixtures from `conftest.py`
4. Add markers (@pytest.mark.integration, etc.)
5. Document test purpose in docstring
6. Run locally before committing

Example:
```python
@pytest.mark.integration
class TestNewFeature:
    """Tests for new feature."""

    @pytest.mark.asyncio
    async def test_feature_success(self, authenticated_client):
        """Test successful feature execution."""
        response = await authenticated_client.post(
            "/api/v1/feature/endpoint",
            json={"data": "value"},
        )
        assert response.status_code == 200
```

## Troubleshooting

### Tests hang
- Check for missing `await` on async calls
- Verify database connection timeouts
- Check for deadlocks in database tests

### Import errors
- Ensure `PYTHONPATH` includes project root
- Check that all dependencies are installed
- Verify `__init__.py` files exist in packages

### Async test errors
- Use `@pytest.mark.asyncio` decorator
- Use `async def` for test functions
- Use `await` on all async calls

### Database issues
- Check `TEST_DATABASE_URL` is set
- Verify database migrations are current
- Clear database between test runs

## Reporting Bugs

When reporting test failures:
1. Include full pytest output
2. Specify Python version
3. List environment variables
4. Provide minimal reproduction example
5. Include logs if available

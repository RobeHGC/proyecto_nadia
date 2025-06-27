# NADIA HITL Testing Guide

This guide covers the testing strategy, structure, and best practices for the NADIA HITL system.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Coverage Requirements](#coverage-requirements)
7. [Best Practices](#best-practices)

## Testing Philosophy

NADIA HITL follows a comprehensive testing strategy based on the testing pyramid:

- **Unit Tests (70%)**: Fast, isolated tests for individual components
- **Integration Tests (25%)**: Test component interactions with real dependencies
- **End-to-End Tests (5%)**: Full system behavior validation

### Key Principles

1. **Test Isolation**: Each test should be independent and repeatable
2. **Fast Feedback**: Unit tests should run in milliseconds
3. **Realistic Scenarios**: Integration tests use real databases and services
4. **Continuous Testing**: All tests run automatically on every commit

## Test Structure

```
tests/
├── unit/                           # Fast, isolated unit tests
│   ├── test_supervisor_core.py     # Supervisor agent logic
│   ├── test_memory_core.py         # Memory management
│   ├── test_protocol_manager_unit.py # Protocol manager units
│   ├── test_intermediary_agent.py  # Intermediary agent logic
│   ├── test_post_llm2_agent.py     # Post-LLM2 agent logic
│   └── test_recovery_agent.py      # Recovery system logic
├── integration/                    # Component integration tests
│   ├── test_coherence_integration.py # Coherence system flow
│   ├── test_protocol_api_integration.py # API endpoints
│   ├── test_multi_llm_integration.py # Multi-LLM pipeline
│   └── test_wal_integration.py     # WAL system integration
├── e2e/                           # End-to-end tests
│   ├── automated_e2e_tester.py    # Full system automation
│   └── visual_test_monitor.py     # Dashboard testing
├── conftest.py                    # Shared fixtures
└── pytest.ini                     # Test configuration
```

## Running Tests

### Quick Start

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Fast unit tests only
make test-integration   # Integration tests
make test-e2e          # End-to-end tests

# Generate coverage report
make test-coverage

# Run tests locally (without Docker)
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/ -v
```

### Advanced Testing

```bash
# Run specific test file
make test-specific TEST=test_supervisor_core.py

# Run tests matching pattern
pytest tests/ -k "protocol" -v

# Run tests with specific marker
pytest -m "not slow" -v

# Run in watch mode (auto-rerun on changes)
make test-watch

# Run with detailed output
pytest tests/ -vvs

# Run failed tests only
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

### Test Markers

Tests are categorized using markers defined in `pytest.ini`:

```python
@pytest.mark.unit        # Fast unit tests
@pytest.mark.integration # Tests requiring external services
@pytest.mark.e2e        # End-to-end system tests
@pytest.mark.slow       # Tests taking >1 second
```

## Writing Tests

### Unit Test Template

```python
"""Unit tests for MyFeature."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from module.my_feature import MyFeature


@pytest.mark.unit
class TestMyFeature:
    """Test suite for MyFeature."""
    
    @pytest.fixture
    def mock_dependency(self):
        """Mock external dependency."""
        mock = AsyncMock()
        mock.some_method.return_value = "expected"
        return mock
    
    @pytest.fixture
    def my_feature(self, mock_dependency):
        """Create MyFeature instance."""
        return MyFeature(mock_dependency)
    
    async def test_basic_functionality(self, my_feature):
        """Test basic feature behavior."""
        result = await my_feature.do_something("input")
        assert result == "expected_output"
    
    @patch('module.my_feature.external_api')
    async def test_with_mocked_api(self, mock_api, my_feature):
        """Test with mocked external API."""
        mock_api.return_value = {"status": "success"}
        result = await my_feature.call_api()
        assert result["status"] == "success"
        mock_api.assert_called_once()
```

### Integration Test Template

```python
"""Integration tests for API endpoints."""
import pytest
from httpx import AsyncClient
from datetime import datetime

from api.server import app
from database.models import DatabaseManager


@pytest.mark.integration
class TestAPIIntegration:
    """Test API endpoint integration."""
    
    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    async def test_db(self):
        """Create test database."""
        db = DatabaseManager("postgresql://localhost/test_db")
        await db.initialize()
        yield db
        await db.cleanup()
    
    async def test_create_resource(self, client, test_db):
        """Test resource creation endpoint."""
        response = await client.post(
            "/api/resources",
            json={"name": "test", "value": 123}
        )
        assert response.status_code == 201
        
        # Verify in database
        resource = await test_db.get_resource("test")
        assert resource["value"] == 123
```

### Async Testing Patterns

```python
# Testing async context managers
async def test_async_context_manager():
    async with MyAsyncResource() as resource:
        result = await resource.process()
        assert result is not None

# Testing async generators
async def test_async_generator():
    results = []
    async for item in my_async_generator():
        results.append(item)
    assert len(results) == expected_count

# Testing concurrent operations
async def test_concurrent_operations():
    tasks = [process_item(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    assert all(r["status"] == "success" for r in results)
```

## CI/CD Pipeline

The GitHub Actions workflow (`/.github/workflows/test.yml`) runs on every push and pull request:

### Pipeline Stages

1. **Lint & Format**
   - Runs `ruff` for code quality checks
   - Validates import sorting with `isort`
   - Ensures consistent code formatting

2. **Test Suite**
   - Spins up PostgreSQL 14 and Redis 7
   - Runs full test suite with coverage
   - Uploads results to Codecov

3. **Security Scan**
   - Scans for secrets with Trufflehog
   - Validates no API keys in code

### Local CI Simulation

```bash
# Run the same checks as CI locally
./scripts/run_ci_checks.sh

# Individual checks
ruff check .
ruff format --check .
isort --check-only .
pytest tests/ --cov=. --cov-report=xml
```

## Coverage Requirements

### Current Thresholds

- **Line Coverage**: 80% minimum
- **Branch Coverage**: 70% minimum
- **Critical Paths**: 95% minimum

### Viewing Coverage

```bash
# Generate HTML report
make test-coverage

# View in browser
python -m http.server 8080 --directory htmlcov/
# Open http://localhost:8080

# Check specific module coverage
pytest tests/ --cov=agents.supervisor_agent --cov-report=term-missing
```

### Improving Coverage

1. **Identify gaps**: Look for red lines in HTML report
2. **Test edge cases**: Empty inputs, errors, boundaries
3. **Mock external calls**: Don't test third-party code
4. **Focus on business logic**: Prioritize critical paths

## Best Practices

### 1. Test Organization

- One test class per module/feature
- Descriptive test names that explain the scenario
- Group related tests with nested classes
- Use fixtures for common setup

### 2. Mocking Strategy

```python
# Good: Mock at boundaries
@patch('external_api.client.request')
async def test_api_call(mock_request):
    mock_request.return_value = {"data": "test"}
    
# Bad: Over-mocking internal implementation
@patch('my_module._internal_method')  # Avoid this
```

### 3. Assertion Guidelines

```python
# Good: Specific assertions
assert response.status_code == 200
assert response.json()["user"]["name"] == "Test User"

# Bad: Generic assertions
assert response is not None
assert len(results) > 0
```

### 4. Test Data Management

```python
# Use factories for test data
@pytest.fixture
def user_factory():
    def _create_user(**kwargs):
        defaults = {
            "id": "user123",
            "name": "Test User",
            "status": "active"
        }
        return {**defaults, **kwargs}
    return _create_user

# Use in tests
def test_user_creation(user_factory):
    user = user_factory(name="Custom Name")
    assert user["name"] == "Custom Name"
```

### 5. Async Best Practices

- Always use `pytest.mark.asyncio` for async tests
- Properly await all async operations
- Clean up resources in finally blocks
- Use `asyncio.gather` for concurrent test operations

### 6. Database Testing

```python
# Use transactions for isolation
@pytest.fixture
async def db_transaction():
    async with db.transaction() as tx:
        yield tx
        await tx.rollback()

# Clean state between tests
@pytest.fixture(autouse=True)
async def clean_db():
    yield
    await db.execute("TRUNCATE TABLE test_data")
```

### 7. Performance Testing

```python
# Mark slow tests
@pytest.mark.slow
async def test_large_dataset_processing():
    # Test with 10k records
    pass

# Benchmark critical paths
def test_performance(benchmark):
    result = benchmark(process_data, large_dataset)
    assert result.duration < 1.0  # Max 1 second
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Set PYTHONPATH
   export PYTHONPATH=/home/rober/projects/chatbot_nadia
   ```

2. **Database Connection**
   ```bash
   # Ensure test database exists
   createdb nadia_hitl_test
   ```

3. **Async Warnings**
   ```python
   # Use pytest-asyncio mode
   # Already configured in pytest.ini
   ```

4. **Flaky Tests**
   - Add retries for network operations
   - Use proper test isolation
   - Mock time-dependent operations

### Debug Mode

```bash
# Run with debugging
pytest tests/test_specific.py -vvs --pdb

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

## Contributing Tests

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all edge cases are covered
3. Add integration tests for API changes
4. Update this guide if needed
5. Verify CI passes before merging

### Test Review Checklist

- [ ] Tests are isolated and don't depend on order
- [ ] Mocks are used appropriately
- [ ] Edge cases are covered
- [ ] Tests have descriptive names
- [ ] No hardcoded values or sleeps
- [ ] Async operations are properly handled
- [ ] Coverage meets minimum requirements
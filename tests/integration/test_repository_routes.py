"""
Integration tests for Repository API endpoints (/api/v1/repositories).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.app import create_app
from backend.database.models import Repository
from backend.database.session import get_db_session

app = create_app()
client = TestClient(app)


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def _get_db():
        yield session

    app.dependency_overrides[get_db_session] = _get_db
    yield session
    app.dependency_overrides.pop(get_db_session, None)


def test_register_repository_success(mock_db):
    # Simulate not found on initial query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    response = client.post(
        "/api/v1/repositories",
        json={"url": "https://github.com/fastapi/fastapi", "provider": "github"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["owner"] == "fastapi"
    assert data["name"] == "fastapi"
    assert data["url"] == "https://github.com/fastapi/fastapi"
    assert "id" in data


def test_register_repository_already_exists(mock_db):
    existing = Repository(
        id=uuid.uuid4(),
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
        stars_count=75000,
        created_at=datetime.now(UTC),
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_db.execute.return_value = mock_result

    response = client.post(
        "/api/v1/repositories",
        json={"url": "https://github.com/fastapi/fastapi"},
    )
    assert response.status_code == 201 or response.status_code == 200
    data = response.json()
    assert data["id"] == str(existing.id)
    assert data["owner"] == "fastapi"


def test_register_repository_invalid_url(mock_db):
    response = client.post(
        "/api/v1/repositories",
        json={"url": "not-a-valid-url"},
    )
    # Schema validation or URL parsing failure
    assert response.status_code in {400, 422}


def test_list_repositories(mock_db):
    repo1 = Repository(
        id=uuid.uuid4(),
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
        stars_count=75000,
        created_at=datetime.now(UTC),
    )
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [repo1]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    response = client.get("/api/v1/repositories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "fastapi"


def test_get_repository_by_id_found(mock_db):
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
        stars_count=75000,
        created_at=datetime.now(UTC),
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = repo
    mock_db.execute.return_value = mock_result

    response = client.get(f"/api/v1/repositories/{repo_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(repo_id)
    assert data["name"] == "fastapi"


def test_get_repository_by_id_not_found(mock_db):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    unknown_id = uuid.uuid4()
    response = client.get(f"/api/v1/repositories/{unknown_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["status"] == 404
    assert "not found" in data["detail"].lower()

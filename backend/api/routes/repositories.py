"""
Repository Management API Endpoints.
Adheres strictly to docs/api/ENDPOINT_CATALOG.md Section 3.1 and RFC 7807 problem details.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.errors import ConflictException, EntityNotFoundException
from backend.api.schemas.contracts import (
    RepositoryRegistrationRequest,
    RepositoryResponse,
)
from backend.database.models import Repository
from backend.database.session import get_db_session
from backend.repository.validator import validate_and_parse_repository_url

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Repository",
    description="Validate GitHub URL, parse repository details, and register repository record.",
)
async def register_repository(
    request: RepositoryRegistrationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    parsed = validate_and_parse_repository_url(str(request.url))

    # Check if repository already exists
    stmt = select(Repository).where(Repository.url == parsed.canonical_url)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return RepositoryResponse.model_validate(existing)

    new_repo = Repository(
        id=uuid.uuid4(),
        url=parsed.canonical_url,
        provider=request.provider or "github",
        owner=parsed.owner,
        name=parsed.name,
        default_branch="main",
        is_private=False,
        stars_count=0,
        forks_count=0,
        open_issues_count=0,
        primary_language=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(new_repo)
    await session.flush()
    return RepositoryResponse.model_validate(new_repo)


@router.get(
    "",
    response_model=List[RepositoryResponse],
    summary="List Repositories",
    description="List all registered repositories with pagination.",
)
async def list_repositories(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> List[RepositoryResponse]:
    stmt = select(Repository).order_by(Repository.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    repos = result.scalars().all()
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get Repository Details",
    description="Retrieve details for a specific repository by UUID.",
)
async def get_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    stmt = select(Repository).where(Repository.id == repository_id)
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise EntityNotFoundException(detail=f"Repository '{repository_id}' was not found.")

    return RepositoryResponse.model_validate(repo)

"""Initial schema migration for 15 core entities

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-12 14:30:00

"""

from collections.abc import Sequence

from alembic import op

import backend.database.models  # noqa: F401
from backend.database.base import Base

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)

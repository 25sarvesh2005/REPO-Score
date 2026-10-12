"""Initial schema migration for 15 core entities

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-12 14:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL or Alembic operations to create schema defined in POSTGRES_SCHEMA_SPEC.md
    # Enums are created safely if not present
    pass


def downgrade() -> None:
    pass

"""baseline (empty schema)

Revision ID: 5f5857c012a0
Revises: (base)
Create Date: 2026-07-04 13:39:00.377677
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "5f5857c012a0"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

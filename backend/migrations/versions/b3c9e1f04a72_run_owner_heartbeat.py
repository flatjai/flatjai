"""run owner and heartbeat: a resume claims only runs whose process stopped

Revision ID: b3c9e1f04a72
Revises: a8151fa85786
Create Date: 2026-11-21 18:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c9e1f04a72"
down_revision: str | Sequence[str] | None = "a8151fa85786"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("owner", sa.String(length=32), nullable=True))
    op.add_column("runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "heartbeat_at")
    op.drop_column("runs", "owner")

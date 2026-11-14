"""flag automated clicks

Revision ID: b7c1e2f4a901
Revises: 8dbe45b3def3
Create Date: 2026-11-14 13:45:00.000000

Bot clicks are recorded (they are real traffic) but flagged so that the
human-facing analytics totals can exclude them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e2f4a901"
down_revision: Union[str, Sequence[str], None] = "8dbe45b3def3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the is_bot flag to clicks."""
    # The server default is kept: it makes the column safe to add to a
    # table that already holds rows, and it is portable across SQLite
    # (which cannot ALTER COLUMN).
    op.add_column(
        "clicks",
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Remove the is_bot flag."""
    op.drop_column("clicks", "is_bot")

"""Backfill denuncia status and enforce default.

Revision ID: 9f4e8b1c2d3a
Revises: 5c0e3d927a61
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4e8b1c2d3a"
down_revision: Union[str, Sequence[str], None] = "5c0e3d927a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE denuncias SET status = 'pendente' WHERE status IS NULL OR status = ''")
    op.alter_column(
        "denuncias",
        "status",
        existing_type=sa.String(length=25),
        nullable=False,
        server_default="pendente",
    )


def downgrade() -> None:
    op.alter_column(
        "denuncias",
        "status",
        existing_type=sa.String(length=25),
        nullable=True,
        server_default=None,
    )

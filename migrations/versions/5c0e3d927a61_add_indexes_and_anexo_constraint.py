"""Add indexes and enforce anexo denuncia relation.

Revision ID: 5c0e3d927a61
Revises: 2b4a0b8d91f3
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c0e3d927a61"
down_revision: Union[str, Sequence[str], None] = "2b4a0b8d91f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    orphan_count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM denuncias_anexos WHERE id_denuncia IS NULL"
    )).scalar()

    if orphan_count:
        raise RuntimeError(
            "Found denuncias_anexos rows without id_denuncia. "
            "Fix or archive these rows before running this migration."
        )

    op.alter_column(
        "denuncias_anexos",
        "id_denuncia",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index("ix_denuncias_status", "denuncias", ["status"])
    op.create_index("ix_denuncias_data", "denuncias", ["data"])
    op.create_index("ix_denuncias_data_public", "denuncias", ["data_public"])
    op.create_index("ix_denuncias_vitima_id", "denuncias", ["vitima_id"])
    op.create_index("ix_denuncias_ofesor_id", "denuncias", ["ofesor_id"])
    op.create_index("ix_denuncias_anexos_id_denuncia", "denuncias_anexos", ["id_denuncia"])


def downgrade() -> None:
    op.drop_index("ix_denuncias_anexos_id_denuncia", table_name="denuncias_anexos")
    op.drop_index("ix_denuncias_ofesor_id", table_name="denuncias")
    op.drop_index("ix_denuncias_vitima_id", table_name="denuncias")
    op.drop_index("ix_denuncias_data_public", table_name="denuncias")
    op.drop_index("ix_denuncias_data", table_name="denuncias")
    op.drop_index("ix_denuncias_status", table_name="denuncias")
    op.alter_column(
        "denuncias_anexos",
        "id_denuncia",
        existing_type=sa.Integer(),
        nullable=True,
    )

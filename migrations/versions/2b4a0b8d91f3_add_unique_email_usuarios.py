"""Add unique email index to usuarios.

Revision ID: 2b4a0b8d91f3
Revises: b7d9c2a4f001
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash


PASSWORD_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "argon2:")


# revision identifiers, used by Alembic.
revision: str = "2b4a0b8d91f3"
down_revision: Union[str, Sequence[str], None] = "b7d9c2a4f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE usuarios SET email = LOWER(TRIM(email))")

    connection = op.get_bind()
    duplicates = connection.execute(sa.text("""
        SELECT email, COUNT(*) AS total
        FROM usuarios
        GROUP BY email
        HAVING COUNT(*) > 1
    """)).fetchall()

    if duplicates:
        emails = ", ".join(row[0] for row in duplicates[:10])
        raise RuntimeError(
            "Duplicate user emails found after normalization. "
            f"Resolve duplicates before running this migration: {emails}"
        )

    usuarios = connection.execute(sa.text("SELECT id, senha FROM usuarios")).mappings()

    for usuario in usuarios:
        senha = usuario["senha"]

        if isinstance(senha, str) and not senha.startswith(PASSWORD_HASH_PREFIXES):
            connection.execute(
                sa.text("UPDATE usuarios SET senha = :senha WHERE id = :id"),
                {"senha": generate_password_hash(senha), "id": usuario["id"]}
            )

    op.create_index("uq_usuarios_email", "usuarios", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_usuarios_email", table_name="usuarios")

"""Add account permissions and configurable complaint situation types.

Revision ID: c4a7d2e910b6
Revises: 9f4e8b1c2d3a
"""

from hashlib import sha256
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "c4a7d2e910b6"
down_revision = "9f4e8b1c2d3a"
branch_labels = None
depends_on = None

DEFAULT_TYPES = ("Violência Física", "Violência Psicológica", "Assédio", "Discriminação", "Outro")


def _name_key(name):
    normalized = unicodedata.normalize("NFKC", " ".join(name.split())).casefold()
    return sha256(normalized.encode("utf-8")).hexdigest()


def upgrade():
    op.add_column("usuarios", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("usuarios", sa.Column("administrador_principal", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("usuarios", sa.Column("versao_sessao", sa.Integer(), nullable=False, server_default="1"))

    tipos = op.create_table(
        "tipos_situacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("chave_nome", sa.String(64), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("chave_nome", name="uq_tipos_situacao_chave_nome"),
    )
    connection = op.get_bind()
    tipo_ids = {}
    for name in DEFAULT_TYPES:
        key = _name_key(name)
        result = connection.execute(tipos.insert().values(nome=name, chave_nome=key, ativo=True))
        tipo_ids[key] = result.inserted_primary_key[0]

    with op.batch_alter_table("denuncias") as batch_op:
        batch_op.add_column(sa.Column("tipo_situacao_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_denuncias_tipo_situacao_id", ["tipo_situacao_id"])
        batch_op.create_foreign_key("fk_denuncias_tipo_situacao_id", "tipos_situacao", ["tipo_situacao_id"], ["id"])

    # A categoria textual continua sendo uma fotografia da classificação original.
    # O vínculo novo não renomeia nem remove nenhuma denúncia existente.
    denuncias = sa.table(
        "denuncias", sa.column("id", sa.Integer()), sa.column("categoria", sa.String(255)),
        sa.column("tipo_situacao_id", sa.Integer()),
    )
    last_id = None
    while True:
        query = sa.select(denuncias.c.id, denuncias.c.categoria).order_by(denuncias.c.id).limit(1000)
        if last_id is not None:
            query = query.where(denuncias.c.id > last_id)
        rows = connection.execute(
            query
        ).mappings().all()
        if not rows:
            break
        for row in rows:
            name = row["categoria"]
            if name and name.strip():
                key = _name_key(name)
                if key not in tipo_ids:
                    result = connection.execute(tipos.insert().values(
                        nome=" ".join(name.split()), chave_nome=key, ativo=True,
                    ))
                    tipo_ids[key] = result.inserted_primary_key[0]
                connection.execute(
                    denuncias.update().where(denuncias.c.id == row["id"])
                    .values(tipo_situacao_id=tipo_ids[key])
                )
        last_id = rows[-1]["id"]


def downgrade():
    with op.batch_alter_table("denuncias") as batch_op:
        batch_op.drop_constraint("fk_denuncias_tipo_situacao_id", type_="foreignkey")
        batch_op.drop_index("ix_denuncias_tipo_situacao_id")
        batch_op.drop_column("tipo_situacao_id")
    op.drop_table("tipos_situacao")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("versao_sessao")
        batch_op.drop_column("administrador_principal")
        batch_op.drop_column("ativo")

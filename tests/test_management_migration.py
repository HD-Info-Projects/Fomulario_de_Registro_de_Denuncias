import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlalchemy as sa


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("management_revision", ROOT / "migrations/versions/c4a7d2e910b6_admin_principal_e_tipos_situacao.py")
revision = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(revision)


class ManagementMigrationTests(unittest.TestCase):
    def test_migration_extends_the_current_head_without_creating_a_branch(self):
        config = Config(str(ROOT / "alembic.ini"))
        scripts = ScriptDirectory.from_config(config)
        self.assertEqual(scripts.get_heads(), [revision.revision])
        self.assertEqual(revision.down_revision, "9f4e8b1c2d3a")

    def test_upgrade_and_downgrade_preserve_existing_data(self):
        engine = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        metadata = sa.MetaData()
        usuarios = sa.Table("usuarios", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("nome", sa.String(150)), sa.Column("email", sa.String(255)), sa.Column("senha", sa.String(255)))
        denuncias = sa.Table("denuncias", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("categoria", sa.String(255), nullable=False))
        historico = sa.Table("denuncias_historico", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id")), sa.Column("denuncia_id", sa.Integer, sa.ForeignKey("denuncias.id")), sa.Column("campo", sa.String(80)))

        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(usuarios.insert(), [{"id": 1, "nome": "Administrador existente", "email": "existente@example.com", "senha": "hash-original-preservado"}])
            originals = ["Outro", "  ASSÉDIO  ", "Categoria legada", "Assedio", ""]
            connection.execute(denuncias.insert(), [{"id": index, "categoria": name} for index, name in enumerate(originals, start=1)])
            connection.execute(historico.insert(), [{"id": 1, "usuario_id": 1, "denuncia_id": 1, "campo": "Status"}])

            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()

            rows = connection.execute(sa.text("SELECT categoria, tipo_situacao_id FROM denuncias ORDER BY id")).all()
            self.assertEqual([row.categoria for row in rows], originals)
            self.assertTrue(all(row.tipo_situacao_id is not None for row in rows[:-1]))
            self.assertIsNone(rows[-1].tipo_situacao_id)
            usuario = connection.execute(sa.text("SELECT * FROM usuarios")).mappings().one()
            self.assertTrue(usuario["ativo"])
            self.assertFalse(usuario["administrador_principal"])
            self.assertEqual(usuario["versao_sessao"], 1)
            self.assertEqual(usuario["senha"], "hash-original-preservado")
            names = set(connection.execute(sa.text("SELECT nome FROM tipos_situacao")).scalars())
            self.assertTrue(set(revision.DEFAULT_TYPES).issubset(names))
            self.assertIn("Categoria legada", names)
            self.assertIn("Assedio", names)
            self.assertEqual(connection.execute(sa.text("SELECT COUNT(*) FROM denuncias_historico")).scalar(), 1)

            with Operations.context(MigrationContext.configure(connection)):
                revision.downgrade()
            self.assertEqual(connection.execute(sa.select(denuncias.c.categoria).order_by(denuncias.c.id)).scalars().all(), originals)
            self.assertEqual(connection.execute(sa.select(usuarios.c.senha)).scalar(), "hash-original-preservado")
            self.assertEqual(connection.execute(sa.text("SELECT COUNT(*) FROM denuncias_historico")).scalar(), 1)
            self.assertNotIn("tipos_situacao", sa.inspect(connection).get_table_names())

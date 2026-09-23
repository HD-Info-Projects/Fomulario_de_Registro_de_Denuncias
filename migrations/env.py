import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Permite importar o app e o db
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.settings.extensions import db

# Importa os modelos para registrar o metadata no Alembic.
from src.models import Usuario_model  # noqa: F401
from src.models import Vitima_model  # noqa: F401
from src.models import Ofensor_model  # noqa: F401
from src.models import Denuncia_model  # noqa: F401
from src.models import Denuncia_anexos_model  # noqa: F401
from src.models import Denuncia_historico_model  # noqa: F401

# Config do Alembic (alembic.ini)
config = context.config

# Logging do Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadados que o Alembic vai monitorar
target_metadata = db.metadata

load_dotenv()

def _database_uri():
    url = os.getenv("DATABASE_URI")

    if not url:
        raise RuntimeError("DATABASE_URI must be set to run migrations.")

    return url


def run_migrations_offline():
    """
    Executa migrations sem conexão real (gera SQL).
    Usado raramente — CI/CD, scripts, etc.
    """
    url = _database_uri()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Executa migrations com conexão real ao banco
    (uso normal)
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _database_uri()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# Seleciona modo (online/offline)
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

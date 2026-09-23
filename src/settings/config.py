from dotenv import load_dotenv
import os

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
PUBLIC_STATIC_DIRS = (
    os.path.join(PROJECT_ROOT, "src", "views", "static"),
    os.path.join(PROJECT_ROOT, "static"),
)

def _parse_extensions(value):
    return {
        extension.strip().lower().lstrip(".")
        for extension in value.split(",")
        if extension.strip()
    }

def _env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc

def _required_env(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"{name} must be set.")

    return value.strip()

def _resolve_upload_folder():
    upload_folder = os.getenv("UPLOAD_FOLDER")

    if not upload_folder:
        resolved = os.path.join(PROJECT_ROOT, "instance", "uploads", "denuncias")
    elif os.path.isabs(upload_folder):
        resolved = upload_folder
    else:
        resolved = os.path.join(PROJECT_ROOT, upload_folder)

    resolved = os.path.abspath(resolved)

    for static_dir in PUBLIC_STATIC_DIRS:
        if os.path.commonpath([resolved, static_dir]) == static_dir:
            raise RuntimeError("UPLOAD_FOLDER cannot be inside a public static directory.")

    return resolved

class Config:
    SECRET_KEY = _required_env("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _required_env("DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("SQLALCHEMY_POOL_RECYCLE", 280),
    }
    UPLOAD_FOLDER = _resolve_upload_folder()
    ALLOWED_EXTENSIONS = _parse_extensions(
        os.getenv("ALLOWED_EXTENSIONS", "png,jpg,jpeg,webp,mp4,mov,avi,mkv")
    )
    MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)
    MAX_UPLOAD_FILE_SIZE = _env_int("MAX_UPLOAD_FILE_SIZE", 25 * 1024 * 1024)
    MAX_FILES_PER_DENUNCIA = _env_int("MAX_FILES_PER_DENUNCIA", 5)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

from email_validator import validate_email, EmailNotValidError
import phonenumbers

from uuid import uuid4
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os

load_dotenv()

def validar_email(email: str):
    if not email:
        return None

    try:
        email_valido = validate_email(email, check_deliverability=False)
        return email_valido.normalized
    
    except EmailNotValidError:
        return None

def validar_telefone(telefone: str, ddd_default="11"):
    if not telefone:
        return None

    telefone = telefone.strip()

    # remove espaços, parenteses e traços
    digits = "".join(filter(str.isdigit, telefone))

    # se só vier número de celular (9 dígitos), adiciona DDD padrão
    if len(digits) == 9:
        digits = ddd_default + digits

    try:
        parsed = phonenumbers.parse(digits, "BR")

        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )

        return None

    except phonenumbers.NumberParseException as e:
        return None
    

## Funções utils para uploads de vídeos e img:

def allowed_file(filename, allowed_extensions=None):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    if allowed_extensions is None:
        allowed_extensions = os.getenv(
            "ALLOWED_EXTENSIONS",
            "png,jpg,jpeg,webp,mp4,mov,avi,mkv"
        )

    if isinstance(allowed_extensions, str):
        allowed_extensions = {
            item.strip().lower().lstrip(".")
            for item in allowed_extensions.split(",")
            if item.strip()
        }

    return extension in allowed_extensions

def _read_header(file_storage, limit=4096):
    stream = file_storage.stream

    try:
        position = stream.tell()
        header = stream.read(limit)
        stream.seek(position)
        return header
    except (AttributeError, OSError):
        return b""

def get_upload_size(file_storage):
    stream = file_storage.stream

    try:
        position = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(position)
        return size
    except (AttributeError, OSError):
        return file_storage.content_length or 0

def detect_file_type(file_storage, filename):
    extension = filename.rsplit(".", 1)[1].lower()
    header = _read_header(file_storage)

    if extension == "png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"

    if extension in {"jpg", "jpeg"} and header.startswith(b"\xff\xd8\xff"):
        return "image"

    if extension == "webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image"

    if extension in {"mp4", "mov"} and len(header) >= 12 and header[4:8] == b"ftyp":
        return "video"

    if extension == "avi" and header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return "video"

    if extension == "mkv" and header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video"

    return None

def validate_upload_file(file_storage, allowed_extensions, max_file_size):
    if not file_storage or not file_storage.filename:
        return False, "Arquivo vazio.", None

    if not allowed_file(file_storage.filename, allowed_extensions):
        return False, "Tipo de arquivo não permitido.", None

    size = get_upload_size(file_storage)

    if size <= 0:
        return False, "Arquivo vazio.", None

    if size > max_file_size:
        return False, "Arquivo excede o tamanho máximo permitido.", None

    file_type = detect_file_type(file_storage, file_storage.filename)

    if not file_type:
        return False, "Conteúdo do arquivo não corresponde ao tipo permitido.", None

    return True, "", {"file_type": file_type, "size": size}

def get_file_type(filename):
    extension = filename.rsplit(".", 1)[1].lower()

    if extension in ["png", "jpg", "jpeg", "webp"]:
        return "image"

    if extension in ["mp4", "mov", "avi", "mkv"]:
        return "video"

    return "unknown"

def generate_unique_filename(filename):
    extension = filename.rsplit(".", 1)[1].lower()
    original_stem = filename.rsplit(".", 1)[0]
    stem = secure_filename(original_stem)[:80] or "arquivo"

    unique_name = f"{uuid4().hex}_{stem}.{extension}"

    return unique_name

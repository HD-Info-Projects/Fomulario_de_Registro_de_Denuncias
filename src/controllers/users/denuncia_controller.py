import os

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    current_app,
    redirect,
    url_for
)

from datetime import date, datetime
from werkzeug.utils import secure_filename

from src.models.Vitima_model import Vitima
from src.models.Ofensor_model import Ofesor
from src.models.Denuncia_model import Denuncia
from src.models.Denuncia_anexos_model import DenunciaAnexos

from src.settings.extensions import db
from src.settings.extensions import limiter

from src.utils.utils import (
    generate_unique_filename,
    validar_email,
    validar_telefone,
    validate_upload_file
)

denuncia_bp = Blueprint("denuncias", __name__, url_prefix="/denuncias") 

CATEGORIAS_PERMITIDAS = {
    "Violência Física",
    "Violência Psicológica",
    "Assédio",
    "Discriminação",
    "Outro",
}
TESTEMUNHAS_PERMITIDAS = {"Sim", "Não"}

def _required_text(data, field, label, errors, max_length=None):
    value = (data.get(field) or "").strip()

    if not value:
        errors.append(f"{label} é obrigatório.")
        return value

    if max_length and len(value) > max_length:
        errors.append(f"{label} deve ter no máximo {max_length} caracteres.")

    return value

def _parse_idade(value, errors):
    try:
        idade = int(value)
    except (TypeError, ValueError):
        errors.append("Idade deve ser um número inteiro.")
        return None

    if idade < 0 or idade > 130:
        errors.append("Idade deve estar entre 0 e 130.")

    return idade

def _parse_data_ocorrencia(value, errors):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        errors.append("Data da ocorrência inválida.")
        return None

    if parsed > date.today():
        errors.append("Data da ocorrência não pode estar no futuro.")

    return parsed

def _prepare_uploads(files, errors):
    arquivos = [arquivo for arquivo in files if arquivo and arquivo.filename]
    max_files = current_app.config["MAX_FILES_PER_DENUNCIA"]

    if len(arquivos) > max_files:
        errors.append(f"Envie no máximo {max_files} arquivo(s).")
        return []

    prepared = []

    for arquivo in arquivos:
        ok, message, metadata = validate_upload_file(
            arquivo,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["MAX_UPLOAD_FILE_SIZE"]
        )

        if not ok:
            errors.append(f"{arquivo.filename}: {message}")
            continue

        extension = arquivo.filename.rsplit(".", 1)[1].lower()
        original_stem = secure_filename(arquivo.filename.rsplit(".", 1)[0])[:200] or "arquivo"
        original_name = f"{original_stem}.{extension}"
        prepared.append({
            "file": arquivo,
            "filename": generate_unique_filename(original_name),
            "file_type": metadata["file_type"],
            "original_name": original_name,
        })

    return prepared

def _render_form_errors(errors, form_data):
    for error in errors:
        flash(error, "error")

    return render_template("formulario_denuncia.html", form_data=form_data), 400

@denuncia_bp.route("/formulario", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def form_denuncia():
    if request.method == "POST":
        data = request.form.to_dict()
        errors = []

        nome = _required_text(data, "nome", "Nome da vítima", errors, 150)
        idade = _parse_idade(data.get("idade"), errors)
        telefone = _required_text(data, "telefone", "Telefone", errors, 20)
        email = (data.get("email") or "").strip()
        setor = _required_text(data, "setor", "Setor/Cargo da vítima", errors, 255)
        nome_ofensor = _required_text(data, "nomeOfensor", "Nome do ofensor", errors, 150)
        setor_ofensor = _required_text(data, "setorOfensor", "Setor/Cargo do ofensor", errors, 100)
        descricao_ofensor = _required_text(data, "descricaoOfensor", "Descrição do ofensor", errors, 5000)
        categoria = _required_text(data, "tipo_situacao", "Tipo da situação", errors, 255)
        frequencia = _required_text(data, "frequencia", "Frequência", errors, 255)
        data_ocorrencia = _parse_data_ocorrencia(data.get("data_ocorrencia"), errors)
        descricao_fatos = _required_text(data, "descricaoFatos", "Descrição dos fatos", errors, 10000)
        testemunhas = _required_text(data, "testemunhas", "Informação sobre testemunhas", errors, 10)
        nomes_testemunhas = (data.get("nome_testemunhas") or "").strip()[:5000]

        if categoria and categoria not in CATEGORIAS_PERMITIDAS:
            errors.append("Tipo da situação inválido.")

        if testemunhas and testemunhas not in TESTEMUNHAS_PERMITIDAS:
            errors.append("Valor de testemunhas inválido.")

        if email:
            email = validar_email(email)
            if not email:
                errors.append("E-mail inválido.")

        telefone_formatado = validar_telefone(telefone)
        if not telefone_formatado:
            errors.append("Telefone inválido.")

        prepared_uploads = _prepare_uploads(request.files.getlist("arquivos"), errors)

        if errors:
            return _render_form_errors(errors, data)

        obj_vitima = Vitima(
            nome=nome,
            idade=idade,
            telefone=telefone_formatado,
            email=email,
            setor_cargo=setor
        )
        
        obj_ofensor = Ofesor(
            nome=nome_ofensor,
            setor_cargo=setor_ofensor,
            descricao=descricao_ofensor
        )

        obj_denuncia = Denuncia(
            categoria=categoria,
            frequencia=frequencia,
            data=data_ocorrencia,
            testemunha=testemunhas,
            nomes_testemunhas=nomes_testemunhas,
            descricao_do_fato=descricao_fatos,
            vitima_id=None,
            ofesor_id=None,
            data_public=date.today()
        )

        upload_folder = current_app.config["UPLOAD_FOLDER"]
        saved_files = []

        try:
            os.makedirs(upload_folder, exist_ok=True)
            db.session.add(obj_vitima)
            db.session.add(obj_ofensor)
            db.session.flush()

            obj_denuncia.vitima_id = obj_vitima.id
            obj_denuncia.ofesor_id = obj_ofensor.id

            db.session.add(obj_denuncia)
            db.session.flush()

            for upload in prepared_uploads:
                file_path = os.path.join(upload_folder, upload["filename"])
                saved_files.append(file_path)
                upload["file"].save(file_path)

                db.session.add(DenunciaAnexos(
                    obj_denuncia.id,
                    file_path=upload["filename"],
                    file_type=upload["file_type"],
                    original_name=upload["original_name"]
                ))

            db.session.commit()
        except Exception:
            db.session.rollback()

            for file_path in saved_files:
                try:
                    os.remove(file_path)
                except OSError:
                    current_app.logger.warning("Falha ao remover upload após rollback: %s", file_path)

            current_app.logger.exception("Erro ao registrar denúncia.")
            flash("Não foi possível registrar a denúncia. Tente novamente.", "error")
            return render_template("formulario_denuncia.html", form_data=data), 500

        return redirect(url_for("denuncias.page_success"), code=303)

    return render_template("formulario_denuncia.html", form_data={})


@denuncia_bp.route("/success", methods=["GET"])
def page_success():
    return render_template("success.html")

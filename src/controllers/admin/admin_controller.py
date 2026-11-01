from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_fresh, login_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from src.middlewares.admin_permissions import lock_management_access, principal_required
from src.models.Usuario_model import Usuario
from src.settings.extensions import db
from src.utils.utils import validar_email


administradores_bp = Blueprint("administradores", __name__, url_prefix="/admin/administradores")


def _form_data(usuario=None):
    return {
        "nome": request.form.get("nome", usuario.nome if usuario else ""),
        "email": request.form.get("email", usuario.email if usuario else ""),
        "perfil": request.form.get("perfil", "principal" if usuario and usuario.administrador_principal else "administrador"),
    }


def _validate(data, usuario=None):
    errors = []
    data["nome"] = " ".join(data["nome"].split())
    email = validar_email(data["email"].strip())
    if not data["nome"] or len(data["nome"]) > 150:
        errors.append("Informe um nome com até 150 caracteres.")
    if not email or len(email) > 255:
        errors.append("Informe um e-mail válido com até 255 caracteres.")
    else:
        data["email"] = email.lower()
        duplicate = Usuario.query.filter_by(email=data["email"])
        if usuario:
            duplicate = duplicate.filter(Usuario.id != usuario.id)
        if duplicate.first():
            errors.append("Já existe uma conta com esse e-mail.")
    if data["perfil"] not in {"principal", "administrador"}:
        errors.append("Perfil inválido.")

    senha = request.form.get("senha", "")
    confirmacao = request.form.get("confirmacao_senha", "")
    if senha or confirmacao or usuario is None:
        if not 8 <= len(senha) <= 128:
            errors.append("A senha deve ter entre 8 e 128 caracteres.")
        if senha != confirmacao:
            errors.append("A confirmação da senha não confere.")
    return senha, errors


def _render_form(data, errors=(), usuario=None, status=200):
    return render_template("administrador_form.html", form_data=data, errors=errors, usuario=usuario), status


@administradores_bp.route("", methods=["GET"])
@principal_required
def listar():
    busca = (request.args.get("q") or "").strip()[:255]
    situacao = request.args.get("status", "todos")
    query = Usuario.query
    if busca:
        query = query.filter(or_(Usuario.nome.ilike(f"%{busca}%"), Usuario.email.ilike(f"%{busca}%")))
    if situacao in {"ativos", "inativos"}:
        query = query.filter(Usuario.ativo.is_(situacao == "ativos"))
    else:
        situacao = "todos"
    pagination = query.order_by(Usuario.nome, Usuario.id).paginate(
        page=max(request.args.get("page", 1, type=int), 1), per_page=10, error_out=False,
    )
    return render_template(
        "crud-admin.html", pagination=pagination, busca=busca, situacao=situacao,
        pagination_endpoint="administradores.listar",
        total=Usuario.query.count(), ativos=Usuario.query.filter_by(ativo=True).count(),
        principais=Usuario.query.filter_by(ativo=True, administrador_principal=True).count(),
    )


@administradores_bp.route("/novo", methods=["GET", "POST"])
@principal_required
def criar():
    data = _form_data()
    if request.method == "GET":
        return _render_form(data)

    lock_management_access()
    senha, errors = _validate(data)
    if errors:
        return _render_form(data, errors, status=400)

    # A entrada do formulário é sempre uma senha em texto, nunca um hash fornecido pelo cliente.
    usuario = Usuario(data["nome"], data["email"], generate_password_hash(senha), administrador_principal=data["perfil"] == "principal")
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_form(data, ["Já existe uma conta com esse e-mail."], status=409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro ao cadastrar administrador.")
        return _render_form(data, ["Não foi possível cadastrar a conta. Tente novamente."], status=500)

    flash("Administrador cadastrado com sucesso.", "success")
    return redirect(url_for("administradores.listar"), code=303)


@administradores_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@principal_required
def editar(usuario_id):
    principais = lock_management_access() if request.method == "POST" else []
    query = Usuario.query.filter_by(id=usuario_id)
    if request.method == "POST":
        query = query.populate_existing().with_for_update()
    usuario = query.first_or_404()
    data = _form_data(usuario)
    if request.method == "GET":
        return _render_form(data, usuario=usuario)

    senha, errors = _validate(data, usuario)
    principal = data["perfil"] == "principal"
    if usuario.administrador_principal and not principal:
        if usuario.id == current_user.id:
            errors.append("Você não pode remover o próprio perfil de administrador principal.")
        elif usuario.ativo and len(principais) <= 1:
            errors.append("Mantenha pelo menos um administrador principal ativo.")
    if errors:
        return _render_form(data, errors, usuario, status=400)

    usuario.nome = data["nome"]
    usuario.email = data["email"]
    if usuario.administrador_principal != principal:
        usuario.administrador_principal = principal
        usuario.invalidate_sessions()
    if senha:
        usuario.set_password(senha)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_form(data, ["Já existe uma conta com esse e-mail."], usuario, status=409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro ao editar administrador %s.", usuario_id)
        return _render_form(data, ["Não foi possível salvar a conta. Tente novamente."], usuario, status=500)

    if usuario.id == current_user.id and senha:
        login_user(usuario, fresh=login_fresh())
    flash("Administrador atualizado com sucesso.", "success")
    return redirect(url_for("administradores.listar"), code=303)


@administradores_bp.route("/<int:usuario_id>/status", methods=["POST"])
@principal_required
def alterar_status(usuario_id):
    if request.form.get("ativo") not in {"0", "1"}:
        abort(400, description="Situação inválida.")
    principais = lock_management_access()
    usuario = Usuario.query.filter_by(id=usuario_id).populate_existing().with_for_update().first_or_404()
    ativo = request.form["ativo"] == "1"
    if not ativo and usuario.id == current_user.id:
        flash("Você não pode desativar a própria conta.", "error")
    elif not ativo and usuario.ativo and usuario.administrador_principal and len(principais) <= 1:
        flash("Mantenha pelo menos um administrador principal ativo.", "error")
    else:
        if usuario.ativo != ativo:
            usuario.ativo = ativo
            usuario.invalidate_sessions()
        try:
            db.session.commit()
            flash("Conta reativada com sucesso." if ativo else "Conta desativada. As sessões abertas foram revogadas.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Erro ao alterar situação do administrador %s.", usuario_id)
            flash("Não foi possível alterar a situação da conta.", "error")
    return redirect(url_for("administradores.listar"), code=303)

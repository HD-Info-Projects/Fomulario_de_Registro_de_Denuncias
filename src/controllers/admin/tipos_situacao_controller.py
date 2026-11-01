from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.middlewares.admin_permissions import lock_management_access, principal_required
from src.models.Denuncia_model import Denuncia
from src.models.Tipo_situacao_model import TipoSituacao, tipo_nome_chave
from src.settings.extensions import db


tipos_situacao_bp = Blueprint("tipos_situacao", __name__, url_prefix="/admin/tipos-situacao")


def _form_data(tipo=None):
    return {
        "nome": request.form.get("nome", tipo.nome if tipo else ""),
        "descricao": request.form.get("descricao", (tipo.descricao or "") if tipo else ""),
    }


def _validate(data, tipo=None):
    errors = []
    data["nome"] = " ".join(data["nome"].split())
    data["descricao"] = data["descricao"].strip()
    if not data["nome"] or len(data["nome"]) > 255:
        errors.append("Informe um nome com até 255 caracteres.")
    if len(data["descricao"]) > 2000:
        errors.append("A descrição deve ter até 2000 caracteres.")
    duplicate = TipoSituacao.query.filter_by(chave_nome=tipo_nome_chave(data["nome"]))
    if tipo:
        duplicate = duplicate.filter(TipoSituacao.id != tipo.id)
    if duplicate.first():
        errors.append("Já existe um tipo com esse nome, inclusive entre os desativados.")
    return errors


def _render_form(data, errors=(), tipo=None, status=200):
    return render_template("tipo_situacao_form.html", form_data=data, errors=errors, tipo=tipo), status


@tipos_situacao_bp.route("", methods=["GET"])
@principal_required
def listar():
    busca = (request.args.get("q") or "").strip()[:255]
    situacao = request.args.get("status", "todos")
    query = TipoSituacao.query
    if busca:
        query = query.filter(or_(TipoSituacao.nome.ilike(f"%{busca}%"), TipoSituacao.descricao.ilike(f"%{busca}%")))
    if situacao in {"ativos", "inativos"}:
        query = query.filter(TipoSituacao.ativo.is_(situacao == "ativos"))
    else:
        situacao = "todos"
    pagination = query.order_by(TipoSituacao.nome, TipoSituacao.id).paginate(
        page=max(request.args.get("page", 1, type=int), 1), per_page=10, error_out=False,
    )
    counts = dict(db.session.query(Denuncia.tipo_situacao_id, func.count(Denuncia.id))
                  .filter(Denuncia.tipo_situacao_id.in_([tipo.id for tipo in pagination.items]))
                  .group_by(Denuncia.tipo_situacao_id).all())
    return render_template(
        "tipos_situacao.html", pagination=pagination, busca=busca, situacao=situacao,
        pagination_endpoint="tipos_situacao.listar", counts=counts,
        total=TipoSituacao.query.count(), ativos=TipoSituacao.query.filter_by(ativo=True).count(),
    )


@tipos_situacao_bp.route("/novo", methods=["GET", "POST"])
@principal_required
def criar():
    data = _form_data()
    if request.method == "GET":
        return _render_form(data)
    lock_management_access()
    errors = _validate(data)
    if errors:
        return _render_form(data, errors, status=400)
    db.session.add(TipoSituacao(data["nome"], data["descricao"] or None))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_form(data, ["Já existe um tipo com esse nome."], status=409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro ao cadastrar tipo de situação.")
        return _render_form(data, ["Não foi possível cadastrar o tipo. Tente novamente."], status=500)
    flash("Tipo de situação cadastrado com sucesso.", "success")
    return redirect(url_for("tipos_situacao.listar"), code=303)


@tipos_situacao_bp.route("/<int:tipo_id>/editar", methods=["GET", "POST"])
@principal_required
def editar(tipo_id):
    if request.method == "POST":
        lock_management_access()
    query = TipoSituacao.query.filter_by(id=tipo_id)
    if request.method == "POST":
        query = query.populate_existing().with_for_update()
    tipo = query.first_or_404()
    data = _form_data(tipo)
    if request.method == "GET":
        return _render_form(data, tipo=tipo)
    errors = _validate(data, tipo)
    if errors:
        return _render_form(data, errors, tipo, status=400)
    tipo.set_nome(data["nome"])
    tipo.descricao = data["descricao"] or None
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_form(data, ["Já existe um tipo com esse nome."], tipo, status=409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro ao editar tipo de situação %s.", tipo_id)
        return _render_form(data, ["Não foi possível salvar o tipo. Tente novamente."], tipo, status=500)
    flash("Tipo atualizado. As classificações das denúncias anteriores foram preservadas.", "success")
    return redirect(url_for("tipos_situacao.listar"), code=303)


@tipos_situacao_bp.route("/<int:tipo_id>/status", methods=["POST"])
@principal_required
def alterar_status(tipo_id):
    if request.form.get("ativo") not in {"0", "1"}:
        abort(400, description="Situação inválida.")
    lock_management_access()
    tipo = TipoSituacao.query.filter_by(id=tipo_id).populate_existing().with_for_update().first_or_404()
    tipo.ativo = request.form["ativo"] == "1"
    try:
        db.session.commit()
        flash("Tipo reativado no formulário público." if tipo.ativo else "Tipo desativado. As denúncias existentes foram preservadas.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Erro ao alterar situação do tipo %s.", tipo_id)
        flash("Não foi possível alterar a situação do tipo.", "error")
    return redirect(url_for("tipos_situacao.listar"), code=303)

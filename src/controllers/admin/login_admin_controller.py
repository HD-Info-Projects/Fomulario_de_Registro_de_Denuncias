from flask import (
    Blueprint,
    render_template,
    request,
    session,
    flash,
    url_for,
    redirect,
    jsonify,
    Response,
    current_app,
    send_from_directory,
    abort,
    stream_with_context
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from datetime import date, datetime
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import selectinload
    
import csv
import io
import os

from src.models.Vitima_model import Vitima
from src.models.Ofensor_model import Ofesor
from src.models.Denuncia_model import Denuncia, StatusEnum
from src.models.Denuncia_anexos_model import DenunciaAnexos
from src.models.Denuncia_historico_model import DenunciaHistorico
from src.models.Usuario_model import Usuario

from src.settings.extensions import db, limiter

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

PAINEL_DEFAULT_PER_PAGE = 10
PAINEL_MAX_PER_PAGE = 50
PRAZO_PENDENTE_DIAS = 7

STATUS_OPTIONS = [
    ("", "Todos"),
    (StatusEnum.PENDENTE.value, "Pendente"),
    (StatusEnum.EM_ANALISE.value, "Em análise"),
    (StatusEnum.SUSPENSO.value, "Suspenso"),
    (StatusEnum.FINALIZADO.value, "Finalizado"),
]

SEVERIDADES = [
    ("baixa", "Baixa"),
    ("media", "Média"),
    ("alta", "Alta"),
    ("critica", "Crítica"),
]

SEVERIDADE_OPTIONS = [
    ("", "Todas"),
    *SEVERIDADES,
    ("nao_definida", "Não definida"),
]

EVIDENCIAS_OPTIONS = [
    ("", "Todos"),
    ("com", "Com evidências"),
    ("sem", "Sem evidências"),
]

SORT_OPTIONS = [
    ("recentes", "Mais recentes"),
    ("antigas", "Mais antigas"),
    ("status", "Status"),
    ("categoria", "Categoria"),
]


def _parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_export_value(value):
    text = "" if value is None else str(value)
    text = "".join(" " if char in "\r\n\t" else char for char in text)

    if text.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{text}"

    return text


def _normalize_filter_value(value):
    value = (value or "").strip()
    return "" if value == "all" else value


def _get_dashboard_filters(source=None):
    source = source or request.args

    return {
        "data_inicio": (source.get("data_inicio") or source.get("dataInicio") or "").strip(),
        "data_fim": (source.get("data_fim") or source.get("dataFim") or "").strip(),
        "status": _normalize_filter_value(source.get("status")),
        "severidade": _normalize_filter_value(source.get("severidade")),
        "evidencias": _normalize_filter_value(source.get("evidencias")),
    }


def _dashboard_query_params(filtros):
    return {
        key: value
        for key, value in filtros.items()
        if value not in (None, "")
    }


def _apply_dashboard_filters(query, filtros, include_status=True, include_severidade=True):
    data_inicio = _parse_date(filtros["data_inicio"])
    data_fim = _parse_date(filtros["data_fim"])
    status = filtros["status"]
    severidade = filtros["severidade"]
    evidencias = filtros["evidencias"]

    if data_inicio:
        query = query.filter(Denuncia.data_public >= data_inicio)

    if data_fim:
        query = query.filter(Denuncia.data_public <= data_fim)

    if include_status and status in [item.value for item in StatusEnum]:
        query = query.filter(Denuncia.status == status)

    if include_severidade:
        if severidade == "nao_definida":
            query = query.filter(or_(Denuncia.severidade.is_(None), Denuncia.severidade == ""))
        elif severidade in {"baixa", "media", "alta", "critica"}:
            query = query.filter(Denuncia.severidade == severidade)

    if evidencias == "com":
        query = query.filter(Denuncia.anexos.any())
    elif evidencias == "sem":
        query = query.filter(~Denuncia.anexos.any())

    return query


def _dashboard_filtered_query(filtros=None, include_status=True, include_severidade=True):
    filtros = filtros or _get_dashboard_filters()
    return _apply_dashboard_filters(
        Denuncia.query,
        filtros,
        include_status=include_status,
        include_severidade=include_severidade,
    )


def _export_denuncias_query(filtros=None):
    query = Denuncia.query.options(
        selectinload(Denuncia.vitima),
        selectinload(Denuncia.ofesor)
    )

    if filtros:
        query = _apply_dashboard_filters(query, filtros)

    return query.order_by(Denuncia.data_public.desc(), Denuncia.id.desc())


def _get_painel_filters():
    per_page = request.args.get("per_page", PAINEL_DEFAULT_PER_PAGE, type=int)
    per_page = min(max(per_page, 5), PAINEL_MAX_PER_PAGE)

    return {
        "q": (request.args.get("q") or "").strip(),
        "status": request.args.get("status") or "",
        "evidencias": request.args.get("evidencias") or "",
        "data_inicio": request.args.get("data_inicio") or "",
        "data_fim": request.args.get("data_fim") or "",
        "sort": request.args.get("sort") or "recentes",
        "per_page": per_page,
    }


def _apply_painel_filters(query, filtros):
    search = filtros["q"]
    status = filtros["status"]
    evidencias = filtros["evidencias"]
    data_inicio = _parse_date(filtros["data_inicio"])
    data_fim = _parse_date(filtros["data_fim"])

    if search:
        term = f"%{search}%"
        query = query.filter(or_(
            Denuncia.categoria.ilike(term),
            Denuncia.descricao_do_fato.ilike(term),
            Vitima.nome.ilike(term),
            Ofesor.nome.ilike(term),
        ))

    if status in [item.value for item in StatusEnum]:
        query = query.filter(Denuncia.status == status)

    if evidencias == "com":
        query = query.filter(Denuncia.anexos.any())
    elif evidencias == "sem":
        query = query.filter(~Denuncia.anexos.any())

    if data_inicio:
        query = query.filter(Denuncia.data_public >= data_inicio)

    if data_fim:
        query = query.filter(Denuncia.data_public <= data_fim)

    return query


def _apply_painel_sort(query, sort):
    if sort == "antigas":
        return query.order_by(Denuncia.data_public.asc(), Denuncia.id.asc())

    if sort == "status":
        return query.order_by(Denuncia.status.asc(), Denuncia.data_public.desc(), Denuncia.id.desc())

    if sort == "categoria":
        return query.order_by(Denuncia.categoria.asc(), Denuncia.data_public.desc(), Denuncia.id.desc())

    return query.order_by(Denuncia.data_public.desc(), Denuncia.id.desc())


def _build_page_url(page, query_params):
    params = query_params.copy()
    params["page"] = page
    return url_for("admin.painel", **params)


def _build_page_links(pagination, query_params):
    links = []

    for page in pagination.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1):
        if page is None:
            links.append({"page": None, "url": None, "active": False})
        else:
            links.append({
                "page": page,
                "url": _build_page_url(page, query_params),
                "active": page == pagination.page,
            })

    return links


def _painel_query_params(filtros):
    query_params = {}

    for key, value in filtros.items():
        if key == "per_page" and value == PAINEL_DEFAULT_PER_PAGE:
            continue

        if value not in (None, ""):
            query_params[key] = value

    return query_params


def _painel_summary():
    return {
        "total": Denuncia.query.count(),
        "pendentes": Denuncia.query.filter(Denuncia.status == StatusEnum.PENDENTE.value).count(),
        "em_analise": Denuncia.query.filter(Denuncia.status == StatusEnum.EM_ANALISE.value).count(),
        "finalizadas": Denuncia.query.filter(Denuncia.status == StatusEnum.FINALIZADO.value).count(),
    }


def _record_change(denuncia, campo, old_value, new_value):
    old_text = "" if old_value is None else str(old_value)
    new_text = "" if new_value is None else str(new_value)

    if old_text == new_text:
        return

    user_id = int(current_user.get_id()) if current_user and current_user.get_id() else None

    db.session.add(DenunciaHistorico(
        denuncia_id=denuncia.id,
        usuario_id=user_id,
        campo=campo,
        valor_anterior=old_text,
        valor_novo=new_text
    ))

def _clean_limited_text(value, max_length):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("O campo deve conter um texto.")

    text = value.strip()

    if not text:
        return None

    if len(text) > max_length:
        raise ValueError(f"O campo excede o limite de {max_length} caracteres.")

    return text


@admin_bp.route("/", methods=["GET"])
@login_required
def index_page():
    return render_template("index.html")

@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login_admin():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("password") or ""

        user_obj = (
            db.session.query(Usuario)
            .filter(Usuario.email == email)
            .first()
        )

        if not user_obj:
            flash("Usuário ou senha inválidos", "error")
            return render_template("login_adm.html")

        if not user_obj.check_password(senha):
            flash("Usuário ou senha inválidos", "error")
            return render_template("login_adm.html")

        login_user(user_obj)
                
        return redirect(url_for("admin.index_page"))

    
    return render_template("login_adm.html")

@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login_admin"))

# ============== Painel ADM ====================

@admin_bp.route('/painel', methods=['GET'])
@login_required
def painel():
    page = request.args.get("page", 1, type=int)
    filtros = _get_painel_filters()
    query_params = _painel_query_params(filtros)

    query = (
        Denuncia.query
        .options(
            selectinload(Denuncia.vitima),
            selectinload(Denuncia.ofesor),
            selectinload(Denuncia.anexos),
            selectinload(Denuncia.historicos).selectinload(DenunciaHistorico.usuario),
        )
        .join(Vitima, Denuncia.vitima_id == Vitima.id)
        .join(Ofesor, Denuncia.ofesor_id == Ofesor.id)
    )
    query = _apply_painel_filters(query, filtros)
    query = _apply_painel_sort(query, filtros["sort"])

    pagination = query.paginate(
        page=max(page, 1),
        per_page=filtros["per_page"],
        error_out=False
    )
    denuncias_dict = [d.to_dict() for d in pagination.items]

    return render_template(
        "painel_denuncias.html",
        denuncias=denuncias_dict,
        pagination=pagination,
        page_links=_build_page_links(pagination, query_params),
        previous_url=_build_page_url(pagination.prev_num, query_params) if pagination.has_prev else None,
        next_url=_build_page_url(pagination.next_num, query_params) if pagination.has_next else None,
        filtros=filtros,
        resumo=_painel_summary(),
        total_filtrado=pagination.total,
        status_options=STATUS_OPTIONS,
        severidade_options=[("", "Não definida"), *SEVERIDADES],
        sort_options=SORT_OPTIONS,
        prazo_pendente_dias=PRAZO_PENDENTE_DIAS,
    )


@admin_bp.route("/anexos/<int:anexo_id>", methods=["GET"])
@login_required
def visualizar_anexo(anexo_id):
    anexo = DenunciaAnexos.query.get_or_404(anexo_id)
    filename = os.path.basename(anexo.file_path)

    if not filename:
        abort(404)

    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=False,
        download_name=anexo.original_name
    )

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; media-src 'self'"
    return response




@admin_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    try:
        filtros = _get_dashboard_filters()
        query_params = _dashboard_query_params(filtros)
        query = _dashboard_filtered_query(filtros)

        qtd_denuncias = query.count()

        data_hoje = date.today()
        denuncias_do_dia = query.filter(Denuncia.data_public == data_hoje).count()
        denuncias_em_analise = query.filter(Denuncia.status == StatusEnum.EM_ANALISE.value).count()

        return render_template(
            "dashboard.html",
            qtd_denuncias=qtd_denuncias,
            denuncias_em_analise=denuncias_em_analise,
            denuncias_do_dia=denuncias_do_dia,
            filtros=filtros,
            status_options=STATUS_OPTIONS,
            severidade_options=SEVERIDADE_OPTIONS,
            evidencias_options=EVIDENCIAS_OPTIONS,
            export_csv_url=url_for("admin.exportar_csv", **query_params),
            export_excel_url=url_for("admin.exportar_excel", **query_params),
            export_pdf_url=url_for("admin.exportar_pdf", **query_params),
        )
    except Exception as e:
        current_app.logger.exception("Erro ao carregar dashboard.")
        return jsonify({"error": "Erro ao carregar dashboard."}), 500

@admin_bp.route("/filter", methods=["POST"])
@login_required
def filter_dashboard():
    try:
        filtros = _get_dashboard_filters(request.form)
        return redirect(url_for("admin.dashboard", **_dashboard_query_params(filtros)))
    except Exception as e:
        current_app.logger.exception("Erro ao aplicar filtro do dashboard.")
        return jsonify({"error": "Erro ao aplicar filtro."}), 500
    
    
@admin_bp.route("/filter/quantidade_status", methods=["GET"])
@login_required
def quatidade_status():
    try:
        filtros = _get_dashboard_filters()
        query = _dashboard_filtered_query(filtros, include_status=False)
        qtd_recebida = query.filter(Denuncia.status == StatusEnum.PENDENTE.value).count()
        qtd_em_analise = query.filter(Denuncia.status == StatusEnum.EM_ANALISE.value).count()
        qtd_suspenso = query.filter(Denuncia.status == StatusEnum.SUSPENSO.value).count()
        qtd_encerrada = query.filter(Denuncia.status == StatusEnum.FINALIZADO.value).count()

        return jsonify({
            "pendente": qtd_recebida,
            "em_analise": qtd_em_analise,
            "suspenso": qtd_suspenso,
            "encerrada": qtd_encerrada
        }), 200
    except Exception as e:
        current_app.logger.exception("Erro ao carregar quantidade por status.")
        return jsonify({"error": "Erro ao carregar indicadores."}), 500


@admin_bp.route("/filter/severidade", methods=["GET"])
@login_required
def quantidade_severidade():
    try:
        filtros = _get_dashboard_filters()
        query = _dashboard_filtered_query(filtros, include_severidade=False)
        labels = [label for _, label in SEVERIDADES]
        values = [
            query.filter(Denuncia.severidade == value).count()
            for value, _ in SEVERIDADES
        ]
        labels.append("Não definida")
        values.append(query.filter(or_(Denuncia.severidade.is_(None), Denuncia.severidade == "")).count())

        return jsonify({"labels": labels, "values": values}), 200
    except Exception as e:
        current_app.logger.exception("Erro ao carregar quantidade por severidade.")
        return jsonify({"error": "Erro ao carregar severidades."}), 500
    
    
# @admin_bp.route("/denuncia/<int:id>/finalizar", methods=["POST"])
# @login_required
# def finalizar_denuncia(id):
#     print("CHEGOU NA ROTA FINALIZAR")
#     print("ID RECEBIDO:", id)

#     denuncia = Denuncia.query.get_or_404(id)

#     print("STATUS ANTES:", denuncia.status)

#     denuncia.status = "finalizado"

#     db.session.commit()

#     print("STATUS DEPOIS:", denuncia.status)

#     return jsonify({
#         "sucesso": True,
#         "novo_status": denuncia.status
#     }), 200


@admin_bp.route("/denuncia/<int:id>/atualizar", methods=["POST"])
@login_required
def atualizar_denuncia(id):
    denuncia = Denuncia.query.get_or_404(id)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "sucesso": False,
            "mensagem": "Envie um objeto JSON válido."
        }), 400

    campos = {}

    try:
        if "status" in data:
            status = data["status"]

            if status not in [item.value for item in StatusEnum]:
                raise ValueError("Status inválido.")

            campos["Status"] = ("status", status)

        if "severidade" in data:
            severidade = _clean_limited_text(data["severidade"], 25)

            if severidade is not None and severidade not in [value for value, _ in SEVERIDADES]:
                raise ValueError("Severidade inválida.")

            campos["Severidade"] = ("severidade", severidade)

        campos_texto = {
            "responsavel": ("Responsável", 150),
            "depoimento_vitima": ("Depoimento da vítima", 10000),
            "depoimento_acusado": ("Depoimento do acusado", 10000),
            "depoimento_testemunha": ("Depoimento das testemunhas", 10000),
            "depoimento_admin": ("Observações da administração", 10000),
        }

        for attr, (label, max_length) in campos_texto.items():
            if attr in data:
                campos[label] = (attr, _clean_limited_text(data[attr], max_length))

        if not campos:
            raise ValueError("Nenhuma alteração válida foi informada.")
    except ValueError as exc:
        return jsonify({
            "sucesso": False,
            "mensagem": str(exc)
        }), 400

    try:
        for label, (attr, new_value) in campos.items():
            old_value = getattr(denuncia, attr)
            _record_change(denuncia, label, old_value, new_value)
            setattr(denuncia, attr, new_value)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao atualizar denúncia %s.", id)
        return jsonify({
            "sucesso": False,
            "mensagem": "Não foi possível atualizar a denúncia."
        }), 500

    return jsonify({
        "sucesso": True,
        "mensagem": "Denúncia atualizada com sucesso.",
        "novo_status": denuncia.status
    }), 200
    
    
@admin_bp.route("/meses-denuncias")
@login_required
def meses_denuncias():
    filtros = _get_dashboard_filters()
    query = db.session.query(
        extract('month', Denuncia.data_public),
        func.count(Denuncia.id)
    ).select_from(Denuncia)
    query = _apply_dashboard_filters(query, filtros)
    query = query.filter(Denuncia.data_public.isnot(None))

    if not filtros["data_inicio"] and not filtros["data_fim"]:
        query = query.filter(extract('year', Denuncia.data_public) == date.today().year)

    counts = dict(
        query
        .group_by(extract('month', Denuncia.data_public))
        .all()
    )
    meses = [counts.get(i, 0) for i in range(1, 13)]
        
    return jsonify({
        "Jan": meses[0] or 0,
        "Fev": meses[1] or 0,
        "Mar": meses[2] or 0,
        "Abr": meses[3] or 0,
        "Mai": meses[4] or 0,
        "Jun": meses[5] or 0,
        "Jul": meses[6] or 0,
        "Ago": meses[7] or 0,
        "Set": meses[8] or 0,
        "Out": meses[9] or 0,
        "Nov": meses[10] or 0,
        "Dez": meses[11] or 0     
    })
    

@admin_bp.route("/denuncia/<int:id>/exportar/csv")
@login_required
def exportar_denuncia_csv(id):
    denuncia = (
        Denuncia.query
        .options(selectinload(Denuncia.vitima), selectinload(Denuncia.ofesor))
        .get_or_404(id)
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Categoria", "Data", "Status", "Severidade", "Responsável",
        "Vítima", "Telefone", "Email", "Ofensor", "Descrição"
    ])
    writer.writerow([
        _safe_export_value(denuncia.id),
        _safe_export_value(denuncia.categoria),
        _safe_export_value(denuncia.data),
        _safe_export_value(denuncia.status),
        _safe_export_value(denuncia.severidade),
        _safe_export_value(denuncia.responsavel),
        _safe_export_value(denuncia.vitima.nome if denuncia.vitima else ""),
        _safe_export_value(denuncia.vitima.telefone if denuncia.vitima else ""),
        _safe_export_value(denuncia.vitima.email if denuncia.vitima else ""),
        _safe_export_value(denuncia.ofesor.nome if denuncia.ofesor else ""),
        _safe_export_value(denuncia.descricao_do_fato),
    ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=denuncia_{denuncia.id}.csv"}
    )


@admin_bp.route("/exportar/csv")
@login_required
def exportar_csv():
    filtros = _get_dashboard_filters()

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Categoria", "Data", "Status", "Severidade",
                         "Responsável", "Vítima", "Ofensor", "Descrição"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for d in _export_denuncias_query(filtros).yield_per(100):
            writer.writerow([
                _safe_export_value(d.id),
                _safe_export_value(d.categoria),
                _safe_export_value(d.data),
                _safe_export_value(d.status),
                _safe_export_value(d.severidade),
                _safe_export_value(d.responsavel),
                _safe_export_value(d.vitima.nome if d.vitima else ""),
                _safe_export_value(d.ofesor.nome if d.ofesor else ""),
                _safe_export_value(d.descricao_do_fato)
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=denuncias.csv"}
    )

@admin_bp.route("/exportar/excel")
@login_required
def exportar_excel():
    from openpyxl import Workbook

    filtros = _get_dashboard_filters()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Denúncias")

    headers = ["ID", "Categoria", "Data", "Status", "Severidade",
               "Responsável", "Vítima", "Ofensor", "Descrição"]
    ws.append(headers)

    for d in _export_denuncias_query(filtros).yield_per(100):
        ws.append([
            _safe_export_value(d.id),
            _safe_export_value(d.categoria),
            _safe_export_value(str(d.data) if d.data else ""),
            _safe_export_value(d.status),
            _safe_export_value(d.severidade),
            _safe_export_value(d.responsavel),
            _safe_export_value(d.vitima.nome if d.vitima else ""),
            _safe_export_value(d.ofesor.nome if d.ofesor else ""),
            _safe_export_value(d.descricao_do_fato)
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return Response(
        output.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=denuncias.xlsx"}
    )


@admin_bp.route("/exportar/pdf")
@login_required
def exportar_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    filtros = _get_dashboard_filters()
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    elements = [
        Paragraph("Relatório de Denúncias", styles["Title"]),
        Spacer(1, 0.3 * cm),
    ]

    rows = [["ID", "Categoria", "Data", "Status", "Severidade", "Responsável", "Vítima", "Ofensor"]]

    for d in _export_denuncias_query(filtros).yield_per(100):
        rows.append([
            Paragraph(escape(_safe_export_value(d.id)), cell_style),
            Paragraph(escape(_safe_export_value(d.categoria)), cell_style),
            Paragraph(escape(_safe_export_value(d.data.strftime("%d/%m/%Y") if d.data else "")), cell_style),
            Paragraph(escape(_safe_export_value(d.status)), cell_style),
            Paragraph(escape(_safe_export_value(d.severidade or "Não definida")), cell_style),
            Paragraph(escape(_safe_export_value(d.responsavel or "")), cell_style),
            Paragraph(escape(_safe_export_value(d.vitima.nome if d.vitima else "")), cell_style),
            Paragraph(escape(_safe_export_value(d.ofesor.nome if d.ofesor else "")), cell_style),
        ])

    if len(rows) == 1:
        rows.append(["-", "Nenhuma denúncia encontrada", "", "", "", "", "", ""])

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[1.2 * cm, 4 * cm, 2.2 * cm, 2.5 * cm, 2.7 * cm, 4 * cm, 4.5 * cm, 4.5 * cm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ]))
    elements.append(table)
    doc.build(elements)
    output.seek(0)

    return Response(
        output.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=denuncias.pdf"}
    )

from flask import Blueprint, redirect, request, url_for
from flask_login import login_required

exportar_bp = Blueprint("export", __name__, url_prefix="/export")

@exportar_bp.route("/exportar/csv")
@login_required
def exportar_csv():
    return redirect(url_for("admin.exportar_csv", **request.args.to_dict()))
    
@exportar_bp.route("/exportar/excel", methods=["GET"])
@login_required
def exportar_excel():
    return redirect(url_for("admin.exportar_excel", **request.args.to_dict()))

@exportar_bp.route("/exportar/pdf", methods=["GET"])
@login_required
def exportar_pdf():
    return redirect(url_for("admin.exportar_pdf", **request.args.to_dict()))

from flask import (
    Flask,
    jsonify,
    render_template,
    request
)
from flask_login import (
    LoginManager
)

from src.settings.config import Config
from src.settings.extensions import db, csrf, limiter
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import IntegrityError
import os

app = Flask(
    __name__,
    template_folder="src/views/templates",
    static_folder="src/views/static"
)
app.config.from_object(Config)

trusted_proxy_hops = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
if trusted_proxy_hops > 0:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=trusted_proxy_hops,
        x_proto=trusted_proxy_hops,
        x_host=trusted_proxy_hops,
        x_port=trusted_proxy_hops,
    )

db.init_app(app=app)
csrf.init_app(app)
limiter.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "admin.login_admin"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")

    if request.path.startswith(("/admin", "/export", "/denuncias")):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    return response

# Models para importa o metadata
from src.models import Usuario_model
from src.models import Vitima_model
from src.models import Ofensor_model
from src.models import Denuncia_model
from src.models import Denuncia_anexos_model
from src.models import Denuncia_historico_model

# Import Controllers

from src.controllers.admin.login_admin_controller import admin_bp
from src.controllers.users.denuncia_controller import denuncia_bp
from src.controllers.admin.exportar_controller import exportar_bp

# Register Routes

app.register_blueprint(admin_bp) 
app.register_blueprint(denuncia_bp)
app.register_blueprint(exportar_bp)

# Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Usuario_model.Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


def create_admin_from_env():
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or ""
    name = (os.getenv("ADMIN_NAME") or "Administrador").strip() or "Administrador"

    if not email and not password:
        return "skipped"

    if not email or not password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set together.")

    if len(password) < 8:
        raise RuntimeError("ADMIN_PASSWORD must have at least 8 characters.")

    existing_user = Usuario_model.Usuario.query.filter(Usuario_model.Usuario.email == email).first()

    if existing_user:
        return "exists"

    db.session.add(Usuario_model.Usuario(name, email, password))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return "exists"

    return "created"


@app.cli.command("create-admin")
def create_admin_command():
    result = create_admin_from_env()

    if result == "created":
        print("Admin user created.")
    elif result == "exists":
        print("Admin user already exists.")
    else:
        print("ADMIN_EMAIL/ADMIN_PASSWORD not set; skipping admin creation.")

# Main
@app.route("/", methods=["GET"])
def index():
    return render_template("indexUser.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))
    app.run(host=host, port=port, debug=debug)

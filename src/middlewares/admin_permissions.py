from functools import wraps

from flask import abort, session
from flask_login import current_user, login_required

from src.models.Usuario_model import Usuario


def principal_required(view):
    @wraps(view)
    @login_required
    def protected(*args, **kwargs):
        if not current_user.administrador_principal:
            abort(403, description="Esta seção é exclusiva de administradores principais.")
        return view(*args, **kwargs)

    return protected


def lock_management_access():
    # Serializa mudanças de permissão e revalida o autor após obter o lock.
    # Isso impede que dois principais desativem um ao outro simultaneamente.
    principais = (
        Usuario.query.filter_by(ativo=True, administrador_principal=True)
        .order_by(Usuario.id)
        .populate_existing()
        .with_for_update()
        .all()
    )
    if current_user.id not in {usuario.id for usuario in principais}:
        abort(403, description="Seu acesso à gestão foi alterado. Entre novamente no sistema.")
    if current_user.get_id() != session.get("_user_id"):
        abort(403, description="Sua sessão foi revogada. Entre novamente no sistema.")
    return principais

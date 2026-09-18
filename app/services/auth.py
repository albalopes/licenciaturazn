from app.models import User
from app.services.suap import current_user_data
from app.extensions import db


def _normalized_admin_identifiers(data: dict) -> set[str]:
    """Retorna todos os identificadores úteis do usuário SUAP, normalizados."""
    candidates = [
        data.get("username"),
        data.get("matricula"),
        data.get("registration"),
        data.get("id"),
        data.get("pk"),
        data.get("identificacao"),
        data.get("email"),
    ]
    return {str(value).strip().lower() for value in candidates if value not in (None, "")}


def upsert_suap_user(data: dict) -> User:
    suap_id = str(data.get("id") or data.get("pk") or data.get("matricula") or data.get("username"))
    username = str(data.get("username") or data.get("matricula") or suap_id)
    name = data.get("nome") or data.get("name") or username
    email = data.get("email")
    registration = data.get("matricula") or data.get("registration")

    user = User.query.filter_by(suap_id=suap_id).first()
    if not user:
        user = User(suap_id=suap_id)
        db.session.add(user)
    user.username = username
    user.name = name
    user.email = email
    user.registration = registration

    # O SUAP pode devolver username, matrícula, id ou outros identificadores
    # dependendo do endpoint/versão da API. A configuração ADMIN_SUAP_USERS
    # aceita qualquer um desses identificadores, separados por vírgulas.
    configured_admins = __import__("flask").current_app.config["ADMIN_SUAP_USERS"]
    identifiers = _normalized_admin_identifiers(data)
    user.is_admin = bool(identifiers & configured_admins)

    db.session.commit()
    return user

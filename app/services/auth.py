from app.models import User
from app.services.suap import current_user_data
from app.extensions import db


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
    user.is_admin = username.lower() in __import__("flask").current_app.config["ADMIN_SUAP_USERS"]
    db.session.commit()
    return user

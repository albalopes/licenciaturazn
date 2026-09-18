import secrets

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_user, logout_user

from app.services.auth import upsert_suap_user
from app.services.suap import SuapOAuthError, authorization_url, current_user_data, exchange_code, store_tokens

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard" if current_user.is_admin else "public.home"))
    if not current_app_is_configured():
        return render_template("auth/login.html", oauth_configured=False)
    state = secrets.token_urlsafe(32)
    session["suap_oauth_state"] = state
    return redirect(authorization_url(state))


def current_app_is_configured():
    from flask import current_app
    return bool(current_app.config.get("SUAP_CLIENT_ID") and current_app.config.get("SUAP_CLIENT_SECRET"))


@bp.get("/suap/callback")
def callback():
    from flask import request

    state = request.args.get("state")
    code = request.args.get("code")
    if not state or state != session.pop("suap_oauth_state", None):
        flash("Estado de autenticação inválido. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))
    if not code:
        flash("O SUAP não retornou um código de autorização.", "danger")
        return redirect(url_for("auth.login"))
    try:
        token_data = exchange_code(code)
        store_tokens(token_data)
        data = current_user_data()
        user = upsert_suap_user(data)
        if not user.is_admin:
            session.clear()
            flash("Seu usuário foi autenticado, mas não possui acesso à área administrativa.", "warning")
            return redirect(url_for("public.home"))
        login_user(user, remember=False)
        session.permanent = True
        flash(f"Bem-vindo(a), {user.name}.", "success")
        return redirect(url_for("admin.dashboard"))
    except (SuapOAuthError, ValueError) as exc:
        session.clear()
        flash(f"Não foi possível autenticar pelo SUAP: {exc}", "danger")
        return redirect(url_for("auth.login"))


@bp.get("/logout")
def logout():
    logout_user()
    session.clear()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("public.home"))

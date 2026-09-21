from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from flask import current_app, session


class SuapOAuthError(Exception):
    pass


def authorization_url(state: str):
    params = {
        "response_type": "code",
        "client_id": current_app.config["SUAP_CLIENT_ID"],
        "redirect_uri": current_app.config["SUAP_REDIRECT_URI"],
        "scope": current_app.config["SUAP_SCOPE"],
        "state": state,
    }
    return f"{current_app.config['SUAP_AUTH_URL']}?{urlencode(params)}"


def exchange_code(code: str):
    response = requests.post(
        current_app.config["SUAP_TOKEN_URL"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": current_app.config["SUAP_REDIRECT_URI"],
            "client_id": current_app.config["SUAP_CLIENT_ID"],
            "client_secret": current_app.config["SUAP_CLIENT_SECRET"],
        },
        timeout=15,
    )
    if not response.ok:
        raise SuapOAuthError(f"SUAP token endpoint returned HTTP {response.status_code}.")
    return response.json()


def refresh_access_token(refresh_token: str):
    response = requests.post(
        current_app.config["SUAP_TOKEN_URL"],
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": current_app.config["SUAP_CLIENT_ID"],
            "client_secret": current_app.config["SUAP_CLIENT_SECRET"],
        },
        timeout=15,
    )
    if not response.ok:
        raise SuapOAuthError(f"SUAP refresh endpoint returned HTTP {response.status_code}.")
    return response.json()


def store_tokens(token_data: dict):
    session["suap_access_token"] = token_data["access_token"]
    if token_data.get("refresh_token"):
        session["suap_refresh_token"] = token_data["refresh_token"]
    expires_in = int(token_data.get("expires_in", 36000))
    session["suap_token_expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).timestamp()


def ensure_access_token():
    access_token = session.get("suap_access_token")
    expires_at = session.get("suap_token_expires_at", 0)
    if access_token and datetime.now(timezone.utc).timestamp() < expires_at - 60:
        return access_token
    refresh_token = session.get("suap_refresh_token")
    if not refresh_token:
        return None
    data = refresh_access_token(refresh_token)
    store_tokens(data)
    return data.get("access_token")


def api_get(endpoint: str, params: dict | None = None):
    """GET em um endpoint relativo à base /api/ atual do SUAP."""
    token = ensure_access_token()
    if not token:
        raise SuapOAuthError("No SUAP access token in session.")

    url = current_app.config["SUAP_API_BASE_URL"].rstrip("/") + "/" + endpoint.lstrip("/")
    response = requests.get(
        url,
        params=params or {},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20,
    )
    if response.status_code == 401:
        session.pop("suap_access_token", None)
        session.pop("suap_token_expires_at", None)
        raise SuapOAuthError("SUAP access token expired or unauthorized.")
    if response.status_code == 403:
        raise SuapOAuthError("SUAP API denied access to this resource (HTTP 403).")
    if response.status_code == 404:
        raise SuapOAuthError(f"SUAP API resource not found: {endpoint} (HTTP 404).")
    if not response.ok:
        raise SuapOAuthError(f"SUAP API returned HTTP {response.status_code}.")
    return response.json()


def current_user_data():
    return api_get(current_app.config["SUAP_ENDPOINT_ME"])


def my_links():
    return api_get(current_app.config["SUAP_ENDPOINT_MY_LINKS"])


def my_personal_data():
    return api_get(current_app.config["SUAP_ENDPOINT_MY_DATA"])


def my_student_data():
    return api_get(current_app.config["SUAP_ENDPOINT_STUDENT_DATA"])


def my_periods():
    return api_get(current_app.config["SUAP_ENDPOINT_PERIODS"])


def my_virtual_classes(year: int | None = None, period: int | None = None):
    endpoint = current_app.config["SUAP_ENDPOINT_VIRTUAL_CLASSES"]
    if "{year}" in endpoint or "{period}" in endpoint:
        if year is None or period is None:
            raise SuapOAuthError("Ano e período são necessários para consultar as turmas virtuais.")
        endpoint = endpoint.format(year=year, period=period)
    return api_get(endpoint)


def my_disciplines(year: int, period: int):
    endpoint = current_app.config["SUAP_ENDPOINT_DISCIPLINES"].format(year=year, period=period)
    return api_get(endpoint)


def my_completion_requirements():
    return api_get(current_app.config["SUAP_ENDPOINT_COMPLETION_REQUIREMENTS"])


def my_frequency(year: int, period: int):
    endpoint = current_app.config["SUAP_ENDPOINT_FREQUENCY"].format(year=year, period=period)
    return api_get(endpoint)


def my_upcoming_evaluations():
    return api_get(current_app.config["SUAP_ENDPOINT_UPCOMING_EVALUATIONS"])


def my_calendar(year: int, period: int):
    endpoint = current_app.config["SUAP_ENDPOINT_CALENDAR"].format(year=year, period=period)
    return api_get(endpoint)


def my_report(year: int, period: int):
    endpoint = current_app.config["SUAP_ENDPOINT_REPORT"].format(year=year, period=period)
    return api_get(endpoint)


def my_schedule(year: int, period: int):
    endpoint = current_app.config["SUAP_ENDPOINT_SCHEDULE"].format(year=year, period=period)
    return api_get(endpoint)


def api_get_custom(endpoint: str, params: dict | None = None):
    """Consulta genérica para qualquer endpoint documentado pelo SUAP."""
    return api_get(endpoint, params=params)


def api_get_url(url: str):
    """Consulta uma URL `next` fornecida pelo próprio SUAP, mantendo o token."""
    base = urlparse(current_app.config["SUAP_BASE_URL"])
    target = urlparse(url)
    if target.netloc and target.netloc != base.netloc:
        raise SuapOAuthError("SUAP next URL points to an unexpected host.")
    endpoint = target.path
    if endpoint.startswith("/api/"):
        endpoint = endpoint[len("/api/"):]
    return api_get(endpoint, params={k: v[-1] for k, v in parse_qs(target.query).items()})

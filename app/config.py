import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://licenciatura:licenciatura@localhost:3306/licenciaturazn"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None

    SUAP_BASE_URL = os.getenv("SUAP_BASE_URL", "https://suap.ifrn.edu.br")
    SUAP_AUTH_URL = os.getenv("SUAP_AUTH_URL", f"{SUAP_BASE_URL}/o/authorize/")
    SUAP_TOKEN_URL = os.getenv("SUAP_TOKEN_URL", f"{SUAP_BASE_URL}/o/token/")
    SUAP_API_BASE_URL = os.getenv("SUAP_API_BASE_URL", f"{SUAP_BASE_URL}/api/")
    SUAP_CLIENT_ID = os.getenv("SUAP_CLIENT_ID", "")
    SUAP_CLIENT_SECRET = os.getenv("SUAP_CLIENT_SECRET", "")
    SUAP_REDIRECT_URI = os.getenv("SUAP_REDIRECT_URI", "http://localhost:5003/auth/suap/callback")
    SUAP_SCOPE = os.getenv("SUAP_SCOPE", "read identificacao email")
    # Endpoints atuais documentados na API /api/.
    SUAP_ENDPOINT_ME = os.getenv("SUAP_ENDPOINT_ME", "rh/eu/")
    SUAP_ENDPOINT_MY_LINKS = os.getenv("SUAP_ENDPOINT_MY_LINKS", "rh/meus-vinculos/")
    SUAP_ENDPOINT_MY_DATA = os.getenv("SUAP_ENDPOINT_MY_DATA", "rh/meus-dados/")
    SUAP_ENDPOINT_STUDENT_DATA = os.getenv("SUAP_ENDPOINT_STUDENT_DATA", "ensino/meus-dados-aluno/")
    SUAP_ENDPOINT_PERIODS = os.getenv("SUAP_ENDPOINT_PERIODS", "ensino/periodos/")
    SUAP_ENDPOINT_SERVERS = os.getenv("SUAP_ENDPOINT_SERVERS", "rh/servidores/")
    SUAP_CAMPUS_SIGLA = os.getenv("SUAP_CAMPUS_SIGLA", "ZN")
    SUAP_ENDPOINT_PROJECTS_RESEARCH = os.getenv("SUAP_ENDPOINT_PROJECTS_RESEARCH", "pesquisa/projetos/")
    SUAP_ENDPOINT_PROJECTS_EXTENSION = os.getenv("SUAP_ENDPOINT_PROJECTS_EXTENSION", "extensao/projetos/")
    SUAP_ENDPOINT_PROJECTS_TEACHING = os.getenv("SUAP_ENDPOINT_PROJECTS_TEACHING", "")
    SUAP_PROJECT_CAMPUS = os.getenv("SUAP_PROJECT_CAMPUS", "Natal-Zona Norte")
    # Endpoints de diário permanecem configuráveis para acompanhar mudanças da documentação.
    SUAP_ENDPOINT_VIRTUAL_CLASSES = os.getenv("SUAP_ENDPOINT_VIRTUAL_CLASSES", "ensino/minhas-turmas-virtuais/{year}/{period}/")
    SUAP_ENDPOINT_REPORT = os.getenv("SUAP_ENDPOINT_REPORT", "ensino/meu-boletim/{year}/{period}/")
    SUAP_ENDPOINT_DISCIPLINES = os.getenv("SUAP_ENDPOINT_DISCIPLINES", "ensino/disciplinas/{year}.{period}/")
    SUAP_ENDPOINT_COMPLETION_REQUIREMENTS = os.getenv("SUAP_ENDPOINT_COMPLETION_REQUIREMENTS", "ensino/requisitos-conclusao/")
    SUAP_ENDPOINT_FREQUENCY = os.getenv("SUAP_ENDPOINT_FREQUENCY", "ensino/frequencia-periodo-letivo/{year}/{period}/")
    SUAP_ENDPOINT_UPCOMING_EVALUATIONS = os.getenv("SUAP_ENDPOINT_UPCOMING_EVALUATIONS", "ensino/minhas-proximas-avaliacoes/")
    SUAP_ENDPOINT_CALENDAR = os.getenv("SUAP_ENDPOINT_CALENDAR", "ensino/meu-calendario-academico/{year}/{period}/")
    SUAP_ENDPOINT_SCHEDULE = os.getenv("SUAP_ENDPOINT_SCHEDULE", "meu-diario/horario/{year}/{period}/")
    ADMIN_SUAP_USERS = {item.strip().lower() for item in os.getenv("ADMIN_SUAP_USERS", "").split(",") if item.strip()}
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    KNOWLEDGE_UPLOAD_DIR = os.getenv("KNOWLEDGE_UPLOAD_DIR", "knowledge_documents")

    @staticmethod
    def admin_suap_users():
        raw = os.getenv("ADMIN_SUAP_USERS", "")
        return {item.strip().lower() for item in raw.split(",") if item.strip()}


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

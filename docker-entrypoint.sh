#!/bin/sh
set -eu

MAX_RETRIES="${DB_STARTUP_RETRIES:-30}"
RETRY_DELAY="${DB_STARTUP_RETRY_DELAY:-2}"

python - <<'PY'
import os
import sys
import time
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL")
if not url:
    print("ERRO: DATABASE_URL não foi definida.", file=sys.stderr)
    sys.exit(1)

retries = int(os.environ.get("DB_STARTUP_RETRIES", "30"))
delay = float(os.environ.get("DB_STARTUP_RETRY_DELAY", "2"))

last_error = None
for attempt in range(1, retries + 1):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        print(f"Banco de dados disponível (tentativa {attempt}).")
        break
    except Exception as exc:
        last_error = exc
        print(f"Aguardando banco de dados ({attempt}/{retries}): {exc}", file=sys.stderr)
        time.sleep(delay)
else:
    print(f"ERRO: não foi possível conectar ao banco após {retries} tentativas: {last_error}", file=sys.stderr)
    sys.exit(1)
PY

echo "Validando estrutura da aplicação..."
echo "Diretório atual: $(pwd)"
echo "Conteúdo de /app/app (até 2 níveis):"
find /app/app -maxdepth 2 -type f | sort || true

# Validação explícita dos módulos essenciais antes de acessar o banco.
# Isso evita o loop de reinicialização com erros pouco claros e também
# faz o build/deploy denunciar imediatamente se o código do GitHub estiver
# incompleto ou se o contexto de build estiver apontando para outra pasta/branch.
if [ ! -f /app/app/__init__.py ]; then
    echo "ERRO: /app/app/__init__.py não foi encontrado." >&2
    echo "Verifique o branch e o contexto de build configurados no Portainer." >&2
    exit 1
fi

if [ ! -f /app/app/models/__init__.py ]; then
    echo "ERRO: /app/app/models/__init__.py não foi encontrado." >&2
    echo "O pacote app.models é obrigatório para inicializar o banco." >&2
    echo "Verifique se a pasta app/models está no GitHub e se o Portainer está usando o branch correto." >&2
    exit 1
fi

if [ ! -f /app/app/models/project.py ] || [ ! -f /app/app/models/knowledge.py ]; then
    echo "ERRO: arquivos de modelos do portal estão ausentes em /app/app/models/." >&2
    echo "Verifique o conteúdo do repositório/branch usado no build." >&2
    exit 1
fi

python - <<'PY'
import sys

try:
    import app.models as models
    required = ["Discipline", "Matrix", "Project", "SitePage", "KnowledgeSource"]
    missing = [name for name in required if not hasattr(models, name)]
    if missing:
        print("ERRO: app.models foi encontrado, mas faltam modelos: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)
    print("Estrutura validada: app.models e modelos essenciais encontrados.")
except Exception as exc:
    print(f"ERRO ao importar app.models: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "Inicializando/atualizando as tabelas do portal..."
python seed.py

echo "Iniciando Gunicorn na porta ${PORT:-5003}..."
exec gunicorn --bind "0.0.0.0:${PORT:-5003}" --workers "${WEB_CONCURRENCY:-2}" --timeout "${GUNICORN_TIMEOUT:-120}" run:app

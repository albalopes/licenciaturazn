FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# O projeto precisa estar na raiz do contexto de build.
COPY . /app

# Diagnóstico durante o build: se o Portainer estiver usando outro
# branch, outra pasta ou outro contexto, o build falha mostrando o conteúdo recebido.
RUN echo '=== LICENCIATURA ZN: VALIDACAO DO BUILD ===' \
    && echo 'Diretorio de trabalho:' \
    && pwd \
    && echo 'Conteudo da raiz:' \
    && find /app -maxdepth 2 -type f | sort \
    && echo '--- validando pacote app ---' \
    && test -f /app/app/__init__.py \
    && test -f /app/app/models/__init__.py \
    && test -f /app/app/models/project.py \
    && test -f /app/app/models/knowledge.py \
    && echo 'OK: estrutura app/models encontrada.' \
    && python -c "import app.models; print('OK: import app.models realizado durante o build.')"

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5003

ENTRYPOINT ["/app/docker-entrypoint.sh"]

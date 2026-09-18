FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5003

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Falha durante o build se o pacote de modelos não estiver no contexto
# enviado ao Docker/Portainer. Isso evita descobrir o problema somente
# quando o container já estiver em loop de reinicialização.
RUN test -f /app/app/__init__.py \
    && test -f /app/app/models/__init__.py \
    && test -f /app/app/models/project.py \
    && test -f /app/app/models/knowledge.py

RUN chmod +x docker-entrypoint.sh

EXPOSE 5003

ENTRYPOINT ["/app/docker-entrypoint.sh"]

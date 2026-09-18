As migrações são geradas com Flask-Migrate/Alembic.

Com o ambiente virtual ativo:

    flask --app run db init
    flask --app run db migrate -m "initial schema"
    flask --app run db upgrade

No primeiro desenvolvimento, `python seed.py` também pode criar as tabelas diretamente para facilitar o protótipo.

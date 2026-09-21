from flask import Flask

from .config import DevelopmentConfig
from .extensions import csrf, db, login_manager, migrate


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or DevelopmentConfig)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    import json
    app.jinja_env.filters["fromjson"] = json.loads

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .blueprints.public import bp as public_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.api import bp as api_bp
    from .blueprints.chatbot import bp as chatbot_bp
    from .blueprints.student import bp as student_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(chatbot_bp, url_prefix="/assistente")
    app.register_blueprint(student_bp, url_prefix="/aluno")

    return app

"""Fábrica da aplicação Flask (padrão "application factory")."""
from flask import Flask, jsonify
from sqlalchemy import text

from .cli import registrar_comandos
from .config import Config
from .extensions import db


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(config_class)

    db.init_app(app)
    registrar_comandos(app)

    # Importa os models para que o SQLAlchemy conheça todas as tabelas.
    from . import models  # noqa: F401

    # As rotas da API (blueprints) serão registradas nos Passos 3 e 4.

    @app.get("/api/status")
    def status():
        """Verificação de saúde: usado pelo Render e para testes rápidos."""
        try:
            db.session.execute(text("SELECT 1"))
            banco = "ok"
        except Exception as erro:  # noqa: BLE001
            banco = f"erro: {erro.__class__.__name__}"
        codigo = 200 if banco == "ok" else 503
        return jsonify(aplicacao="ok", banco=banco, salao=app.config["SALAO_NOME"]), codigo

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return jsonify(erro="Recurso não encontrado."), 404

    @app.errorhandler(500)
    def erro_interno(_erro):
        db.session.rollback()
        return jsonify(erro="Erro interno no servidor."), 500

    return app

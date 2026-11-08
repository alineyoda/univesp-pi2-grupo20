"""Fábrica da aplicação Flask (padrão "application factory")."""
from flask import Flask, jsonify, render_template
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

    # Rotas da API (blueprints) e tratamento de erros em JSON.
    from .api import registrar_api

    registrar_api(app)

    @app.get("/")
    def pagina_principal():
        """Single Page Application: o roteamento das telas é feito no
        navegador (#/agenda, #/clientes...) e os dados vêm da /api/."""
        return render_template("index.html", salao_nome=app.config["SALAO_NOME"])

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

    return app

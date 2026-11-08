"""Configuração dos testes: banco SQLite em memória (não toca no MySQL)."""
import pytest

from salao import create_app
from salao.config import Config
from salao.extensions import db
from salao.models import Usuario


class ConfigTeste(Config):
    TESTING = True
    SECRET_KEY = "chave-de-teste"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def app():
    app = create_app(ConfigTeste)
    with app.app_context():
        db.create_all()
        for email, perfil in (("admin@salao.com", "admin"), ("atendente@salao.com", "atendente")):
            usuario = Usuario(nome=perfil.title(), email=email, perfil=perfil)
            usuario.definir_senha("senha1234")
            db.session.add(usuario)
        db.session.commit()
    # O contexto é fechado antes dos testes para que cada requisição tenha
    # o seu próprio contexto (e o seu próprio "g"), como em produção.
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _logar(client, email):
    resposta = client.post("/api/auth/login", json={"email": email, "senha": "senha1234"})
    assert resposta.status_code == 200
    return client


@pytest.fixture
def admin(client):
    return _logar(client, "admin@salao.com")


@pytest.fixture
def atendente(client):
    return _logar(client, "atendente@salao.com")

"""Autenticação por sessão (cookie assinado do Flask).

Escolha para o protótipo: como o front-end é servido pelo próprio Flask
(mesma origem), a sessão em cookie é o método mais simples e seguro:
o cookie é HttpOnly (JavaScript não o lê) e SameSite=Lax.

Rotas:
    POST /api/auth/login   {"email": "...", "senha": "..."}
    POST /api/auth/logout
    GET  /api/auth/me      usuário logado
"""
from functools import wraps

from flask import Blueprint, g, jsonify, session

from ..extensions import db
from ..models import Usuario
from .validacao import ErroApi, Validador, obter_json

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ---------------------------------------------------------------------
# Proteção das rotas
# ---------------------------------------------------------------------
def carregar_usuario_logado() -> Usuario | None:
    """Coloca em g.usuario o usuário da sessão (se ainda estiver ativo)."""
    if "usuario" not in g:
        id_usuario = session.get("usuario_id")
        usuario = db.session.get(Usuario, id_usuario) if id_usuario else None
        g.usuario = usuario if usuario and usuario.ativo else None
    return g.usuario


def exigir_login() -> None:
    """Usado como before_request nos blueprints protegidos."""
    if carregar_usuario_logado() is None:
        raise ErroApi("Faça login para continuar.", 401)


def somente_admin(funcao):
    """Decorador: restringe a rota ao perfil 'admin' (ex.: exclusões)."""

    @wraps(funcao)
    def interna(*args, **kwargs):
        usuario = carregar_usuario_logado()
        if usuario is None:
            raise ErroApi("Faça login para continuar.", 401)
        if usuario.perfil != "admin":
            raise ErroApi("Apenas administradores podem realizar esta ação.", 403)
        return funcao(*args, **kwargs)

    return interna


# ---------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------
@bp.post("/login")
def login():
    dados = Validador(obter_json()).texto("email", maximo=160).texto("senha", maximo=200).resultado()
    usuario = Usuario.query.filter_by(email=dados["email"].lower()).first()

    # Mensagem genérica: não revela se o e-mail existe.
    if usuario is None or not usuario.ativo or not usuario.verificar_senha(dados["senha"]):
        raise ErroApi("E-mail ou senha inválidos.", 401)

    session.clear()  # evita reaproveitar uma sessão anterior (session fixation)
    session.permanent = True
    session["usuario_id"] = usuario.id_usuario
    return jsonify(mensagem="Login realizado.", usuario=usuario.to_dict())


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(mensagem="Sessão encerrada.")


@bp.get("/me")
def me():
    usuario = carregar_usuario_logado()
    if usuario is None:
        raise ErroApi("Nenhum usuário logado.", 401)
    return jsonify(usuario.to_dict())

"""API RESTful: registro dos blueprints e tratamento de erros em JSON."""
from flask import Flask, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from ..extensions import db
from . import (agendamentos, auth, clientes, dashboard, notificacoes, pacotes, pagamentos,
               profissionais, servicos)
from .validacao import ErroApi

BLUEPRINTS = (
    auth.bp, clientes.bp, profissionais.bp, servicos.bp,                  # Passo 3
    agendamentos.bp, pagamentos.bp, pacotes.bp, notificacoes.bp,          # Passo 4
    notificacoes.bp_tarefas,
    dashboard.bp,                                                         # Passo 5
)


def registrar_api(app: Flask) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.errorhandler(ErroApi)
    def tratar_erro_api(erro: ErroApi):
        db.session.rollback()
        return jsonify(erro.to_dict()), erro.status

    @app.errorhandler(IntegrityError)
    def tratar_integridade(_erro):
        # Última barreira: o banco recusou (UNIQUE, FK RESTRICT, CHECK).
        db.session.rollback()
        return jsonify(erro="Operação recusada pelo banco: conflito com dados existentes."), 409

    @app.errorhandler(HTTPException)
    def tratar_http(erro: HTTPException):
        # Fora da API (ex.: arquivo estático inexistente) mantém a resposta padrão
        if not request.path.startswith("/api/"):
            return erro
        mensagens = {
            404: "Recurso não encontrado.",
            405: "Método não permitido para este endereço.",
        }
        return jsonify(erro=mensagens.get(erro.code, erro.description)), erro.code

    @app.errorhandler(Exception)
    def tratar_inesperado(erro: Exception):
        if isinstance(erro, HTTPException):
            return tratar_http(erro)
        app.logger.exception("Erro inesperado")
        db.session.rollback()
        return jsonify(erro="Erro interno no servidor."), 500

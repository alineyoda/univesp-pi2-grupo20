"""Comandos de terminal (flask <comando>) para preparar o banco.

Exemplos:
    flask testar-conexao
    flask executar-sql database/schema.sql
    flask executar-sql database/seed.sql
    flask criar-usuario --nome "Admin" --email admin@salao.com --perfil admin
"""
import re

import click
from flask import Flask
from sqlalchemy import text

from .extensions import db
from .models import PERFIS_USUARIO, Usuario


def _dividir_script(conteudo: str) -> list[str]:
    """Separa um arquivo .sql em comandos individuais.

    Remove linhas de comentário (--) e ignora CREATE DATABASE / USE, pois a
    conexão já aponta para o banco configurado no .env (no TiDB/Aiven o
    nome do banco pode ser diferente).
    """
    linhas = [l for l in conteudo.splitlines() if not l.strip().startswith("--")]
    comandos = []
    for comando in "\n".join(linhas).split(";"):
        comando = comando.strip()
        if not comando:
            continue
        if re.match(r"^(CREATE\s+DATABASE|USE\s)", comando, re.IGNORECASE):
            continue
        comandos.append(comando)
    return comandos


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("testar-conexao")
    def testar_conexao():
        """Verifica se o Flask consegue acessar o banco."""
        try:
            with db.engine.connect() as conexao:
                versao = conexao.execute(text("SELECT VERSION()")).scalar()
                banco = conexao.execute(text("SELECT DATABASE()")).scalar()
                hora = conexao.execute(text("SELECT NOW()")).scalar()
            click.secho(f"Conectado! Servidor {versao}, banco '{banco}', hora {hora}.", fg="green")
        except Exception as erro:  # noqa: BLE001 - mostrar qualquer falha ao usuário
            click.secho(f"Falha na conexão: {erro}", fg="red")
            raise SystemExit(1)

    @app.cli.command("executar-sql")
    @click.argument("arquivo", type=click.Path(exists=True, dir_okay=False))
    def executar_sql(arquivo):
        """Executa um script .sql (útil para criar as tabelas na nuvem)."""
        with open(arquivo, encoding="utf-8") as f:
            comandos = _dividir_script(f.read())
        with db.engine.begin() as conexao:
            for comando in comandos:
                conexao.exec_driver_sql(comando)
        click.secho(f"{len(comandos)} comandos executados de {arquivo}.", fg="green")

    @app.cli.command("criar-usuario")
    @click.option("--nome", prompt="Nome")
    @click.option("--email", prompt="E-mail")
    @click.option("--senha", prompt="Senha", hide_input=True, confirmation_prompt=True)
    @click.option("--perfil", type=click.Choice(PERFIS_USUARIO), default="admin", show_default=True)
    def criar_usuario(nome, email, senha, perfil):
        """Cria um usuário para fazer login no sistema."""
        email = email.strip().lower()
        if Usuario.query.filter_by(email=email).first():
            click.secho(f"Já existe um usuário com o e-mail {email}.", fg="yellow")
            return
        if len(senha) < 8:
            click.secho("A senha deve ter pelo menos 8 caracteres.", fg="red")
            raise SystemExit(1)
        usuario = Usuario(nome=nome.strip(), email=email, perfil=perfil)
        usuario.definir_senha(senha)
        db.session.add(usuario)
        db.session.commit()
        click.secho(f"Usuário {email} ({perfil}) criado com sucesso.", fg="green")

"""Configurações da aplicação, lidas de variáveis de ambiente (.env)."""
import os
from datetime import time, timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

# Pasta raiz do projeto (onde ficam app.py, .env, ca.pem...)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _hora(valor: str) -> time:
    """Converte 'HH:MM' em datetime.time."""
    horas, minutos = valor.split(":")
    return time(int(horas), int(minutos))


def montar_url_banco() -> str:
    """Monta a URL de conexão do SQLAlchemy.

    DATABASE_URL, se existir, tem prioridade. Caso contrário, a URL é
    montada a partir de DB_HOST, DB_PORT, DB_USER, DB_PASSWORD e DB_NAME.
    A senha passa por quote_plus para aceitar caracteres como @ e #.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        # Render/Heroku às vezes fornecem "mysql://": forçamos o driver PyMySQL.
        return url.replace("mysql://", "mysql+pymysql://", 1)

    usuario = os.getenv("DB_USER", "root")
    senha = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "localhost")
    porta = os.getenv("DB_PORT", "3306")
    banco = os.getenv("DB_NAME", "salao_agenda")
    return f"mysql+pymysql://{usuario}:{senha}@{host}:{porta}/{banco}?charset=utf8mb4"


def montar_opcoes_conexao() -> dict:
    """Opções extras do driver: SSL (nuvem) e fuso horário da sessão."""
    connect_args = {}

    fuso = os.getenv("DB_TIMEZONE", "-03:00")
    if fuso:
        connect_args["init_command"] = f"SET time_zone = '{fuso}'"

    ca = os.getenv("DB_SSL_CA")
    if ca:
        caminho = ca if os.path.isabs(ca) else os.path.join(BASE_DIR, ca)
        connect_args["ssl"] = {"ca": caminho}

    return {
        "connect_args": connect_args,
        # Testa a conexão antes de usar e recicla conexões antigas:
        # bancos na nuvem derrubam conexões ociosas.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "chave-de-desenvolvimento-troque")
    JSON_SORT_KEYS = False
    JSON_AS_ASCII = False

    # Banco de dados
    SQLALCHEMY_DATABASE_URI = montar_url_banco()
    SQLALCHEMY_ENGINE_OPTIONS = montar_opcoes_conexao()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessão de login (cookies). Expira após 8 horas (um turno de trabalho).
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Regras do salão (horário único para todos os profissionais)
    FUSO_HORARIO = "America/Sao_Paulo"
    SALAO_NOME = os.getenv("SALAO_NOME", "Salão Bela Vida")
    SALAO_ABERTURA = _hora(os.getenv("SALAO_ABERTURA", "08:00"))
    SALAO_FECHAMENTO = _hora(os.getenv("SALAO_FECHAMENTO", "20:00"))
    SALAO_DIAS_FUNCIONAMENTO = [
        int(d) for d in os.getenv("SALAO_DIAS_FUNCIONAMENTO", "0,1,2,3,4,5").split(",")
    ]
    # Intervalo entre os horários livres sugeridos pela agenda
    AGENDA_INTERVALO_MINUTOS = int(os.getenv("AGENDA_INTERVALO_MINUTOS", "15"))

    # WhatsApp
    WHATSAPP_MODO = os.getenv("WHATSAPP_MODO", "simulado")
    LEMBRETE_HORAS_ANTES = int(os.getenv("LEMBRETE_HORAS_ANTES", "24"))
    CRON_TOKEN = os.getenv("CRON_TOKEN", "")

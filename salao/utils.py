"""Funções auxiliares usadas em vários módulos."""
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    """Data/hora atual no horário de Brasília, sem fuso (igual ao DATETIME do banco)."""
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


def serializar(valor):
    """Converte tipos do banco em tipos aceitos pelo JSON."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="minutes")
    if isinstance(valor, date):
        return valor.isoformat()
    return valor

"""Dashboard gerencial: indicadores de volume de atendimentos e faturamento.

    GET /api/dashboard?inicio=AAAA-MM-DD&fim=AAAA-MM-DD
        (padrão: do primeiro dia do mês atual até hoje)

Definições:
- Um agendamento pertence ao período pela data do seu PRIMEIRO serviço.
- Faturamento RECEBIDO = soma dos pagamentos com data no período
  (inclui vendas de pacotes). Faturamento PREVISTO = valor dos
  agendamentos não cancelados do período.
- Ticket médio = valor médio dos agendamentos concluídos.
- Taxa de faltas = faltas / (concluídos + faltas).
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (
    STATUS_AGENDAMENTO,
    Agendamento,
    ItemAgendamento,
    PacoteCliente,
    Pagamento,
    Profissional,
    Servico,
)
from ..services.agenda import ler_data
from ..utils import agora
from .auth import exigir_login
from .validacao import ErroApi

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
bp.before_request(exigir_login)

ZERO = Decimal("0.00")


def _dia(valor) -> str:
    """func.date() devolve date no MySQL e texto no SQLite: normaliza."""
    return str(valor)[:10]


@bp.get("")
def indicadores():
    hoje = agora().date()
    inicio = ler_data(request.args.get("inicio"), hoje.replace(day=1))
    fim = ler_data(request.args.get("fim"), hoje)
    if fim < inicio:
        raise ErroApi("A data final deve ser maior ou igual à inicial.")
    if (fim - inicio).days > 366:
        raise ErroApi("Período máximo de 1 ano.")
    ini_dt = datetime.combine(inicio, time.min)
    fim_dt = datetime.combine(fim + timedelta(days=1), time.min)

    # Data do primeiro serviço de cada agendamento
    primeiro = (
        db.session.query(ItemAgendamento.agendamento_id.label("id"),
                         func.min(ItemAgendamento.data_hora_inicio).label("inicio"))
        .group_by(ItemAgendamento.agendamento_id).subquery()
    )
    no_periodo = (primeiro.c.inicio >= ini_dt) & (primeiro.c.inicio < fim_dt)

    # ---- Agendamentos por status -------------------------------------
    por_status = {s: {"quantidade": 0, "valor": 0.0} for s in STATUS_AGENDAMENTO}
    linhas = (
        db.session.query(Agendamento.status_geral, func.count(), func.coalesce(func.sum(Agendamento.valor_total), 0))
        .join(primeiro, primeiro.c.id == Agendamento.id_agendamento)
        .filter(no_periodo).group_by(Agendamento.status_geral).all()
    )
    for status, quantidade, valor in linhas:
        por_status[status] = {"quantidade": quantidade, "valor": float(valor)}

    concluidos = por_status["concluido"]
    faltas = por_status["falta"]["quantidade"]
    total_ativos = sum(v["quantidade"] for s, v in por_status.items() if s != "cancelado")
    previsto = sum(v["valor"] for s, v in por_status.items() if s not in ("cancelado",))

    # ---- Pagamentos recebidos ----------------------------------------
    pag_periodo = (Pagamento.data_pagamento >= ini_dt) & (Pagamento.data_pagamento < fim_dt)
    recebido = db.session.query(func.coalesce(func.sum(Pagamento.valor_pago), 0)).filter(pag_periodo).scalar()
    recebido_pacotes = (db.session.query(func.coalesce(func.sum(Pagamento.valor_pago), 0))
                        .filter(pag_periodo, Pagamento.pacote_cliente_id.isnot(None)).scalar())
    por_forma = [
        {"forma_pagamento": forma, "quantidade": qtd, "valor": float(valor)}
        for forma, qtd, valor in db.session.query(
            Pagamento.forma_pagamento, func.count(), func.sum(Pagamento.valor_pago))
        .filter(pag_periodo).group_by(Pagamento.forma_pagamento)
        .order_by(func.sum(Pagamento.valor_pago).desc()).all()
    ]

    # ---- Atendimentos (itens) por serviço e por profissional ---------
    itens_validos = (
        db.session.query(ItemAgendamento).join(Agendamento)
        .filter(ItemAgendamento.data_hora_inicio >= ini_dt, ItemAgendamento.data_hora_inicio < fim_dt,
                Agendamento.status_geral != "cancelado")
    )
    top_servicos = [
        {"servico": nome, "quantidade": qtd, "valor": float(valor)}
        for nome, qtd, valor in itens_validos.join(Servico)
        .with_entities(Servico.nome, func.count(ItemAgendamento.id_item), func.sum(ItemAgendamento.subtotal))
        .group_by(Servico.nome).order_by(func.count(ItemAgendamento.id_item).desc()).limit(5).all()
    ]
    por_profissional = [
        {"profissional": nome, "quantidade": qtd, "valor": float(valor),
         "minutos": int(minutos or 0)}
        for nome, qtd, valor, minutos in itens_validos.join(Profissional).join(Servico)
        .with_entities(Profissional.nome, func.count(ItemAgendamento.id_item),
                       func.sum(ItemAgendamento.subtotal), func.sum(Servico.duracao_minutos))
        .group_by(Profissional.nome).order_by(func.count(ItemAgendamento.id_item).desc()).all()
    ]

    # ---- Série diária -------------------------------------------------
    atend_dia = dict(
        db.session.query(func.date(primeiro.c.inicio), func.count())
        .join(Agendamento, primeiro.c.id == Agendamento.id_agendamento)
        .filter(no_periodo, Agendamento.status_geral != "cancelado")
        .group_by(func.date(primeiro.c.inicio)).all()
    )
    receita_dia = dict(
        db.session.query(func.date(Pagamento.data_pagamento), func.sum(Pagamento.valor_pago))
        .filter(pag_periodo).group_by(func.date(Pagamento.data_pagamento)).all()
    )
    atend_dia = {_dia(k): v for k, v in atend_dia.items()}
    receita_dia = {_dia(k): float(v) for k, v in receita_dia.items()}
    serie = []
    dia = inicio
    while dia <= fim:
        chave = dia.isoformat()
        serie.append({"data": chave, "atendimentos": atend_dia.get(chave, 0),
                      "recebido": receita_dia.get(chave, 0.0)})
        dia += timedelta(days=1)

    # ---- Pacotes ------------------------------------------------------
    pacotes_ativos, sessoes_restantes = db.session.query(
        func.count(PacoteCliente.id_pacote_cliente),
        func.coalesce(func.sum(PacoteCliente.qtd_sessoes_total - PacoteCliente.sessoes_realizadas), 0),
    ).filter(PacoteCliente.status_pacote == "ativo").one()

    return jsonify(
        periodo={"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        resumo={
            "agendamentos": total_ativos,
            "concluidos": concluidos["quantidade"],
            "pendentes": por_status["agendado"]["quantidade"] + por_status["confirmado"]["quantidade"],
            "cancelados": por_status["cancelado"]["quantidade"],
            "faltas": faltas,
            "taxa_faltas": round(faltas / (concluidos["quantidade"] + faltas), 3)
            if (concluidos["quantidade"] + faltas) else 0.0,
            "faturamento_recebido": float(recebido or ZERO),
            "faturamento_pacotes": float(recebido_pacotes or ZERO),
            "faturamento_previsto": previsto,
            "ticket_medio": round(concluidos["valor"] / concluidos["quantidade"], 2)
            if concluidos["quantidade"] else 0.0,
            "pacotes_ativos": pacotes_ativos,
            "sessoes_restantes": int(sessoes_restantes),
        },
        por_status=por_status,
        por_forma_pagamento=por_forma,
        top_servicos=top_servicos,
        por_profissional=por_profissional,
        serie_diaria=serie,
    )

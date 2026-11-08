"""Agendamentos, agenda (calendário) e horários livres.

    GET   /api/agenda?inicio=AAAA-MM-DD&fim=AAAA-MM-DD&profissional_id=
          itens no período (visão diária/semanal do calendário)
    GET   /api/disponibilidade?profissional_id=&data=&servico_id=
          horários livres de um profissional para um serviço

    GET   /api/agendamentos?inicio=&fim=&cliente_id=&status=
    GET   /api/agendamentos/<id>                 completo (itens, pagamentos, notificações)
    POST  /api/agendamentos                      cria
    PUT   /api/agendamentos/<id>                 substitui os itens (reagendar)
    PATCH /api/agendamentos/<id>/status          {"status": "confirmado|concluido|falta|cancelado"}
    POST  /api/agendamentos/<id>/cancelar        atalho para status = cancelado
    POST  /api/agendamentos/<id>/notificar       {"tipo": "confirmacao|lembrete"} (reenvia)

Corpo do POST/PUT:
{
  "cliente_id": 1,                     (apenas no POST)
  "enviar_confirmacao": true,          (opcional, padrão true)
  "itens": [
    {"servico_id": 3, "profissional_id": 1, "data_hora_inicio": "2026-11-10T09:00"},
    {"servico_id": 4, "profissional_id": 2, "data_hora_inicio": "2026-11-10T09:00",
     "pacote_cliente_id": null, "subtotal": null}
  ]
}
"""
from datetime import datetime, time, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    STATUS_AGENDAMENTO,
    TIPOS_NOTIFICACAO,
    Agendamento,
    Cliente,
    ItemAgendamento,
    Profissional,
    Servico,
)
from ..services import agenda, whatsapp
from ..utils import agora, serializar
from .auth import exigir_login
from .validacao import ErroApi, buscar_ou_404, obter_json

bp = Blueprint("agendamentos", __name__, url_prefix="/api")
bp.before_request(exigir_login)

MAX_DIAS_PERIODO = 62


def _periodo():
    """Lê ?inicio= e ?fim= (datas). Padrão: hoje."""
    hoje = agora().date()
    inicio = agenda.ler_data(request.args.get("inicio"), hoje)
    fim = agenda.ler_data(request.args.get("fim"), inicio)
    if fim < inicio:
        raise ErroApi("A data final deve ser maior ou igual à inicial.")
    if (fim - inicio).days > MAX_DIAS_PERIODO:
        raise ErroApi(f"Período máximo de {MAX_DIAS_PERIODO} dias.")
    return datetime.combine(inicio, time.min), datetime.combine(fim + timedelta(days=1), time.min)


def _resposta_completa(agendamento: Agendamento, status=200, **extras):
    dados = agendamento.to_dict(completo=True)
    dados.update(extras)
    return jsonify(dados), status


# ---------------------------------------------------------------------
# Agenda (calendário) e disponibilidade
# ---------------------------------------------------------------------
@bp.get("/agenda")
def ver_agenda():
    inicio, fim = _periodo()
    consulta = (
        ItemAgendamento.query.join(Agendamento)
        .options(selectinload(ItemAgendamento.agendamento).selectinload(Agendamento.cliente),
                 selectinload(ItemAgendamento.servico),
                 selectinload(ItemAgendamento.profissional))
        .filter(ItemAgendamento.data_hora_inicio >= inicio, ItemAgendamento.data_hora_inicio < fim)
    )
    if request.args.get("incluir_cancelados", "").lower() not in ("true", "1"):
        consulta = consulta.filter(Agendamento.status_geral != "cancelado")
    if request.args.get("profissional_id"):
        consulta = consulta.filter(ItemAgendamento.profissional_id == agenda._id(request.args["profissional_id"]))

    itens = [{
        "id_item": i.id_item,
        "agendamento_id": i.agendamento_id,
        "status_geral": i.agendamento.status_geral,
        "cliente_id": i.agendamento.cliente_id,
        "cliente_nome": i.agendamento.cliente.nome,
        "servico_id": i.servico_id,
        "servico_nome": i.servico.nome,
        "profissional_id": i.profissional_id,
        "profissional_nome": i.profissional.nome,
        "data_hora_inicio": serializar(i.data_hora_inicio),
        "data_hora_fim": serializar(i.data_hora_fim),
        "subtotal": serializar(i.subtotal),
        "pacote_cliente_id": i.pacote_cliente_id,
    } for i in consulta.order_by(ItemAgendamento.data_hora_inicio).all()]

    abertura, fechamento, dias = agenda.horario_salao()
    profissionais = Profissional.query.filter_by(ativo=True).order_by(Profissional.nome).all()
    return jsonify(
        inicio=serializar(inicio.date()),
        fim=serializar((fim - timedelta(days=1)).date()),
        horario={"abertura": f"{abertura:%H:%M}", "fechamento": f"{fechamento:%H:%M}",
                 "dias_funcionamento": dias},
        profissionais=[p.to_dict() for p in profissionais],
        itens=itens,
    )


@bp.get("/disponibilidade")
def disponibilidade():
    profissional = buscar_ou_404(Profissional, agenda._id(request.args.get("profissional_id")) or 0, "Profissional")
    servico = buscar_ou_404(Servico, agenda._id(request.args.get("servico_id")) or 0, "Serviço")
    dia = agenda.ler_data(request.args.get("data"))
    ignorar = agenda._id(request.args.get("ignorar_agendamento_id"))
    return jsonify(
        profissional_id=profissional.id_profissional,
        servico_id=servico.id_servico,
        data=dia.isoformat(),
        duracao_minutos=servico.duracao_minutos,
        horarios=agenda.horarios_livres(profissional, dia, servico.duracao_minutos, ignorar),
    )


# ---------------------------------------------------------------------
# CRUD de agendamentos
# ---------------------------------------------------------------------
@bp.get("/agendamentos")
def listar():
    consulta = Agendamento.query.options(
        selectinload(Agendamento.cliente),
        selectinload(Agendamento.itens),
        selectinload(Agendamento.pagamentos),
    )
    if request.args.get("inicio") or request.args.get("fim"):
        inicio, fim = _periodo()
        consulta = consulta.filter(Agendamento.itens.any(
            (ItemAgendamento.data_hora_inicio >= inicio) & (ItemAgendamento.data_hora_inicio < fim)))
    if request.args.get("cliente_id"):
        consulta = consulta.filter(Agendamento.cliente_id == agenda._id(request.args["cliente_id"]))
    status = request.args.get("status")
    if status:
        if status not in STATUS_AGENDAMENTO:
            raise ErroApi(f"Status inválido. Use: {', '.join(STATUS_AGENDAMENTO)}.")
        consulta = consulta.filter(Agendamento.status_geral == status)

    agendamentos = consulta.all()
    agendamentos.sort(key=lambda a: a.inicio or datetime.max)
    return jsonify([a.to_dict() for a in agendamentos])


@bp.get("/agendamentos/<int:id_agendamento>")
def detalhar(id_agendamento):
    return _resposta_completa(buscar_ou_404(Agendamento, id_agendamento, "Agendamento"))


@bp.post("/agendamentos")
def criar():
    dados = obter_json()
    cliente = db.session.get(Cliente, agenda._id(dados.get("cliente_id")) or 0)
    if cliente is None:
        raise ErroApi("Cliente não encontrado.", 400, {"cliente_id": "Selecione um cliente válido."})

    agendamento = agenda.criar_agendamento(cliente, dados.get("itens"))
    if dados.get("enviar_confirmacao", True):
        whatsapp.enviar_confirmacao(agendamento)
    db.session.commit()
    return _resposta_completa(agendamento, 201)


@bp.put("/agendamentos/<int:id_agendamento>")
def atualizar(id_agendamento):
    agendamento = buscar_ou_404(Agendamento, id_agendamento, "Agendamento")
    dados = obter_json()
    if "cliente_id" in dados and agenda._id(dados["cliente_id"]) != agendamento.cliente_id:
        raise ErroApi("Não é possível trocar o cliente de um agendamento. Cancele e crie outro.", 400)

    horario_mudou = agenda.atualizar_agendamento(agendamento, dados.get("itens"))
    if horario_mudou and dados.get("enviar_confirmacao", True):
        db.session.flush()
        whatsapp.enviar_confirmacao(agendamento, reenviar=True)
        # O lembrete antigo tinha o horário anterior: será gerado de novo.
        for notificacao in list(agendamento.notificacoes):
            if notificacao.tipo == "lembrete":
                agendamento.notificacoes.remove(notificacao)
    db.session.commit()
    return _resposta_completa(agendamento, horario_alterado=horario_mudou)


@bp.patch("/agendamentos/<int:id_agendamento>/status")
def mudar_status(id_agendamento):
    agendamento = buscar_ou_404(Agendamento, id_agendamento, "Agendamento")
    novo = obter_json().get("status")
    if novo not in STATUS_AGENDAMENTO:
        raise ErroApi(f"Status inválido. Use: {', '.join(STATUS_AGENDAMENTO)}.", 400,
                      {"status": "Valor inválido."})
    agenda.alterar_status(agendamento, novo)
    db.session.commit()
    return _resposta_completa(agendamento)


@bp.post("/agendamentos/<int:id_agendamento>/cancelar")
def cancelar(id_agendamento):
    agendamento = buscar_ou_404(Agendamento, id_agendamento, "Agendamento")
    agenda.alterar_status(agendamento, "cancelado")
    db.session.commit()
    return _resposta_completa(agendamento)


@bp.post("/agendamentos/<int:id_agendamento>/notificar")
def notificar(id_agendamento):
    """Gera (ou regenera) manualmente a mensagem de WhatsApp."""
    agendamento = buscar_ou_404(Agendamento, id_agendamento, "Agendamento")
    if agendamento.status_geral not in ("agendado", "confirmado"):
        raise ErroApi("Só é possível notificar agendamentos ativos.", 409)
    tipo = (request.get_json(silent=True) or {}).get("tipo", "confirmacao")
    if tipo not in TIPOS_NOTIFICACAO:
        raise ErroApi("Tipo inválido. Use 'confirmacao' ou 'lembrete'.")
    if tipo == "confirmacao":
        notificacao = whatsapp.enviar_confirmacao(agendamento, reenviar=True)
    else:
        notificacao = whatsapp.enviar_lembrete(agendamento, reenviar=True)
    db.session.commit()
    return jsonify(notificacao.to_dict())

"""Notificações de WhatsApp e rotina automática de lembretes.

    POST /api/tarefas/lembretes
         Rotina chamada por um cron externo (ex.: cron-job.org a cada 15 min).
         Autenticação: cabeçalho "X-Cron-Token: <CRON_TOKEN>" (ou ?token=),
         ou um usuário logado (botão "enviar lembretes agora" no painel).

    GET  /api/notificacoes?status=&tipo=&agendamento_id=
    POST /api/notificacoes/<id>/resposta   {"resposta": "confirmou" | "cancelou"}
         Simula a resposta do cliente no WhatsApp (SIM/NÃO).
"""
import hmac

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import RESPOSTAS_CLIENTE, Agendamento, Notificacao
from ..services import whatsapp
from ..services.agenda import _id
from ..utils import agora, serializar
from .auth import carregar_usuario_logado, exigir_login
from .validacao import ErroApi, buscar_ou_404, obter_json

bp_tarefas = Blueprint("tarefas", __name__, url_prefix="/api/tarefas")
bp = Blueprint("notificacoes", __name__, url_prefix="/api/notificacoes")
bp.before_request(exigir_login)


def _token_valido() -> bool:
    esperado = current_app.config.get("CRON_TOKEN") or ""
    recebido = request.headers.get("X-Cron-Token") or request.args.get("token") or ""
    # compare_digest: comparação em tempo constante (evita ataque de tempo)
    return bool(esperado) and hmac.compare_digest(esperado, recebido)


def _descrever(notificacao: Notificacao) -> dict:
    dados = notificacao.to_dict()
    agendamento = notificacao.agendamento
    dados["cliente_nome"] = agendamento.cliente.nome
    dados["agendamento_inicio"] = serializar(agendamento.inicio)
    dados["status_geral"] = agendamento.status_geral
    return dados


@bp_tarefas.post("/lembretes")
def rotina_lembretes():
    if not _token_valido() and carregar_usuario_logado() is None:
        raise ErroApi("Token do cron inválido ou ausente.", 401)
    gerados = whatsapp.processar_lembretes()
    db.session.commit()
    return jsonify(
        executado_em=serializar(agora()),
        janela_horas=current_app.config["LEMBRETE_HORAS_ANTES"],
        quantidade=len(gerados),
        notificacoes=[_descrever(n) for n in gerados],
    )


@bp.get("")
def listar():
    consulta = Notificacao.query.options(
        selectinload(Notificacao.agendamento).selectinload(Agendamento.cliente),
        selectinload(Notificacao.agendamento).selectinload(Agendamento.itens),
    )
    for campo in ("status_envio", "tipo"):
        valor = request.args.get(campo) or request.args.get(campo.split("_")[0])
        if valor:
            consulta = consulta.filter(getattr(Notificacao, campo) == valor)
    if request.args.get("agendamento_id"):
        consulta = consulta.filter(Notificacao.agendamento_id == _id(request.args["agendamento_id"]))
    notificacoes = consulta.order_by(Notificacao.data_envio.desc()).limit(200).all()
    return jsonify([_descrever(n) for n in notificacoes])


@bp.post("/<int:id_notificacao>/resposta")
def responder(id_notificacao):
    notificacao = buscar_ou_404(Notificacao, id_notificacao, "Notificação")
    resposta = obter_json().get("resposta")
    if resposta not in RESPOSTAS_CLIENTE:
        raise ErroApi("Resposta inválida. Use 'confirmou' ou 'cancelou'.", 400)
    whatsapp.registrar_resposta(notificacao, resposta)
    db.session.commit()
    return jsonify(_descrever(notificacao))

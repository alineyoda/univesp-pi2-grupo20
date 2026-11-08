"""Notificações por WhatsApp (modo simulado).

Fluxo:
1. Ao criar um agendamento, é gerada uma mensagem de CONFIRMAÇÃO.
2. Uma rotina periódica (cron externo -> POST /api/tarefas/lembretes)
   gera LEMBRETES para os agendamentos das próximas N horas (padrão 24h).
3. Cada mensagem é gravada na tabela `notificacao` com o link
   https://wa.me/<telefone>?text=<mensagem>. Clicando no link, o WhatsApp
   abre com a conversa e o texto prontos.

Há no máximo 1 confirmação e 1 lembrete por agendamento (UNIQUE no banco),
evitando mensagens duplicadas.

Para usar uma API real no futuro (Meta Cloud API, Twilio...), basta criar
outro "provedor" com o método enviar() e selecioná-lo em WHATSAPP_MODO.
"""
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import Agendamento, ItemAgendamento, Notificacao
from ..utils import agora

DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo")


# ---------------------------------------------------------------------
# Provedores de envio
# ---------------------------------------------------------------------
class ProvedorSimulado:
    """Não envia nada: apenas marca a mensagem como 'simulado'.
    O link wa.me gerado permite abrir a conversa manualmente."""

    status_sucesso = "simulado"

    def enviar(self, telefone: str, mensagem: str) -> None:
        current_app.logger.info("[WhatsApp simulado] Para %s: %s", telefone, mensagem)


PROVEDORES = {"simulado": ProvedorSimulado}


def obter_provedor():
    modo = current_app.config.get("WHATSAPP_MODO", "simulado")
    if modo not in PROVEDORES:
        current_app.logger.warning("WHATSAPP_MODO '%s' não implementado; usando simulado.", modo)
        modo = "simulado"
    return PROVEDORES[modo]()


# ---------------------------------------------------------------------
# Formatação das mensagens
# ---------------------------------------------------------------------
def gerar_link_wa(telefone: str, mensagem: str) -> str:
    return f"https://wa.me/{telefone}?text={quote(mensagem)}"


def formatar_moeda(valor: Decimal) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _lista_servicos(agendamento: Agendamento) -> str:
    itens = sorted(agendamento.itens, key=lambda i: i.data_hora_inicio)
    return "\n".join(
        f"• {i.data_hora_inicio:%H:%M} - {i.servico.nome} com {i.profissional.nome}" for i in itens
    )


def _quando(agendamento: Agendamento, referencia=None) -> str:
    inicio = agendamento.inicio
    referencia = referencia or agora()
    dias = (inicio.date() - referencia.date()).days
    relativo = {0: "hoje", 1: "amanhã"}.get(dias, DIAS_SEMANA[inicio.weekday()])
    return f"{relativo}, {inicio:%d/%m}, às {inicio:%H:%M}"


def mensagem_confirmacao(agendamento: Agendamento) -> str:
    salao = current_app.config["SALAO_NOME"]
    primeiro_nome = agendamento.cliente.nome.split()[0]
    return (
        f"Olá, {primeiro_nome}! Seu horário no {salao} está agendado para "
        f"{_quando(agendamento)}:\n{_lista_servicos(agendamento)}\n"
        f"Valor total: {formatar_moeda(agendamento.valor_total)}.\n"
        f"Responda SIM para confirmar ou NÃO para cancelar."
    )


def mensagem_lembrete(agendamento: Agendamento, referencia=None) -> str:
    salao = current_app.config["SALAO_NOME"]
    primeiro_nome = agendamento.cliente.nome.split()[0]
    return (
        f"Olá, {primeiro_nome}! Lembrete: você tem horário no {salao} "
        f"{_quando(agendamento, referencia)}:\n{_lista_servicos(agendamento)}\n"
        f"Responda SIM para confirmar sua presença ou NÃO para cancelar. Até lá!"
    )


# ---------------------------------------------------------------------
# Registro / envio
# ---------------------------------------------------------------------
def registrar_notificacao(agendamento: Agendamento, tipo: str, mensagem: str,
                          reenviar: bool = False) -> Notificacao:
    """Grava (ou atualiza, se reenviar=True) a notificação e "envia"."""
    existente = next((n for n in agendamento.notificacoes if n.tipo == tipo), None)
    if existente and not reenviar:
        return existente

    telefone = agendamento.cliente.telefone
    provedor = obter_provedor()
    try:
        provedor.enviar(telefone, mensagem)
        status = provedor.status_sucesso
    except Exception:  # noqa: BLE001 - falha de envio não pode quebrar o agendamento
        current_app.logger.exception("Falha ao enviar WhatsApp")
        status = "falha"

    dados = dict(telefone_destino=telefone, mensagem=mensagem,
                 link_wa=gerar_link_wa(telefone, mensagem), status_envio=status,
                 data_envio=agora(), resposta_cliente=None, data_resposta=None)
    if existente:
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        return existente

    notificacao = Notificacao(tipo=tipo, canal="whatsapp", **dados)
    agendamento.notificacoes.append(notificacao)
    return notificacao


def enviar_confirmacao(agendamento: Agendamento, reenviar: bool = False) -> Notificacao:
    return registrar_notificacao(agendamento, "confirmacao", mensagem_confirmacao(agendamento), reenviar)


def enviar_lembrete(agendamento: Agendamento, referencia=None, reenviar: bool = False) -> Notificacao:
    return registrar_notificacao(agendamento, "lembrete",
                                 mensagem_lembrete(agendamento, referencia), reenviar)


def processar_lembretes(referencia=None) -> list[Notificacao]:
    """Gera lembretes para agendamentos que começam nas próximas N horas.

    Critérios: status 'agendado' ou 'confirmado', primeiro serviço entre
    agora e agora + LEMBRETE_HORAS_ANTES, e nenhum lembrete gerado ainda.
    """
    referencia = referencia or agora()
    limite = referencia + timedelta(hours=current_app.config["LEMBRETE_HORAS_ANTES"])

    primeiro_item = (
        db.session.query(ItemAgendamento.agendamento_id.label("agendamento_id"),
                         func.min(ItemAgendamento.data_hora_inicio).label("inicio"))
        .group_by(ItemAgendamento.agendamento_id)
        .subquery()
    )
    agendamentos = (
        Agendamento.query
        .join(primeiro_item, Agendamento.id_agendamento == primeiro_item.c.agendamento_id)
        .filter(
            primeiro_item.c.inicio > referencia,
            primeiro_item.c.inicio <= limite,
            Agendamento.status_geral.in_(("agendado", "confirmado")),
            ~Agendamento.notificacoes.any(Notificacao.tipo == "lembrete"),
        )
        .order_by(primeiro_item.c.inicio)
        .all()
    )
    return [enviar_lembrete(ag, referencia) for ag in agendamentos]


def registrar_resposta(notificacao: Notificacao, resposta: str) -> None:
    """Simula a resposta do cliente: SIM confirma, NÃO cancela o agendamento."""
    from .agenda import alterar_status  # import local evita ciclo

    notificacao.resposta_cliente = resposta
    notificacao.data_resposta = agora()
    agendamento = notificacao.agendamento
    novo_status = "confirmado" if resposta == "confirmou" else "cancelado"
    alterar_status(agendamento, novo_status)

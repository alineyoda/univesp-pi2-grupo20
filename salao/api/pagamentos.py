"""Pagamentos de agendamentos e de compras de pacotes.

    GET    /api/pagamentos?inicio=&fim=&forma_pagamento=&agendamento_id=&pacote_cliente_id=
    POST   /api/pagamentos
           {"agendamento_id": 5, "forma_pagamento": "pix", "valor_pago": 120.00}
           ou {"pacote_cliente_id": 2, "forma_pagamento": "dinheiro", "valor_pago": 300}
    DELETE /api/pagamentos/<id>     estorno (somente admin)

Regras: cada pagamento referencia um agendamento OU um pacote; o valor
não pode ultrapassar o saldo devedor; itens cancelados não recebem
pagamento. Pagamentos parciais (sinal + restante) são permitidos.
"""
from datetime import datetime, time, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import FORMAS_PAGAMENTO, Agendamento, PacoteCliente, Pagamento
from ..services.agenda import _id, ler_data
from ..services.whatsapp import formatar_moeda
from ..utils import agora
from .auth import exigir_login, somente_admin
from .validacao import ErroApi, Validador, buscar_ou_404, obter_json

bp = Blueprint("pagamentos", __name__, url_prefix="/api/pagamentos")
bp.before_request(exigir_login)


def _descrever(pagamento: Pagamento) -> dict:
    dados = pagamento.to_dict()
    if pagamento.agendamento is not None:
        dados["referencia"] = f"Agendamento #{pagamento.agendamento_id}"
        dados["cliente_nome"] = pagamento.agendamento.cliente.nome
    else:
        dados["referencia"] = f"Pacote: {pagamento.pacote.descricao}"
        dados["cliente_nome"] = pagamento.pacote.cliente.nome
    return dados


@bp.get("")
def listar():
    consulta = Pagamento.query.options(
        selectinload(Pagamento.agendamento).selectinload(Agendamento.cliente),
        selectinload(Pagamento.pacote).selectinload(PacoteCliente.cliente),
    )
    if request.args.get("inicio") or request.args.get("fim"):
        hoje = agora().date()
        inicio = ler_data(request.args.get("inicio"), hoje)
        fim = ler_data(request.args.get("fim"), inicio)
        consulta = consulta.filter(
            Pagamento.data_pagamento >= datetime.combine(inicio, time.min),
            Pagamento.data_pagamento < datetime.combine(fim + timedelta(days=1), time.min),
        )
    if request.args.get("forma_pagamento"):
        consulta = consulta.filter(Pagamento.forma_pagamento == request.args["forma_pagamento"])
    if request.args.get("agendamento_id"):
        consulta = consulta.filter(Pagamento.agendamento_id == _id(request.args["agendamento_id"]))
    if request.args.get("pacote_cliente_id"):
        consulta = consulta.filter(Pagamento.pacote_cliente_id == _id(request.args["pacote_cliente_id"]))
    pagamentos = consulta.order_by(Pagamento.data_pagamento.desc()).limit(500).all()
    return jsonify([_descrever(p) for p in pagamentos])


@bp.post("")
def registrar():
    dados = obter_json()
    limpos = Validador(dados).dinheiro("valor_pago", minimo=0).resultado()
    valor = limpos["valor_pago"]
    if valor <= 0:
        raise ErroApi("Informe um valor maior que zero.", 400, {"valor_pago": "Deve ser maior que zero."})
    forma = dados.get("forma_pagamento")
    if forma not in FORMAS_PAGAMENTO:
        raise ErroApi("Forma de pagamento inválida.", 400,
                      {"forma_pagamento": f"Use: {', '.join(FORMAS_PAGAMENTO)}."})

    id_agendamento = _id(dados.get("agendamento_id"))
    id_pacote = _id(dados.get("pacote_cliente_id"))
    if bool(id_agendamento) == bool(id_pacote):
        raise ErroApi("Informe agendamento_id OU pacote_cliente_id (apenas um).")

    if id_agendamento:
        alvo = buscar_ou_404(Agendamento, id_agendamento, "Agendamento")
        if alvo.status_geral == "cancelado":
            raise ErroApi("Agendamento cancelado não recebe pagamentos.", 409)
    else:
        alvo = buscar_ou_404(PacoteCliente, id_pacote, "Pacote")
        if alvo.status_pacote == "cancelado":
            raise ErroApi("Pacote cancelado não recebe pagamentos.", 409)

    if alvo.saldo_devedor <= 0:
        raise ErroApi("Não há saldo a pagar.", 409)
    if valor > alvo.saldo_devedor:
        raise ErroApi(f"Valor maior que o saldo devedor ({formatar_moeda(alvo.saldo_devedor)}).", 409,
                      {"valor_pago": "Valor acima do saldo."})

    pagamento = Pagamento(forma_pagamento=forma, valor_pago=valor, data_pagamento=agora(),
                          agendamento_id=id_agendamento, pacote_cliente_id=id_pacote)
    alvo.pagamentos.append(pagamento)
    db.session.commit()
    resposta = _descrever(pagamento)
    resposta["saldo_devedor_restante"] = float(alvo.saldo_devedor)
    return jsonify(resposta), 201


@bp.delete("/<int:id_pagamento>")
@somente_admin
def estornar(id_pagamento):
    pagamento = buscar_ou_404(Pagamento, id_pagamento, "Pagamento")
    db.session.delete(pagamento)
    db.session.commit()
    return "", 204

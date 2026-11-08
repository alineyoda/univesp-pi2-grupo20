"""Pacotes de serviços dos clientes (combos de várias sessões).

    GET    /api/pacotes?cliente_id=&servico_id=&status=&disponiveis=true
    GET    /api/pacotes/<id>          detalhe com sessões usadas e pagamentos
    POST   /api/pacotes               vende um pacote (pagamento opcional)
    PATCH  /api/pacotes/<id>          descrição, qtd. de sessões ou status 'cancelado'
    DELETE /api/pacotes/<id>          admin; apenas se nunca foi usado nem pago

Corpo do POST:
{
  "cliente_id": 2, "servico_id": 6, "qtd_sessoes_total": 5, "valor_pacote": 600,
  "descricao": "Pacote 5 limpezas de pele",          (opcional)
  "pagamento": {"forma_pagamento": "pix", "valor_pago": 300}   (opcional)
}

Consumo de sessões: acontece automaticamente quando um item de
agendamento usa o pacote (pacote_cliente_id) e é devolvido se o
agendamento for cancelado ou remarcado sem o pacote.
"""
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import FORMAS_PAGAMENTO, Cliente, PacoteCliente, Pagamento, Servico
from ..services.agenda import _id
from ..utils import agora, serializar
from .auth import exigir_login, somente_admin
from .validacao import ErroApi, Validador, buscar_ou_404, obter_json

bp = Blueprint("pacotes", __name__, url_prefix="/api/pacotes")
bp.before_request(exigir_login)


def _detalhe(pacote: PacoteCliente) -> dict:
    dados = pacote.to_dict()
    dados["sessoes"] = [{
        "id_item": i.id_item,
        "agendamento_id": i.agendamento_id,
        "data_hora_inicio": serializar(i.data_hora_inicio),
        "profissional_nome": i.profissional.nome,
        "status_geral": i.agendamento.status_geral,
    } for i in sorted(pacote.itens, key=lambda i: i.data_hora_inicio)]
    dados["pagamentos"] = [p.to_dict() for p in pacote.pagamentos]
    return dados


@bp.get("")
def listar():
    consulta = PacoteCliente.query
    if request.args.get("cliente_id"):
        consulta = consulta.filter(PacoteCliente.cliente_id == _id(request.args["cliente_id"]))
    if request.args.get("servico_id"):
        consulta = consulta.filter(PacoteCliente.servico_id == _id(request.args["servico_id"]))
    if request.args.get("status"):
        consulta = consulta.filter(PacoteCliente.status_pacote == request.args["status"])
    pacotes = consulta.order_by(PacoteCliente.data_compra.desc()).all()
    if request.args.get("disponiveis", "").lower() in ("true", "1"):
        pacotes = [p for p in pacotes if p.disponivel]
    return jsonify([p.to_dict() for p in pacotes])


@bp.get("/<int:id_pacote>")
def detalhar(id_pacote):
    return jsonify(_detalhe(buscar_ou_404(PacoteCliente, id_pacote, "Pacote")))


@bp.post("")
def vender():
    dados = obter_json()
    limpos = (
        Validador(dados)
        .inteiro("qtd_sessoes_total", minimo=1, maximo=100)
        .dinheiro("valor_pacote")
        .texto("descricao", obrigatorio=False, minimo=3, maximo=160)
        .resultado()
    )
    cliente = db.session.get(Cliente, _id(dados.get("cliente_id")) or 0)
    servico = db.session.get(Servico, _id(dados.get("servico_id")) or 0)
    erros = {}
    if cliente is None:
        erros["cliente_id"] = "Cliente não encontrado."
    if servico is None:
        erros["servico_id"] = "Serviço não encontrado."
    if erros:
        raise ErroApi("Verifique os campos informados.", 400, erros)

    pacote = PacoteCliente(
        cliente_id=cliente.id_cliente,
        servico_id=servico.id_servico,
        descricao=limpos.get("descricao") or f"Pacote {limpos['qtd_sessoes_total']}x {servico.nome}",
        qtd_sessoes_total=limpos["qtd_sessoes_total"],
        sessoes_realizadas=0,
        status_pacote="ativo",
        valor_pacote=limpos["valor_pacote"],
        data_compra=agora(),
    )
    db.session.add(pacote)

    # Pagamento opcional no ato da compra (à vista ou entrada)
    pagamento = dados.get("pagamento")
    if pagamento:
        valor = Validador(pagamento).dinheiro("valor_pago").resultado()["valor_pago"]
        if pagamento.get("forma_pagamento") not in FORMAS_PAGAMENTO:
            raise ErroApi("Forma de pagamento inválida.", 400, {"pagamento.forma_pagamento": "Inválida."})
        if not 0 < valor <= pacote.valor_pacote:
            raise ErroApi("O pagamento deve ser maior que zero e até o valor do pacote.", 400)
        pacote.pagamentos.append(Pagamento(forma_pagamento=pagamento["forma_pagamento"],
                                           valor_pago=valor, data_pagamento=agora()))
    db.session.commit()
    return jsonify(_detalhe(pacote)), 201


@bp.patch("/<int:id_pacote>")
def atualizar(id_pacote):
    pacote = buscar_ou_404(PacoteCliente, id_pacote, "Pacote")
    dados = obter_json()
    limpos = (
        Validador(dados, parcial=True)
        .texto("descricao", minimo=3, maximo=160)
        .inteiro("qtd_sessoes_total", minimo=1, maximo=100)
        .resultado()
    )
    if "qtd_sessoes_total" in limpos:
        if limpos["qtd_sessoes_total"] < pacote.sessoes_realizadas:
            raise ErroApi("A quantidade total não pode ser menor que as sessões já realizadas.", 409)
        pacote.qtd_sessoes_total = limpos["qtd_sessoes_total"]
        if pacote.status_pacote != "cancelado":
            pacote.status_pacote = "ativo" if pacote.sessoes_restantes > 0 else "concluido"
    if "descricao" in limpos:
        pacote.descricao = limpos["descricao"]

    status = dados.get("status_pacote")
    if status and status != pacote.status_pacote:
        if status != "cancelado":
            raise ErroApi("Pelo status só é possível cancelar o pacote "
                          "(ativo/concluído são calculados pelas sessões).", 400)
        pacote.status_pacote = "cancelado"
    db.session.commit()
    return jsonify(_detalhe(pacote))


@bp.delete("/<int:id_pacote>")
@somente_admin
def excluir(id_pacote):
    pacote = buscar_ou_404(PacoteCliente, id_pacote, "Pacote")
    if pacote.itens or pacote.pagamentos:
        raise ErroApi("Pacote com sessões ou pagamentos não pode ser excluído; cancele-o.", 409)
    db.session.delete(pacote)
    db.session.commit()
    return "", 204

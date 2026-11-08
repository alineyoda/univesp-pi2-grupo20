"""CRUD de Serviços.

    GET    /api/servicos?categoria=Cabelo&busca=texto
    GET    /api/servicos/categorias    lista de categorias existentes
    GET    /api/servicos/<id>
    POST   /api/servicos
    PUT    /api/servicos/<id>          (PATCH para atualização parcial)
    DELETE /api/servicos/<id>          bloqueado se usado em agendamento/pacote
"""
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import ItemAgendamento, PacoteCliente, Servico
from .auth import exigir_login, somente_admin
from .validacao import ErroApi, Validador, buscar_ou_404, obter_json

bp = Blueprint("servicos", __name__, url_prefix="/api/servicos")
bp.before_request(exigir_login)


def _validar(dados: dict, parcial: bool) -> dict:
    return (
        Validador(dados, parcial)
        .texto("nome", minimo=2, maximo=120)
        .texto("categoria", minimo=2, maximo=60)
        .inteiro("duracao_minutos", minimo=5, maximo=600)
        .dinheiro("preco_base")
        .resultado()
    )


def _garantir_nome_unico(nome: str | None, id_atual: int | None = None) -> None:
    if not nome:
        return
    consulta = Servico.query.filter(Servico.nome == nome)
    if id_atual:
        consulta = consulta.filter(Servico.id_servico != id_atual)
    if consulta.first():
        raise ErroApi("Já existe um serviço com este nome.", 409, {"nome": "Nome já cadastrado."})


@bp.get("")
def listar():
    consulta = Servico.query
    categoria = request.args.get("categoria", "").strip()
    if categoria:
        consulta = consulta.filter(Servico.categoria == categoria)
    busca = request.args.get("busca", "").strip()
    if busca:
        consulta = consulta.filter(Servico.nome.ilike(f"%{busca}%"))
    servicos = consulta.order_by(Servico.categoria, Servico.nome).all()
    return jsonify([s.to_dict() for s in servicos])


@bp.get("/categorias")
def categorias():
    linhas = db.session.query(Servico.categoria).distinct().order_by(Servico.categoria).all()
    return jsonify([linha[0] for linha in linhas])


@bp.get("/<int:id_servico>")
def detalhar(id_servico):
    return jsonify(buscar_ou_404(Servico, id_servico, "Serviço").to_dict())


@bp.post("")
def criar():
    dados = _validar(obter_json(), parcial=False)
    _garantir_nome_unico(dados.get("nome"))
    servico = Servico(**dados)
    db.session.add(servico)
    db.session.commit()
    return jsonify(servico.to_dict()), 201


@bp.route("/<int:id_servico>", methods=["PUT", "PATCH"])
def atualizar(id_servico):
    servico = buscar_ou_404(Servico, id_servico, "Serviço")
    dados = _validar(obter_json(), parcial=request.method == "PATCH")
    _garantir_nome_unico(dados.get("nome"), id_servico)
    for campo, valor in dados.items():
        setattr(servico, campo, valor)
    db.session.commit()
    return jsonify(servico.to_dict())


@bp.delete("/<int:id_servico>")
@somente_admin
def excluir(id_servico):
    servico = buscar_ou_404(Servico, id_servico, "Serviço")
    qtd_itens = ItemAgendamento.query.filter_by(servico_id=id_servico).count()
    qtd_pacotes = PacoteCliente.query.filter_by(servico_id=id_servico).count()
    if qtd_itens or qtd_pacotes:
        raise ErroApi(
            f"Serviço não pode ser excluído: está vinculado a {qtd_itens} atendimento(s) "
            f"e {qtd_pacotes} pacote(s).",
            409,
        )
    db.session.delete(servico)
    db.session.commit()
    return "", 204

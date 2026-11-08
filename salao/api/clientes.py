"""CRUD de Clientes.

    GET    /api/clientes?busca=texto   lista (busca por nome, telefone ou CPF)
    GET    /api/clientes/<id>          detalhe (com pacotes e nº de agendamentos)
    POST   /api/clientes               cria
    PUT    /api/clientes/<id>          atualiza (todos os campos obrigatórios)
    PATCH  /api/clientes/<id>          atualiza apenas os campos enviados
    DELETE /api/clientes/<id>          exclui (bloqueado se houver histórico)
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import Cliente
from .auth import exigir_login, somente_admin
from .validacao import ErroApi, Validador, buscar_ou_404, obter_json, somente_digitos

bp = Blueprint("clientes", __name__, url_prefix="/api/clientes")
bp.before_request(exigir_login)


def _validar(dados: dict, parcial: bool) -> dict:
    return (
        Validador(dados, parcial)
        .texto("nome", minimo=2, maximo=120)
        .telefone("telefone")
        .cpf("cpf", obrigatorio=False)
        .resultado()
    )


def _garantir_cpf_unico(cpf: str | None, id_atual: int | None = None) -> None:
    if not cpf:
        return
    consulta = Cliente.query.filter(Cliente.cpf == cpf)
    if id_atual:
        consulta = consulta.filter(Cliente.id_cliente != id_atual)
    if consulta.first():
        raise ErroApi("Já existe um cliente com este CPF.", 409, {"cpf": "CPF já cadastrado."})


def _detalhe(cliente: Cliente) -> dict:
    dados = cliente.to_dict()
    dados["total_agendamentos"] = cliente.agendamentos.count()
    dados["pacotes"] = [p.to_dict() for p in cliente.pacotes]
    return dados


@bp.get("")
def listar():
    consulta = Cliente.query
    busca = request.args.get("busca", "").strip()
    if busca:
        filtros = [Cliente.nome.ilike(f"%{busca}%")]
        digitos = somente_digitos(busca)
        if digitos:
            filtros += [Cliente.telefone.contains(digitos), Cliente.cpf.contains(digitos)]
        consulta = consulta.filter(or_(*filtros))
    return jsonify([c.to_dict() for c in consulta.order_by(Cliente.nome).all()])


@bp.get("/<int:id_cliente>")
def detalhar(id_cliente):
    return jsonify(_detalhe(buscar_ou_404(Cliente, id_cliente, "Cliente")))


@bp.post("")
def criar():
    dados = _validar(obter_json(), parcial=False)
    _garantir_cpf_unico(dados.get("cpf"))
    cliente = Cliente(**dados)
    db.session.add(cliente)
    db.session.commit()
    return jsonify(cliente.to_dict()), 201


@bp.route("/<int:id_cliente>", methods=["PUT", "PATCH"])
def atualizar(id_cliente):
    cliente = buscar_ou_404(Cliente, id_cliente, "Cliente")
    dados = _validar(obter_json(), parcial=request.method == "PATCH")
    _garantir_cpf_unico(dados.get("cpf"), id_cliente)
    for campo, valor in dados.items():
        setattr(cliente, campo, valor)
    db.session.commit()
    return jsonify(cliente.to_dict())


@bp.delete("/<int:id_cliente>")
@somente_admin
def excluir(id_cliente):
    cliente = buscar_ou_404(Cliente, id_cliente, "Cliente")
    qtd_agendamentos = cliente.agendamentos.count()
    qtd_pacotes = cliente.pacotes.count()
    if qtd_agendamentos or qtd_pacotes:
        raise ErroApi(
            f"Cliente não pode ser excluído: possui {qtd_agendamentos} agendamento(s) "
            f"e {qtd_pacotes} pacote(s) no histórico.",
            409,
        )
    db.session.delete(cliente)
    db.session.commit()
    return "", 204

"""CRUD de Profissionais (com exclusão lógica).

    GET    /api/profissionais?ativo=true|false&busca=texto
    GET    /api/profissionais/<id>
    POST   /api/profissionais
    PUT    /api/profissionais/<id>     (PATCH para atualização parcial)
    DELETE /api/profissionais/<id>     desativa (ativo = false), não apaga

Para reativar um profissional: PATCH /api/profissionais/<id> {"ativo": true}
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import Profissional
from .auth import exigir_login, somente_admin
from .validacao import ErroApi, Validador, buscar_ou_404, obter_json

bp = Blueprint("profissionais", __name__, url_prefix="/api/profissionais")
bp.before_request(exigir_login)


def _validar(dados: dict, parcial: bool) -> dict:
    return (
        Validador(dados, parcial)
        .texto("nome", minimo=2, maximo=120)
        .texto("especialidade", minimo=2, maximo=80)
        .telefone("telefone", obrigatorio=False)
        .booleano("ativo")
        .resultado()
    )


@bp.get("")
def listar():
    consulta = Profissional.query
    ativo = request.args.get("ativo", "").lower()
    if ativo in ("true", "1"):
        consulta = consulta.filter(Profissional.ativo.is_(True))
    elif ativo in ("false", "0"):
        consulta = consulta.filter(Profissional.ativo.is_(False))
    busca = request.args.get("busca", "").strip()
    if busca:
        consulta = consulta.filter(
            or_(Profissional.nome.ilike(f"%{busca}%"), Profissional.especialidade.ilike(f"%{busca}%"))
        )
    profissionais = consulta.order_by(Profissional.ativo.desc(), Profissional.nome).all()
    return jsonify([p.to_dict() for p in profissionais])


@bp.get("/<int:id_profissional>")
def detalhar(id_profissional):
    return jsonify(buscar_ou_404(Profissional, id_profissional, "Profissional").to_dict())


@bp.post("")
def criar():
    dados = _validar(obter_json(), parcial=False)
    dados.setdefault("ativo", True)
    profissional = Profissional(**dados)
    db.session.add(profissional)
    db.session.commit()
    return jsonify(profissional.to_dict()), 201


@bp.route("/<int:id_profissional>", methods=["PUT", "PATCH"])
def atualizar(id_profissional):
    profissional = buscar_ou_404(Profissional, id_profissional, "Profissional")
    dados = _validar(obter_json(), parcial=request.method == "PATCH")
    for campo, valor in dados.items():
        setattr(profissional, campo, valor)
    db.session.commit()
    return jsonify(profissional.to_dict())


@bp.delete("/<int:id_profissional>")
@somente_admin
def desativar(id_profissional):
    """Exclusão lógica: o histórico de atendimentos é preservado."""
    profissional = buscar_ou_404(Profissional, id_profissional, "Profissional")
    if not profissional.ativo:
        raise ErroApi("Profissional já está desativado(a).", 409)
    profissional.ativo = False
    db.session.commit()
    return jsonify(mensagem="Profissional desativado(a).", profissional=profissional.to_dict())

"""Validação de dados recebidos pela API e erros padronizados.

Todas as respostas de erro seguem o formato:
    {"erro": "mensagem geral", "campos": {"nome_do_campo": "problema"}}
"""
import re
from decimal import Decimal, InvalidOperation

from flask import request

from ..extensions import db


class ErroApi(Exception):
    """Erro de regra de negócio, convertido em resposta JSON."""

    status = 400

    def __init__(self, mensagem: str, status: int | None = None, campos: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campos = campos or {}
        if status:
            self.status = status

    def to_dict(self) -> dict:
        dados = {"erro": self.mensagem}
        if self.campos:
            dados["campos"] = self.campos
        return dados


def obter_json() -> dict:
    """Lê o corpo da requisição. Exige JSON (também dificulta ataques CSRF,
    pois formulários de outros sites não conseguem enviar JSON)."""
    if not request.is_json:
        raise ErroApi("Envie os dados no formato JSON (Content-Type: application/json).", 415)
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ErroApi("JSON inválido.")
    return dados


def buscar_ou_404(modelo, id_registro: int, nome: str):
    """Busca um registro pela chave primária ou responde 404."""
    registro = db.session.get(modelo, id_registro)
    if registro is None:
        raise ErroApi(f"{nome} não encontrado(a).", 404)
    return registro


# ---------------------------------------------------------------------
# Regras específicas
# ---------------------------------------------------------------------
def somente_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor))


def cpf_valido(cpf: str) -> bool:
    """Confere os dígitos verificadores do CPF."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[posicao]):
            return False
    return True


def normalizar_telefone(valor) -> str | None:
    """Converte para o formato do WhatsApp (E.164 sem '+').

    '(11) 98765-4321' -> '5511987654321'. Números com DDD (10 ou 11
    dígitos) recebem o código do Brasil (55) automaticamente.
    """
    digitos = somente_digitos(valor)
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos if 12 <= len(digitos) <= 15 else None


# ---------------------------------------------------------------------
# Validador de campos
# ---------------------------------------------------------------------
class Validador:
    """Valida campo a campo e acumula os erros.

    Em modo parcial (PATCH), campos ausentes são ignorados; em modo
    completo (POST/PUT), campos obrigatórios ausentes geram erro.
    """

    def __init__(self, dados: dict, parcial: bool = False):
        self.dados = dados
        self.parcial = parcial
        self.erros: dict[str, str] = {}
        self.saida: dict = {}

    def _valor(self, campo: str, obrigatorio: bool):
        """Retorna (deve_processar, valor)."""
        if campo not in self.dados:
            if self.parcial:
                return False, None
            if obrigatorio:
                self.erros[campo] = "Campo obrigatório."
                return False, None
            return False, None
        valor = self.dados[campo]
        if isinstance(valor, str):
            valor = valor.strip()
        if valor in (None, ""):
            if obrigatorio:
                self.erros[campo] = "Campo obrigatório."
            else:
                self.saida[campo] = None
            return False, None
        return True, valor

    def texto(self, campo, obrigatorio=True, minimo=1, maximo=120):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            valor = " ".join(str(valor).split())  # remove espaços duplicados
            if not minimo <= len(valor) <= maximo:
                self.erros[campo] = f"Deve ter entre {minimo} e {maximo} caracteres."
            else:
                self.saida[campo] = valor
        return self

    def telefone(self, campo, obrigatorio=True):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            numero = normalizar_telefone(valor)
            if numero is None:
                self.erros[campo] = "Telefone inválido. Informe DDD + número, ex.: (11) 98765-4321."
            else:
                self.saida[campo] = numero
        return self

    def cpf(self, campo, obrigatorio=False):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            cpf = somente_digitos(valor)
            if not cpf_valido(cpf):
                self.erros[campo] = "CPF inválido."
            else:
                self.saida[campo] = cpf
        return self

    def inteiro(self, campo, obrigatorio=True, minimo=None, maximo=None):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            try:
                if isinstance(valor, bool) or float(valor) != int(float(valor)):
                    raise ValueError
                numero = int(float(valor))
            except (TypeError, ValueError):
                self.erros[campo] = "Deve ser um número inteiro."
                return self
            if (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo):
                self.erros[campo] = f"Deve estar entre {minimo} e {maximo}."
            else:
                self.saida[campo] = numero
        return self

    def dinheiro(self, campo, obrigatorio=True, minimo=Decimal("0")):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            try:
                if isinstance(valor, bool):
                    raise InvalidOperation
                # Aceita "80,50" (vírgula decimal) e 80.5
                numero = Decimal(str(valor).replace(",", ".")).quantize(Decimal("0.01"))
                if not numero.is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                self.erros[campo] = "Valor monetário inválido."
                return self
            if numero < minimo or numero > Decimal("99999999.99"):
                self.erros[campo] = f"Deve ser maior ou igual a {minimo}."
            else:
                self.saida[campo] = numero
        return self

    def booleano(self, campo, obrigatorio=False):
        ok, valor = self._valor(campo, obrigatorio)
        if ok:
            if isinstance(valor, bool):
                self.saida[campo] = valor
            elif str(valor).lower() in ("true", "1", "sim"):
                self.saida[campo] = True
            elif str(valor).lower() in ("false", "0", "nao", "não"):
                self.saida[campo] = False
            else:
                self.erros[campo] = "Deve ser verdadeiro ou falso."
        return self

    def resultado(self) -> dict:
        """Retorna os dados limpos ou lança ErroApi com todos os problemas."""
        if self.erros:
            raise ErroApi("Verifique os campos informados.", 400, self.erros)
        return self.saida

"""Models do SQLAlchemy: representação em Python das tabelas do Passo 1.

O arquivo database/schema.sql é a fonte oficial da estrutura (com CHECKs
e índices). Os models abaixo espelham exatamente os mesmos nomes de
tabelas e colunas. Itens marcados com [EXT] são extensões ao MER
original (ver docs/MER.md).
"""
from decimal import Decimal

from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .utils import serializar

# ---------------------------------------------------------------------
# Domínios (valores permitidos nos campos ENUM)
# ---------------------------------------------------------------------
STATUS_AGENDAMENTO = ("agendado", "confirmado", "concluido", "cancelado", "falta")
STATUS_PACOTE = ("ativo", "concluido", "cancelado")
FORMAS_PAGAMENTO = ("dinheiro", "pix", "cartao_credito", "cartao_debito")
TIPOS_NOTIFICACAO = ("confirmacao", "lembrete")
STATUS_ENVIO = ("pendente", "simulado", "enviado", "falha")
RESPOSTAS_CLIENTE = ("confirmou", "cancelou")
PERFIS_USUARIO = ("admin", "atendente")

# Status em que o horário continua "ocupado" na agenda do profissional
STATUS_OCUPAM_HORARIO = ("agendado", "confirmado", "concluido")


def _enum(valores, nome):
    return db.Enum(*valores, name=nome)


class SerializavelMixin:
    """Gera um dicionário (JSON) com as colunas da tabela."""

    def to_dict(self) -> dict:
        return {
            coluna.name: serializar(getattr(self, coluna.name))
            for coluna in self.__table__.columns
        }


# ---------------------------------------------------------------------
# [EXT] Usuário do sistema (login / LGPD)
# ---------------------------------------------------------------------
class Usuario(SerializavelMixin, db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(_enum(PERFIS_USUARIO, "perfil"), nullable=False, default="atendente")
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    data_cadastro = db.Column(db.DateTime, nullable=False, server_default=func.now())

    def definir_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self) -> dict:
        dados = super().to_dict()
        dados.pop("senha_hash")  # nunca expor o hash da senha
        return dados


# ---------------------------------------------------------------------
# 1. Cliente
# ---------------------------------------------------------------------
class Cliente(SerializavelMixin, db.Model):
    __tablename__ = "cliente"

    id_cliente = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    cpf = db.Column(db.String(11), unique=True)
    data_cadastro = db.Column(db.DateTime, nullable=False, server_default=func.now())

    agendamentos = db.relationship("Agendamento", back_populates="cliente", lazy="dynamic")
    pacotes = db.relationship("PacoteCliente", back_populates="cliente", lazy="dynamic")

    def __repr__(self):
        return f"<Cliente {self.id_cliente} {self.nome}>"


# ---------------------------------------------------------------------
# 2. Profissional
# ---------------------------------------------------------------------
class Profissional(SerializavelMixin, db.Model):
    __tablename__ = "profissional"

    id_profissional = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    especialidade = db.Column(db.String(80), nullable=False)
    telefone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    itens = db.relationship("ItemAgendamento", back_populates="profissional", lazy="dynamic")

    def __repr__(self):
        return f"<Profissional {self.id_profissional} {self.nome}>"


# ---------------------------------------------------------------------
# 3. Serviço
# ---------------------------------------------------------------------
class Servico(SerializavelMixin, db.Model):
    __tablename__ = "servico"

    id_servico = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    categoria = db.Column(db.String(60), nullable=False)
    duracao_minutos = db.Column(db.SmallInteger, nullable=False)
    preco_base = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f"<Servico {self.id_servico} {self.nome}>"


# ---------------------------------------------------------------------
# 4. Agendamento (cabeçalho)
# ---------------------------------------------------------------------
class Agendamento(SerializavelMixin, db.Model):
    __tablename__ = "agendamento"

    id_agendamento = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, server_default=func.now())
    valor_total = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    status_geral = db.Column(
        _enum(STATUS_AGENDAMENTO, "status_geral"), nullable=False, default="agendado"
    )

    cliente = db.relationship("Cliente", back_populates="agendamentos")
    itens = db.relationship(
        "ItemAgendamento",
        back_populates="agendamento",
        cascade="all, delete-orphan",
        order_by="ItemAgendamento.data_hora_inicio",
    )
    pagamentos = db.relationship("Pagamento", back_populates="agendamento")
    notificacoes = db.relationship(
        "Notificacao", back_populates="agendamento", cascade="all, delete-orphan"
    )

    # --- Valores calculados ------------------------------------------
    @property
    def inicio(self):
        return min((i.data_hora_inicio for i in self.itens), default=None)

    @property
    def fim(self):
        return max((i.data_hora_fim for i in self.itens), default=None)

    @property
    def valor_pago(self) -> Decimal:
        return sum((p.valor_pago for p in self.pagamentos), Decimal("0.00"))

    @property
    def saldo_devedor(self) -> Decimal:
        return max(self.valor_total - self.valor_pago, Decimal("0.00"))

    def recalcular_total(self) -> None:
        """valor_total = soma dos subtotais dos itens."""
        self.valor_total = sum((i.subtotal for i in self.itens), Decimal("0.00"))

    def to_dict(self, completo: bool = False) -> dict:
        dados = super().to_dict()
        dados.update(
            cliente_nome=self.cliente.nome if self.cliente else None,
            inicio=serializar(self.inicio),
            fim=serializar(self.fim),
            valor_pago=serializar(self.valor_pago),
            saldo_devedor=serializar(self.saldo_devedor),
        )
        if completo:
            dados["itens"] = [i.to_dict() for i in self.itens]
            dados["pagamentos"] = [p.to_dict() for p in self.pagamentos]
            dados["notificacoes"] = [n.to_dict() for n in self.notificacoes]
        return dados


# ---------------------------------------------------------------------
# 5. Item do agendamento (1 serviço + 1 profissional + 1 intervalo)
# ---------------------------------------------------------------------
class ItemAgendamento(SerializavelMixin, db.Model):
    __tablename__ = "item_agendamento"

    id_item = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer, db.ForeignKey("agendamento.id_agendamento", ondelete="CASCADE"), nullable=False
    )
    servico_id = db.Column(db.Integer, db.ForeignKey("servico.id_servico"), nullable=False)
    profissional_id = db.Column(
        db.Integer, db.ForeignKey("profissional.id_profissional"), nullable=False
    )
    data_hora_inicio = db.Column(db.DateTime, nullable=False)
    data_hora_fim = db.Column(db.DateTime, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    # [EXT] pacote que pagou esta sessão (subtotal = 0)
    pacote_cliente_id = db.Column(
        db.Integer, db.ForeignKey("pacote_cliente.id_pacote_cliente", ondelete="SET NULL")
    )

    agendamento = db.relationship("Agendamento", back_populates="itens")
    servico = db.relationship("Servico")
    profissional = db.relationship("Profissional", back_populates="itens")
    pacote = db.relationship("PacoteCliente", back_populates="itens")

    def to_dict(self) -> dict:
        dados = super().to_dict()
        dados.update(
            servico_nome=self.servico.nome if self.servico else None,
            profissional_nome=self.profissional.nome if self.profissional else None,
        )
        return dados


# ---------------------------------------------------------------------
# 6. Pagamento (de um agendamento OU [EXT] da compra de um pacote)
# ---------------------------------------------------------------------
class Pagamento(SerializavelMixin, db.Model):
    __tablename__ = "pagamento"

    id_pagamento = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey("agendamento.id_agendamento"))
    forma_pagamento = db.Column(_enum(FORMAS_PAGAMENTO, "forma_pagamento"), nullable=False)
    valor_pago = db.Column(db.Numeric(10, 2), nullable=False)
    data_pagamento = db.Column(db.DateTime, nullable=False, server_default=func.now())
    pacote_cliente_id = db.Column(  # [EXT]
        db.Integer, db.ForeignKey("pacote_cliente.id_pacote_cliente")
    )

    agendamento = db.relationship("Agendamento", back_populates="pagamentos")
    pacote = db.relationship("PacoteCliente", back_populates="pagamentos")


# ---------------------------------------------------------------------
# 7. Pacote do cliente (combo de várias sessões)
# ---------------------------------------------------------------------
class PacoteCliente(SerializavelMixin, db.Model):
    __tablename__ = "pacote_cliente"

    id_pacote_cliente = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    descricao = db.Column(db.String(160), nullable=False)
    qtd_sessoes_total = db.Column(db.SmallInteger, nullable=False)
    sessoes_realizadas = db.Column(db.SmallInteger, nullable=False, default=0)
    status_pacote = db.Column(_enum(STATUS_PACOTE, "status_pacote"), nullable=False, default="ativo")
    # [EXT]
    servico_id = db.Column(db.Integer, db.ForeignKey("servico.id_servico"), nullable=False)
    valor_pacote = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    data_compra = db.Column(db.DateTime, nullable=False, server_default=func.now())

    cliente = db.relationship("Cliente", back_populates="pacotes")
    servico = db.relationship("Servico")
    itens = db.relationship("ItemAgendamento", back_populates="pacote")
    pagamentos = db.relationship("Pagamento", back_populates="pacote")

    @property
    def sessoes_restantes(self) -> int:
        return self.qtd_sessoes_total - self.sessoes_realizadas

    @property
    def valor_pago(self) -> Decimal:
        return sum((p.valor_pago for p in self.pagamentos), Decimal("0.00"))

    @property
    def saldo_devedor(self) -> Decimal:
        return max(self.valor_pacote - self.valor_pago, Decimal("0.00"))

    @property
    def disponivel(self) -> bool:
        return self.status_pacote == "ativo" and self.sessoes_restantes > 0

    def consumir_sessao(self) -> None:
        """Registra uma sessão usada; conclui o pacote na última."""
        if not self.disponivel:
            raise ValueError("Pacote sem sessões disponíveis.")
        self.sessoes_realizadas += 1
        if self.sessoes_restantes == 0:
            self.status_pacote = "concluido"

    def devolver_sessao(self) -> None:
        """Desfaz o consumo (ex.: agendamento cancelado)."""
        if self.sessoes_realizadas > 0:
            self.sessoes_realizadas -= 1
            if self.status_pacote == "concluido":
                self.status_pacote = "ativo"

    def to_dict(self) -> dict:
        dados = super().to_dict()
        dados.update(
            cliente_nome=self.cliente.nome if self.cliente else None,
            servico_nome=self.servico.nome if self.servico else None,
            sessoes_restantes=self.sessoes_restantes,
            valor_pago=serializar(self.valor_pago),
            saldo_devedor=serializar(self.saldo_devedor),
        )
        return dados


# ---------------------------------------------------------------------
# [EXT] Notificação de WhatsApp (modo simulado gera link wa.me)
# ---------------------------------------------------------------------
class Notificacao(SerializavelMixin, db.Model):
    __tablename__ = "notificacao"
    __table_args__ = (
        db.UniqueConstraint("agendamento_id", "tipo", name="uq_notificacao_tipo"),
    )

    id_notificacao = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer, db.ForeignKey("agendamento.id_agendamento", ondelete="CASCADE"), nullable=False
    )
    tipo = db.Column(_enum(TIPOS_NOTIFICACAO, "tipo"), nullable=False)
    canal = db.Column(db.String(20), nullable=False, default="whatsapp")
    telefone_destino = db.Column(db.String(20), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    link_wa = db.Column(db.String(1000))
    status_envio = db.Column(_enum(STATUS_ENVIO, "status_envio"), nullable=False, default="pendente")
    data_envio = db.Column(db.DateTime)
    resposta_cliente = db.Column(_enum(RESPOSTAS_CLIENTE, "resposta_cliente"))
    data_resposta = db.Column(db.DateTime)

    agendamento = db.relationship("Agendamento", back_populates="notificacoes")

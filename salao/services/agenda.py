"""Regras de negócio da agenda.

Conceitos:
- Um AGENDAMENTO agrupa um ou mais ITENS (serviço + profissional + horário).
- Itens podem ser SEQUENCIAIS (um após o outro) ou SIMULTÂNEOS (mesmo
  horário com profissionais diferentes).
- O fim de cada item é calculado: início + duração do serviço.

Validações de cada item:
1. Serviço existe; profissional existe e está ativo.
2. Horário no futuro e dentro da janela do salão (dia e horário de
   funcionamento; o serviço precisa terminar até o fechamento).
3. Sem sobreposição com outro item do MESMO profissional, seja no
   mesmo agendamento ou em agendamentos já gravados (ativos).
   Regra de sobreposição: inicio_existente < novo_fim E fim_existente > novo_inicio
   (encostar, ex.: 10:00-11:00 e 11:00-12:00, é permitido).
4. Se usar pacote: pacote do mesmo cliente, do mesmo serviço, ativo e
   com sessões suficientes. O item fica com subtotal 0.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app

from ..api.validacao import ErroApi, Validador
from ..extensions import db
from ..models import (
    STATUS_OCUPAM_HORARIO,
    Agendamento,
    Cliente,
    ItemAgendamento,
    PacoteCliente,
    Profissional,
    Servico,
)
from ..utils import FUSO, agora

MAX_ITENS = 10
DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

# Mudanças de status permitidas (concluído, cancelado e falta são finais)
TRANSICOES = {
    "agendado": {"confirmado", "concluido", "cancelado", "falta"},
    "confirmado": {"concluido", "cancelado", "falta"},
}


# ---------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------
def ler_data_hora(valor) -> datetime:
    """'2026-11-10T09:00' -> datetime (horário de Brasília, sem segundos)."""
    if not isinstance(valor, str):
        raise ValueError("data/hora ausente")
    data_hora = datetime.fromisoformat(valor.strip().replace(" ", "T"))
    if data_hora.tzinfo is not None:
        data_hora = data_hora.astimezone(FUSO).replace(tzinfo=None)
    return data_hora.replace(second=0, microsecond=0)


def ler_data(valor, padrao: date | None = None) -> date:
    """'2026-11-10' -> date. Lança ErroApi se inválida."""
    if valor in (None, ""):
        if padrao is None:
            raise ErroApi("Informe a data (AAAA-MM-DD).")
        return padrao
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise ErroApi(f"Data inválida: {valor}. Use AAAA-MM-DD.") from None


def _id(valor) -> int | None:
    """Converte um identificador recebido no JSON em inteiro positivo."""
    if isinstance(valor, bool):
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def horario_salao():
    cfg = current_app.config
    return cfg["SALAO_ABERTURA"], cfg["SALAO_FECHAMENTO"], cfg["SALAO_DIAS_FUNCIONAMENTO"]


def validar_janela(inicio: datetime, fim: datetime) -> str | None:
    """Retorna a mensagem de erro se o intervalo estiver fora do expediente."""
    abertura, fechamento, dias = horario_salao()
    if inicio.weekday() not in dias:
        return f"O salão não funciona às {DIAS_SEMANA[inicio.weekday()]}s."
    if inicio.time() < abertura or fim.date() != inicio.date() or fim.time() > fechamento:
        return (
            f"Fora do horário de funcionamento ({abertura:%H:%M} às {fechamento:%H:%M}). "
            f"Este serviço iria das {inicio:%H:%M} às {fim:%H:%M}."
        )
    return None


def buscar_conflitos(id_profissional: int, inicio: datetime, fim: datetime,
                     ignorar_agendamento_id: int | None = None):
    """Itens do profissional que se sobrepõem ao intervalo [inicio, fim)."""
    consulta = (
        ItemAgendamento.query.join(Agendamento)
        .filter(
            ItemAgendamento.profissional_id == id_profissional,
            Agendamento.status_geral.in_(STATUS_OCUPAM_HORARIO),
            ItemAgendamento.data_hora_inicio < fim,
            ItemAgendamento.data_hora_fim > inicio,
        )
    )
    if ignorar_agendamento_id:
        consulta = consulta.filter(Agendamento.id_agendamento != ignorar_agendamento_id)
    return consulta.order_by(ItemAgendamento.data_hora_inicio)


# ---------------------------------------------------------------------
# Validação dos itens
# ---------------------------------------------------------------------
def planejar_itens(cliente: Cliente, itens_dados, ignorar_agendamento_id: int | None = None) -> list[dict]:
    """Valida a lista de itens recebida e devolve o "plano" de cada um.

    Não altera o banco. Acumula todos os erros e lança ErroApi
    (400 para dados inválidos, 409 para conflito de horário).
    """
    if not isinstance(itens_dados, list) or not itens_dados:
        raise ErroApi("Informe ao menos um serviço.", 400, {"itens": "Lista de serviços vazia."})
    if len(itens_dados) > MAX_ITENS:
        raise ErroApi(f"Máximo de {MAX_ITENS} serviços por agendamento.", 400)

    erros: dict[str, str] = {}
    houve_conflito = False
    planos: list[dict] = []
    uso_pacote: dict[int, int] = {}
    momento_atual = agora()

    # no_autoflush: evita gravações parciais enquanto consultamos o banco.
    with db.session.no_autoflush:
        # Trava as linhas dos profissionais envolvidos (SELECT ... FOR UPDATE)
        # até o fim da transação: duas pessoas não conseguem reservar o
        # mesmo horário ao mesmo tempo.
        ids_prof = sorted({_id(d.get("profissional_id")) for d in itens_dados
                           if isinstance(d, dict)} - {None})
        profissionais = {
            p.id_profissional: p
            for p in Profissional.query.filter(Profissional.id_profissional.in_(ids_prof))
            .with_for_update().all()
        } if ids_prof else {}

        for n, dados in enumerate(itens_dados):
            campo = f"itens[{n}]"
            if not isinstance(dados, dict):
                erros[campo] = "Item inválido."
                continue

            servico = db.session.get(Servico, _id(dados.get("servico_id")) or 0)
            if servico is None:
                erros[f"{campo}.servico_id"] = "Serviço não encontrado."

            profissional = profissionais.get(_id(dados.get("profissional_id")))
            if profissional is None:
                erros[f"{campo}.profissional_id"] = "Profissional não encontrado(a)."
            elif not profissional.ativo:
                erros[f"{campo}.profissional_id"] = f"{profissional.nome} está inativo(a)."

            try:
                inicio = ler_data_hora(dados.get("data_hora_inicio"))
            except (TypeError, ValueError):
                erros[f"{campo}.data_hora_inicio"] = "Data/hora inválida. Use AAAA-MM-DDTHH:MM."
                continue

            if servico is None or profissional is None or not profissional.ativo:
                continue

            fim = inicio + timedelta(minutes=servico.duracao_minutos)
            if inicio <= momento_atual:
                erros[f"{campo}.data_hora_inicio"] = "Não é possível agendar em horário que já passou."
                continue
            problema = validar_janela(inicio, fim)
            if problema:
                erros[f"{campo}.data_hora_inicio"] = problema
                continue

            # Preço: pacote (R$ 0), valor informado (desconto) ou preço base
            pacote = None
            subtotal = servico.preco_base
            if dados.get("pacote_cliente_id") not in (None, ""):
                pacote = db.session.get(PacoteCliente, _id(dados.get("pacote_cliente_id")) or 0)
                mensagem = None
                if pacote is None:
                    mensagem = "Pacote não encontrado."
                elif pacote.cliente_id != cliente.id_cliente:
                    mensagem = "Este pacote pertence a outro cliente."
                elif pacote.servico_id != servico.id_servico:
                    mensagem = f"Este pacote cobre apenas '{pacote.servico.nome}'."
                else:
                    uso_pacote[pacote.id_pacote_cliente] = uso_pacote.get(pacote.id_pacote_cliente, 0) + 1
                    if (pacote.status_pacote != "ativo"
                            or uso_pacote[pacote.id_pacote_cliente] > pacote.sessoes_restantes):
                        mensagem = "Pacote sem sessões disponíveis."
                if mensagem:
                    erros[f"{campo}.pacote_cliente_id"] = mensagem
                    continue
                subtotal = Decimal("0.00")
            elif dados.get("subtotal") not in (None, ""):
                try:
                    subtotal = Validador({"subtotal": dados["subtotal"]}).dinheiro("subtotal").resultado()["subtotal"]
                except ErroApi:
                    erros[f"{campo}.subtotal"] = "Valor inválido."
                    continue

            planos.append(dict(n=n, servico=servico, profissional=profissional, inicio=inicio,
                               fim=fim, subtotal=subtotal, pacote=pacote))

        # Conflitos dentro do próprio pedido (mesmo profissional, horários sobrepostos)
        for i, atual in enumerate(planos):
            for anterior in planos[:i]:
                if (atual["profissional"] is anterior["profissional"]
                        and atual["inicio"] < anterior["fim"] and atual["fim"] > anterior["inicio"]):
                    erros[f"itens[{atual['n']}].data_hora_inicio"] = (
                        f"{atual['profissional'].nome} já tem outro serviço neste agendamento "
                        f"das {anterior['inicio']:%H:%M} às {anterior['fim']:%H:%M}."
                    )
                    houve_conflito = True
                    break

        # Conflitos com agendamentos já gravados
        for plano in planos:
            chave = f"itens[{plano['n']}].data_hora_inicio"
            if chave in erros:
                continue
            conflito = buscar_conflitos(plano["profissional"].id_profissional, plano["inicio"],
                                        plano["fim"], ignorar_agendamento_id).first()
            if conflito:
                erros[chave] = (
                    f"{plano['profissional'].nome} já tem atendimento em "
                    f"{conflito.data_hora_inicio:%d/%m} das {conflito.data_hora_inicio:%H:%M} "
                    f"às {conflito.data_hora_fim:%H:%M}."
                )
                houve_conflito = True

    if erros:
        if houve_conflito:
            raise ErroApi("Horário indisponível para o(s) profissional(is) escolhido(s).", 409, erros)
        raise ErroApi("Verifique os serviços informados.", 400, erros)
    return planos


def _aplicar_planos(agendamento: Agendamento, planos: list[dict]) -> None:
    """Cria os itens a partir dos planos validados e consome os pacotes."""
    for plano in sorted(planos, key=lambda p: p["inicio"]):
        agendamento.itens.append(ItemAgendamento(
            servico_id=plano["servico"].id_servico,
            profissional_id=plano["profissional"].id_profissional,
            data_hora_inicio=plano["inicio"],
            data_hora_fim=plano["fim"],
            subtotal=plano["subtotal"],
            pacote_cliente_id=plano["pacote"].id_pacote_cliente if plano["pacote"] else None,
        ))
        if plano["pacote"]:
            plano["pacote"].consumir_sessao()
    agendamento.recalcular_total()


def _devolver_sessoes(agendamento: Agendamento) -> None:
    for item in agendamento.itens:
        if item.pacote is not None:
            item.pacote.devolver_sessao()


# ---------------------------------------------------------------------
# Operações
# ---------------------------------------------------------------------
def criar_agendamento(cliente: Cliente, itens_dados) -> Agendamento:
    planos = planejar_itens(cliente, itens_dados)
    agendamento = Agendamento(cliente_id=cliente.id_cliente, status_geral="agendado",
                              valor_total=Decimal("0.00"))
    _aplicar_planos(agendamento, planos)
    db.session.add(agendamento)
    db.session.flush()  # gera o id_agendamento
    return agendamento


def atualizar_agendamento(agendamento: Agendamento, itens_dados) -> bool:
    """Substitui os itens. Retorna True se algum horário mudou."""
    if agendamento.status_geral not in TRANSICOES:
        raise ErroApi(f"Agendamento '{agendamento.status_geral}' não pode ser alterado.", 409)

    horarios_antes = sorted((i.profissional_id, i.data_hora_inicio) for i in agendamento.itens)
    _devolver_sessoes(agendamento)  # libera as sessões para reutilização
    planos = planejar_itens(agendamento.cliente, itens_dados, agendamento.id_agendamento)

    agendamento.itens.clear()
    db.session.flush()
    _aplicar_planos(agendamento, planos)

    if agendamento.valor_total < agendamento.valor_pago:
        raise ErroApi("O novo valor total é menor que o valor já pago. Estorne o pagamento antes.", 409)

    horarios_depois = sorted((p["profissional"].id_profissional, p["inicio"]) for p in planos)
    mudou = horarios_antes != horarios_depois
    if mudou and agendamento.status_geral == "confirmado":
        agendamento.status_geral = "agendado"  # novo horário precisa de nova confirmação
    return mudou


def alterar_status(agendamento: Agendamento, novo_status: str) -> None:
    atual = agendamento.status_geral
    if novo_status == atual:
        return
    if novo_status not in TRANSICOES.get(atual, set()):
        raise ErroApi(f"Não é possível mudar o status de '{atual}' para '{novo_status}'.", 409)
    if novo_status == "cancelado":
        # Cancelamento devolve as sessões de pacote. Em caso de FALTA, a
        # sessão é considerada usada (política comum em salões).
        _devolver_sessoes(agendamento)
    agendamento.status_geral = novo_status


def horarios_livres(profissional: Profissional, dia: date, duracao_minutos: int,
                    ignorar_agendamento_id: int | None = None) -> list[str]:
    """Horários de início em que o serviço cabe na agenda do profissional."""
    abertura, fechamento, dias = horario_salao()
    if dia.weekday() not in dias or not profissional.ativo:
        return []
    inicio_dia = datetime.combine(dia, abertura)
    fim_dia = datetime.combine(dia, fechamento)
    ocupados = [(i.data_hora_inicio, i.data_hora_fim)
                for i in buscar_conflitos(profissional.id_profissional, inicio_dia, fim_dia,
                                          ignorar_agendamento_id)]
    passo = timedelta(minutes=current_app.config["AGENDA_INTERVALO_MINUTOS"])
    duracao = timedelta(minutes=duracao_minutos)
    momento_atual = agora()

    livres, horario = [], inicio_dia
    while horario + duracao <= fim_dia:
        fim = horario + duracao
        if horario > momento_atual and all(not (ini < fim and f > horario) for ini, f in ocupados):
            livres.append(f"{horario:%H:%M}")
        horario += passo
    return livres

"""Testes do Passo 4: agendamentos, disponibilidade, pagamentos, pacotes e WhatsApp."""
from datetime import date, datetime, timedelta
from urllib.parse import unquote

import pytest

from salao.extensions import db
from salao.models import Agendamento
from salao.services import whatsapp


def dia_util(dias_a_frente=2) -> date:
    """Próximo dia de funcionamento (seg-sáb) a partir de N dias à frente."""
    dia = date.today() + timedelta(days=dias_a_frente)
    while dia.weekday() == 6:
        dia += timedelta(days=1)
    return dia


def em(dia: date, hora: str) -> str:
    return f"{dia.isoformat()}T{hora}"


@pytest.fixture
def cad(admin):
    """Cadastros básicos: 1 cliente, 2 profissionais, 3 serviços."""
    def post(rota, dados):
        r = admin.post(rota, json=dados)
        assert r.status_code == 201, r.get_json()
        return r.get_json()

    return {
        "api": admin,
        "cliente": post("/api/clientes", {"nome": "Carla Mendes", "telefone": "11987650003"})["id_cliente"],
        "outro_cliente": post("/api/clientes", {"nome": "Julia", "telefone": "11987650009"})["id_cliente"],
        "regis": post("/api/profissionais", {"nome": "Régis", "especialidade": "Cabeleireiro"})["id_profissional"],
        "bia": post("/api/profissionais", {"nome": "Bia", "especialidade": "Manicure"})["id_profissional"],
        "coloracao": post("/api/servicos", {"nome": "Coloração", "categoria": "Cabelo",
                                            "duracao_minutos": 120, "preco_base": 180})["id_servico"],
        "manicure": post("/api/servicos", {"nome": "Manicure", "categoria": "Unhas",
                                           "duracao_minutos": 40, "preco_base": 35})["id_servico"],
        "escova": post("/api/servicos", {"nome": "Escova", "categoria": "Cabelo",
                                         "duracao_minutos": 45, "preco_base": 60})["id_servico"],
    }


def agendar(cad, itens, cliente=None):
    return cad["api"].post("/api/agendamentos", json={"cliente_id": cliente or cad["cliente"], "itens": itens})


# ---------------------------------------------------------- simultâneos/sequenciais
def test_servicos_simultaneos_e_sequenciais(cad):
    dia = dia_util()
    r = agendar(cad, [
        {"servico_id": cad["coloracao"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "09:00")},
        {"servico_id": cad["manicure"], "profissional_id": cad["bia"], "data_hora_inicio": em(dia, "09:00")},  # simultâneo
        {"servico_id": cad["escova"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "11:00")},  # sequência
    ])
    assert r.status_code == 201, r.get_json()
    ag = r.get_json()
    assert ag["valor_total"] == 275.0  # 180 + 35 + 60
    assert ag["inicio"] == em(dia, "09:00") and ag["fim"] == em(dia, "11:45")
    assert [i["data_hora_fim"] for i in ag["itens"]][0] == em(dia, "11:00")

    # Confirmação de WhatsApp gerada automaticamente com link wa.me
    notif = ag["notificacoes"][0]
    assert notif["tipo"] == "confirmacao" and notif["status_envio"] == "simulado"
    assert notif["link_wa"].startswith("https://wa.me/5511987650003?text=")
    assert "Coloração com Régis" in unquote(notif["link_wa"])
    assert "R$ 275,00" in notif["mensagem"]


def test_conflito_de_horario(cad):
    dia = dia_util()
    assert agendar(cad, [{"servico_id": cad["coloracao"], "profissional_id": cad["regis"],
                          "data_hora_inicio": em(dia, "09:00")}]).status_code == 201
    # Outro cliente, mesmo profissional, horário sobreposto (10:00 < 11:00)
    r = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                       "data_hora_inicio": em(dia, "10:00")}], cliente=cad["outro_cliente"])
    assert r.status_code == 409
    assert "Régis já tem atendimento" in r.get_json()["campos"]["itens[0].data_hora_inicio"]
    # Encostado no fim (11:00) é permitido
    assert agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                          "data_hora_inicio": em(dia, "11:00")}], cliente=cad["outro_cliente"]).status_code == 201


def test_conflito_dentro_do_mesmo_pedido(cad):
    dia = dia_util()
    r = agendar(cad, [
        {"servico_id": cad["coloracao"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "09:00")},
        {"servico_id": cad["escova"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "10:00")},
    ])
    assert r.status_code == 409


@pytest.mark.parametrize("hora,trecho", [
    ("07:00", "Fora do horário"),
    ("19:00", "Fora do horário"),  # coloração de 2h terminaria 21:00
])
def test_fora_da_janela(cad, hora, trecho):
    r = agendar(cad, [{"servico_id": cad["coloracao"], "profissional_id": cad["regis"],
                       "data_hora_inicio": em(dia_util(), hora)}])
    assert r.status_code == 400 and trecho in r.get_json()["campos"]["itens[0].data_hora_inicio"]


def test_domingo_passado_e_inativo(cad):
    domingo = date.today() + timedelta(days=(6 - date.today().weekday()) % 7 or 7)
    r = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                       "data_hora_inicio": em(domingo, "10:00")}])
    assert r.status_code == 400 and "domingo" in str(r.get_json())

    ontem = date.today() - timedelta(days=1)
    r = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                       "data_hora_inicio": em(ontem, "10:00")}])
    assert r.status_code == 400 and "já passou" in str(r.get_json())

    cad["api"].delete(f"/api/profissionais/{cad['bia']}")
    r = agendar(cad, [{"servico_id": cad["manicure"], "profissional_id": cad["bia"],
                       "data_hora_inicio": em(dia_util(), "10:00")}])
    assert r.status_code == 400 and "inativo" in str(r.get_json())


# ---------------------------------------------------------- edição / status
def test_reagendar_e_cancelar_libera_horario(cad):
    dia = dia_util()
    ag = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                        "data_hora_inicio": em(dia, "09:00")}]).get_json()
    id_ = ag["id_agendamento"]
    # Remarcar para 09:30 (sobrepõe o próprio horário antigo: permitido)
    r = cad["api"].put(f"/api/agendamentos/{id_}", json={"itens": [
        {"servico_id": cad["escova"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "09:30")}]})
    assert r.status_code == 200 and r.get_json()["horario_alterado"] is True
    assert "09:30" in r.get_json()["notificacoes"][0]["mensagem"]

    assert cad["api"].patch(f"/api/agendamentos/{id_}/status", json={"status": "confirmado"}).status_code == 200
    assert cad["api"].post(f"/api/agendamentos/{id_}/cancelar").get_json()["status_geral"] == "cancelado"
    # Cancelado é final
    assert cad["api"].patch(f"/api/agendamentos/{id_}/status", json={"status": "confirmado"}).status_code == 409
    # Horário liberado para outro cliente
    assert agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                          "data_hora_inicio": em(dia, "09:30")}], cliente=cad["outro_cliente"]).status_code == 201


def test_disponibilidade(cad):
    dia = dia_util()
    agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                   "data_hora_inicio": em(dia, "09:00")}])
    r = cad["api"].get(f"/api/disponibilidade?profissional_id={cad['regis']}&servico_id={cad['escova']}&data={dia}")
    horarios = r.get_json()["horarios"]
    assert "08:00" in horarios and "08:15" in horarios
    assert "08:30" not in horarios and "09:00" not in horarios  # 08:30+45min invade 09:00
    assert "09:45" in horarios and "19:15" in horarios and "19:30" not in horarios

    agenda = cad["api"].get(f"/api/agenda?inicio={dia}&fim={dia + timedelta(days=6)}").get_json()
    assert len(agenda["itens"]) == 1 and agenda["horario"]["abertura"] == "08:00"


# ---------------------------------------------------------- pacotes
def test_pacote_consumo_e_devolucao(cad):
    api = cad["api"]
    r = api.post("/api/pacotes", json={"cliente_id": cad["cliente"], "servico_id": cad["escova"],
                                       "qtd_sessoes_total": 2, "valor_pacote": 100,
                                       "pagamento": {"forma_pagamento": "pix", "valor_pago": 40}})
    assert r.status_code == 201
    pacote = r.get_json()
    assert pacote["descricao"] == "Pacote 2x Escova" and pacote["saldo_devedor"] == 60.0
    id_pac = pacote["id_pacote_cliente"]
    dia = dia_util()

    def item(hora, prof="regis"):
        return {"servico_id": cad["escova"], "profissional_id": cad[prof],
                "data_hora_inicio": em(dia, hora), "pacote_cliente_id": id_pac}

    ag = agendar(cad, [item("09:00"), item("09:00", "bia")]).get_json()  # usa as 2 sessões
    assert ag["valor_total"] == 0.0
    assert api.get(f"/api/pacotes/{id_pac}").get_json()["status_pacote"] == "concluido"

    # Sem sessões disponíveis
    r = agendar(cad, [item("14:00")])
    assert r.status_code == 400 and "sem sessões" in str(r.get_json())
    # Pacote de outro cliente
    r = agendar(cad, [item("14:00")], cliente=cad["outro_cliente"])
    assert "outro cliente" in str(r.get_json())

    # Cancelar devolve as sessões
    api.post(f"/api/agendamentos/{ag['id_agendamento']}/cancelar")
    pacote = api.get(f"/api/pacotes/{id_pac}").get_json()
    assert pacote["sessoes_realizadas"] == 0 and pacote["status_pacote"] == "ativo"
    assert api.get(f"/api/pacotes?cliente_id={cad['cliente']}&disponiveis=true").get_json()[0]["sessoes_restantes"] == 2


# ---------------------------------------------------------- pagamentos
def test_pagamentos(cad):
    api = cad["api"]
    ag = agendar(cad, [{"servico_id": cad["coloracao"], "profissional_id": cad["regis"],
                        "data_hora_inicio": em(dia_util(), "09:00")}]).get_json()
    id_ = ag["id_agendamento"]
    r = api.post("/api/pagamentos", json={"agendamento_id": id_, "forma_pagamento": "pix", "valor_pago": 100})
    assert r.status_code == 201 and r.get_json()["saldo_devedor_restante"] == 80.0
    r = api.post("/api/pagamentos", json={"agendamento_id": id_, "forma_pagamento": "dinheiro", "valor_pago": 90})
    assert r.status_code == 409  # acima do saldo
    r = api.post("/api/pagamentos", json={"agendamento_id": id_, "forma_pagamento": "boleto", "valor_pago": 10})
    assert r.status_code == 400
    api.post("/api/pagamentos", json={"agendamento_id": id_, "forma_pagamento": "cartao_debito", "valor_pago": "80,00"})
    detalhe = api.get(f"/api/agendamentos/{id_}").get_json()
    assert detalhe["valor_pago"] == 180.0 and detalhe["saldo_devedor"] == 0.0
    assert len(api.get("/api/pagamentos").get_json()) == 2


# ---------------------------------------------------------- WhatsApp / cron
def test_rotina_de_lembretes(app, cad):
    dia = dia_util(2)
    ag = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                        "data_hora_inicio": em(dia, "10:00")}]).get_json()

    # Endpoint exige token quando não há login
    anonimo = app.test_client()
    assert anonimo.post("/api/tarefas/lembretes").status_code == 401
    app.config["CRON_TOKEN"] = "segredo"
    assert anonimo.post("/api/tarefas/lembretes", headers={"X-Cron-Token": "errado"}).status_code == 401
    r = anonimo.post("/api/tarefas/lembretes", headers={"X-Cron-Token": "segredo"})
    assert r.status_code == 200 and r.get_json()["quantidade"] == 0  # ainda faltam > 24h

    # Simula a execução na véspera, 20h antes do horário
    referencia = datetime.fromisoformat(em(dia, "10:00")) - timedelta(hours=20)
    with app.app_context():
        gerados = whatsapp.processar_lembretes(referencia)
        assert len(gerados) == 1 and "amanhã" in gerados[0].mensagem
        db.session.commit()
        assert whatsapp.processar_lembretes(referencia) == []  # sem duplicar
        assert len(db.session.get(Agendamento, ag["id_agendamento"]).notificacoes) == 2


def test_resposta_simulada_do_cliente(cad):
    api = cad["api"]
    ag = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                        "data_hora_inicio": em(dia_util(), "10:00")}]).get_json()
    id_notif = ag["notificacoes"][0]["id_notificacao"]
    r = api.post(f"/api/notificacoes/{id_notif}/resposta", json={"resposta": "confirmou"})
    assert r.status_code == 200 and r.get_json()["status_geral"] == "confirmado"
    assert api.get("/api/notificacoes?tipo=confirmacao").get_json()[0]["resposta_cliente"] == "confirmou"

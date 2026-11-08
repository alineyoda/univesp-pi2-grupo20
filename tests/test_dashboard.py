"""Testes do Passo 5: dashboard gerencial e página principal (SPA)."""
from tests.test_agendamentos import agendar, cad, dia_util, em  # noqa: F401 (fixture cad)


def test_pagina_principal_e_arquivos_estaticos(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '<html lang="pt-BR">' in html and "Pular para o conteúdo principal" in html
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/css/estilo.css").status_code == 200
    assert client.get("/static/nao-existe.js").status_code == 404


def test_dashboard_exige_login(client):
    assert client.get("/api/dashboard").status_code == 401


def test_dashboard_indicadores(cad):
    api = cad["api"]
    dia = dia_util()
    ag1 = agendar(cad, [
        {"servico_id": cad["coloracao"], "profissional_id": cad["regis"], "data_hora_inicio": em(dia, "09:00")},
        {"servico_id": cad["manicure"], "profissional_id": cad["bia"], "data_hora_inicio": em(dia, "09:00")},
    ]).get_json()
    ag2 = agendar(cad, [{"servico_id": cad["escova"], "profissional_id": cad["regis"],
                         "data_hora_inicio": em(dia, "14:00")}], cliente=cad["outro_cliente"]).get_json()
    api.patch(f"/api/agendamentos/{ag1['id_agendamento']}/status", json={"status": "concluido"})
    api.patch(f"/api/agendamentos/{ag2['id_agendamento']}/status", json={"status": "falta"})
    api.post("/api/pagamentos", json={"agendamento_id": ag1["id_agendamento"], "forma_pagamento": "pix", "valor_pago": 215})

    hoje = __import__("datetime").date.today()
    r = api.get(f"/api/dashboard?inicio={hoje}&fim={dia}")
    assert r.status_code == 200
    d = r.get_json()
    assert d["resumo"]["agendamentos"] == 2
    assert d["resumo"]["concluidos"] == 1 and d["resumo"]["faltas"] == 1
    assert d["resumo"]["taxa_faltas"] == 0.5
    assert d["resumo"]["faturamento_recebido"] == 215.0
    assert d["resumo"]["ticket_medio"] == 215.0
    assert d["por_forma_pagamento"][0]["forma_pagamento"] == "pix"
    assert {s["servico"] for s in d["top_servicos"]} == {"Coloração", "Manicure", "Escova"}
    assert len(d["serie_diaria"]) == (dia - hoje).days + 1
    assert sum(x["atendimentos"] for x in d["serie_diaria"]) == 2


def test_dashboard_periodo_invalido(admin):
    assert admin.get("/api/dashboard?inicio=2026-02-10&fim=2026-01-01").status_code == 400

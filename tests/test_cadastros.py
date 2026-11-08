"""Testes do Passo 3: login e CRUD de Clientes, Profissionais e Serviços."""
from datetime import datetime

from salao.extensions import db
from salao.models import Agendamento, ItemAgendamento


# ------------------------------------------------------------------ login
def test_rotas_protegidas_exigem_login(client):
    for rota in ("/api/clientes", "/api/profissionais", "/api/servicos"):
        assert client.get(rota).status_code == 401


def test_login_invalido(client):
    r = client.post("/api/auth/login", json={"email": "admin@salao.com", "senha": "errada"})
    assert r.status_code == 401
    assert r.get_json()["erro"] == "E-mail ou senha inválidos."


def test_login_me_logout(admin):
    me = admin.get("/api/auth/me").get_json()
    assert me["perfil"] == "admin" and "senha_hash" not in me
    assert admin.post("/api/auth/logout").status_code == 200
    assert admin.get("/api/clientes").status_code == 401


# --------------------------------------------------------------- clientes
def test_crud_cliente(admin):
    r = admin.post("/api/clientes", json={
        "nome": "  Maria   Silva ", "telefone": "(11) 98765-4321", "cpf": "529.982.247-25"})
    assert r.status_code == 201
    cliente = r.get_json()
    assert cliente["nome"] == "Maria Silva"
    assert cliente["telefone"] == "5511987654321"  # normalizado para o WhatsApp
    assert cliente["cpf"] == "52998224725"
    id_ = cliente["id_cliente"]

    assert admin.get("/api/clientes?busca=maria").get_json()[0]["id_cliente"] == id_
    assert admin.get(f"/api/clientes/{id_}").get_json()["total_agendamentos"] == 0

    r = admin.patch(f"/api/clientes/{id_}", json={"nome": "Maria S. Souza"})
    assert r.status_code == 200 and r.get_json()["cpf"] == "52998224725"

    assert admin.delete(f"/api/clientes/{id_}").status_code == 204
    assert admin.get(f"/api/clientes/{id_}").status_code == 404


def test_cliente_validacoes(admin):
    r = admin.post("/api/clientes", json={"nome": "A", "telefone": "123", "cpf": "11111111111"})
    assert r.status_code == 400
    assert set(r.get_json()["campos"]) == {"nome", "telefone", "cpf"}

    admin.post("/api/clientes", json={"nome": "Ana", "telefone": "11987654321", "cpf": "52998224725"})
    r = admin.post("/api/clientes", json={"nome": "Bia", "telefone": "11987654322", "cpf": "52998224725"})
    assert r.status_code == 409


def test_cliente_com_agendamento_nao_pode_ser_excluido(app, admin):
    id_cli = admin.post("/api/clientes", json={"nome": "Ana", "telefone": "11987654321"}).get_json()["id_cliente"]
    id_pro = admin.post("/api/profissionais", json={"nome": "Bia", "especialidade": "Unhas"}).get_json()["id_profissional"]
    id_ser = admin.post("/api/servicos", json={
        "nome": "Manicure", "categoria": "Unhas", "duracao_minutos": 40, "preco_base": "35,00"}).get_json()["id_servico"]
    with app.app_context():
        ag = Agendamento(cliente_id=id_cli)
        ag.itens.append(ItemAgendamento(servico_id=id_ser, profissional_id=id_pro,
                                        data_hora_inicio=datetime(2026, 1, 5, 9),
                                        data_hora_fim=datetime(2026, 1, 5, 9, 40), subtotal=35))
        db.session.add(ag)
        db.session.commit()

    r = admin.delete(f"/api/clientes/{id_cli}")
    assert r.status_code == 409 and "1 agendamento" in r.get_json()["erro"]
    r = admin.delete(f"/api/servicos/{id_ser}")
    assert r.status_code == 409 and "1 atendimento" in r.get_json()["erro"]


def test_exclusao_somente_admin(admin, atendente):
    # "atendente" e "admin" compartilham o mesmo client; o último login vale.
    id_ = atendente.post("/api/clientes", json={"nome": "Ana", "telefone": "11987654321"}).get_json()["id_cliente"]
    assert atendente.delete(f"/api/clientes/{id_}").status_code == 403


# ---------------------------------------------------------- profissionais
def test_profissional_exclusao_logica(admin):
    r = admin.post("/api/profissionais", json={
        "nome": "Carla", "especialidade": "Cabeleireira", "telefone": "11 97654-0001"})
    assert r.status_code == 201
    id_ = r.get_json()["id_profissional"]

    r = admin.delete(f"/api/profissionais/{id_}")
    assert r.status_code == 200 and r.get_json()["profissional"]["ativo"] is False
    assert admin.delete(f"/api/profissionais/{id_}").status_code == 409
    # Continua existindo, apenas inativo
    assert admin.get(f"/api/profissionais/{id_}").status_code == 200
    assert admin.get("/api/profissionais?ativo=true").get_json() == []
    assert len(admin.get("/api/profissionais?ativo=false").get_json()) == 1
    # Reativação
    assert admin.patch(f"/api/profissionais/{id_}", json={"ativo": True}).get_json()["ativo"] is True


def test_put_exige_todos_os_campos(admin):
    id_ = admin.post("/api/profissionais", json={"nome": "Carla", "especialidade": "Unhas"}).get_json()["id_profissional"]
    r = admin.put(f"/api/profissionais/{id_}", json={"nome": "Carla Lima"})
    assert r.status_code == 400 and "especialidade" in r.get_json()["campos"]


# --------------------------------------------------------------- serviços
def test_crud_servico(admin):
    dados = {"nome": "Escova", "categoria": "Cabelo", "duracao_minutos": 45, "preco_base": 60}
    r = admin.post("/api/servicos", json=dados)
    assert r.status_code == 201 and r.get_json()["preco_base"] == 60.0
    id_ = r.get_json()["id_servico"]

    assert admin.post("/api/servicos", json=dados).status_code == 409  # nome repetido
    assert admin.get("/api/servicos/categorias").get_json() == ["Cabelo"]
    r = admin.put(f"/api/servicos/{id_}", json={**dados, "preco_base": "65.50"})
    assert r.get_json()["preco_base"] == 65.5

    r = admin.post("/api/servicos", json={**dados, "nome": "Escova curta", "duracao_minutos": 2, "preco_base": -1})
    assert r.status_code == 400 and set(r.get_json()["campos"]) == {"duracao_minutos", "preco_base"}

    assert admin.delete(f"/api/servicos/{id_}").status_code == 204


def test_exige_json(admin):
    r = admin.post("/api/servicos", data="nome=x")
    assert r.status_code == 415

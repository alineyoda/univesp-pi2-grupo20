# Sistema de Agendamentos para Salões de Beleza

Projeto Integrador II do Grupo 20 da Univesp. É um sistema web para microempresas de serviços estéticos gerenciarem clientes, profissionais, serviços, agendamentos, pagamentos e pacotes, com lembretes por WhatsApp.

**Stack:** Python (Flask, API REST), MySQL 8 e HTML, CSS e JavaScript puro, com acessibilidade WCAG 2.2. O deploy será feito no Render, com MySQL externo (TiDB Cloud ou Aiven).

## Banco de dados (Passo 1)

1. Abra o **MySQL Workbench** e conecte-se ao servidor local.
2. Use **File → Open SQL Script** para abrir [`database/schema.sql`](database/schema.sql) e execute o script inteiro (ícone ⚡).
3. Para ter dados de demonstração, abra e execute [`database/seed.sql`](database/seed.sql) do mesmo jeito.

O modelo de dados e as extensões ao MER original estão em [`docs/MER.md`](docs/MER.md).

## Aplicação Flask (Passo 2)

Rode no PowerShell, na pasta do projeto:

```powershell
python -m venv .venv                       # cria o ambiente virtual (uma vez)
.\.venv\Scripts\Activate.ps1               # ativa o ambiente
python -m pip install -r requirements.txt  # instala as dependências
copy .env.example .env                     # depois edite o .env com a senha do MySQL
flask testar-conexao                       # confere o acesso ao banco
flask criar-usuario                        # cria o login do sistema
python app.py                              # inicia em http://127.0.0.1:5000
```

Se o PowerShell bloquear o `Activate.ps1`, rode antes `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Para conferir se tudo está no ar, acesse <http://127.0.0.1:5000/api/status>.

### Estrutura

```
app.py              ponto de entrada (python app.py / gunicorn app:app)
requirements.txt    dependências
.env.example        modelo de configuração (local e TiDB/Aiven)
salao/
  __init__.py       fábrica da aplicação (create_app) e /api/status
  config.py         leitura do .env, conexão com o banco (SSL) e regras do salão
  extensions.py     instância do SQLAlchemy
  models.py         Models de todas as tabelas, incluindo as extensões
  cli.py            comandos: testar-conexao, executar-sql, criar-usuario
  utils.py          horário de Brasília e conversão para JSON
database/           scripts SQL (Passo 1)
docs/MER.md         modelo de dados
```

### Banco na nuvem (deploy)

Preencha o bloco do TiDB Cloud ou do Aiven no `.env`, que fica comentado no `.env.example`. Depois crie as tabelas pelo próprio Flask, sem precisar do Workbench:

```powershell
flask executar-sql database/schema.sql
flask executar-sql database/seed.sql
```

## Andamento

- [x] Passo 1: script DDL do MySQL
- [x] Passo 2: estrutura base do Flask e Models
- [ ] Passo 3: API REST (CRUD de Clientes, Profissionais e Serviços)
- [ ] Passo 4: Agendamentos (disponibilidade) e WhatsApp em modo simulado
- [ ] Passo 5: Front-end acessível (agenda, formulários e dashboard)

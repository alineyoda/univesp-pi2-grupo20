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
  api/              rotas/controllers REST (Passo 3)
    __init__.py     registro dos blueprints e erros em JSON
    validacao.py    validação de campos, CPF, telefone e erros padronizados
    auth.py         login/logout/me e proteção das rotas
    clientes.py  profissionais.py  servicos.py
    agendamentos.py pagamentos.py pacotes.py notificacoes.py   (Passo 4)
  services/         regras de negócio (Passo 4)
    agenda.py       disponibilidade, conflitos, janela do salão, pacotes, status
    whatsapp.py     mensagens, link wa.me, lembretes e respostas simuladas
tests/              testes automatizados (pytest)
database/           scripts SQL (Passo 1)
docs/MER.md         modelo de dados
```

### Banco na nuvem (deploy)

Preencha o bloco do TiDB Cloud ou do Aiven no `.env`, que fica comentado no `.env.example`. Depois crie as tabelas pelo próprio Flask, sem precisar do Workbench:

```powershell
flask executar-sql database/schema.sql
flask executar-sql database/seed.sql
```

## API REST (Passo 3)

Todas as rotas, exceto o login e `/api/status`, exigem login. A autenticação usa uma sessão em cookie (HttpOnly, SameSite=Lax, válida por 8 horas). As requisições `POST`, `PUT` e `PATCH` precisam enviar JSON. Os erros sempre voltam no formato `{"erro": "...", "campos": {...}}`.

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/auth/login` | `{"email", "senha"}` inicia a sessão |
| POST | `/api/auth/logout` | encerra a sessão |
| GET | `/api/auth/me` | usuário logado |
| GET | `/api/clientes?busca=` | lista clientes (busca por nome, telefone ou CPF) |
| GET | `/api/clientes/<id>` | detalhe, com pacotes e total de agendamentos |
| POST | `/api/clientes` | `{"nome", "telefone", "cpf"?}` |
| PUT / PATCH | `/api/clientes/<id>` | atualização completa / parcial |
| DELETE | `/api/clientes/<id>` | **admin**; bloqueado (409) se o cliente tiver agendamentos ou pacotes |
| GET | `/api/profissionais?ativo=true\|false&busca=` | lista profissionais |
| GET / POST | `/api/profissionais[/<id>]` | detalhe / cria `{"nome", "especialidade", "telefone"?}` |
| PUT / PATCH | `/api/profissionais/<id>` | atualiza; `{"ativo": true}` reativa |
| DELETE | `/api/profissionais/<id>` | **admin**; exclusão lógica (`ativo = false`) |
| GET | `/api/servicos?categoria=&busca=` | lista serviços |
| GET | `/api/servicos/categorias` | categorias existentes |
| GET / POST | `/api/servicos[/<id>]` | detalhe / cria `{"nome", "categoria", "duracao_minutos", "preco_base"}` |
| PUT / PATCH | `/api/servicos/<id>` | atualização completa / parcial |
| DELETE | `/api/servicos/<id>` | **admin**; bloqueado (409) se o serviço estiver em algum agendamento ou pacote |

O telefone é guardado no formato do WhatsApp: `(11) 98765-4321` vira `5511987654321`. O CPF passa pela verificação dos dígitos.

## Agendamentos, pagamentos, pacotes e WhatsApp (Passo 4)

As regras de negócio ficam em [`salao/services/`](salao/services/) e as rotas em [`salao/api/`](salao/api/).

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/agenda?inicio=&fim=&profissional_id=` | itens do período para o calendário diário ou semanal, mais o horário do salão e os profissionais ativos |
| GET | `/api/disponibilidade?profissional_id=&servico_id=&data=` | horários livres, a cada 15 minutos |
| GET | `/api/agendamentos?inicio=&fim=&cliente_id=&status=` | lista agendamentos |
| GET | `/api/agendamentos/<id>` | detalhe com itens, pagamentos e notificações |
| POST | `/api/agendamentos` | `{"cliente_id", "itens": [{"servico_id", "profissional_id", "data_hora_inicio", "pacote_cliente_id"?, "subtotal"?}]}` |
| PUT | `/api/agendamentos/<id>` | reagenda (substitui os itens) e reenvia a confirmação |
| PATCH | `/api/agendamentos/<id>/status` | `{"status": "confirmado\|concluido\|falta\|cancelado"}` |
| POST | `/api/agendamentos/<id>/cancelar` | cancela e devolve as sessões de pacote |
| POST | `/api/agendamentos/<id>/notificar` | gera de novo a mensagem `{"tipo": "confirmacao\|lembrete"}` |
| GET / POST | `/api/pagamentos` | lista / registra `{"agendamento_id" OU "pacote_cliente_id", "forma_pagamento", "valor_pago"}` |
| DELETE | `/api/pagamentos/<id>` | estorno (**admin**) |
| GET / POST | `/api/pacotes` | lista (`?cliente_id=&disponiveis=true`) / vende `{"cliente_id", "servico_id", "qtd_sessoes_total", "valor_pacote", "pagamento"?}` |
| GET / PATCH / DELETE | `/api/pacotes/<id>` | detalhe com sessões / edita ou cancela / exclui (só se nunca foi usado) |
| GET | `/api/notificacoes?status=&tipo=` | histórico de mensagens |
| POST | `/api/notificacoes/<id>/resposta` | simula a resposta do cliente `{"resposta": "confirmou\|cancelou"}` |
| POST | `/api/tarefas/lembretes` | rotina de lembretes (cabeçalho `X-Cron-Token` ou usuário logado) |

**Regras da agenda**

- O fim de cada serviço é calculado como início + duração do serviço.
- Todos os serviços precisam começar no futuro, num dia de funcionamento, e terminar até o fechamento do salão.
- Um profissional não pode ter dois atendimentos sobrepostos. Encostar é permitido: um serviço que termina às 10:00 não impede outro que começa às 10:00. Agendamentos cancelados liberam o horário.
- **Simultâneos:** o mesmo horário com profissionais diferentes. **Sequenciais:** um serviço depois do outro. O valor total é a soma dos subtotais.
- Na hora de gravar, o sistema bloqueia temporariamente os profissionais envolvidos (`SELECT ... FOR UPDATE`). Isso impede que duas pessoas reservem o mesmo horário ao mesmo tempo.
- **Pacote:** o atendimento sai por R$ 0 e consome uma sessão. Se o agendamento for cancelado, a sessão volta para o pacote. Em caso de falta, a sessão é considerada usada.
- **Mudança de status:** um agendamento `agendado` pode passar para `confirmado`, `concluido`, `falta` ou `cancelado`. Um `confirmado` pode passar para `concluido`, `falta` ou `cancelado`. Os outros três status são finais.

**Lembretes automáticos em produção:** no [cron-job.org](https://cron-job.org), crie uma tarefa a cada 15 minutos com `POST https://SEU-APP.onrender.com/api/tarefas/lembretes` e o cabeçalho `X-Cron-Token: <CRON_TOKEN>`. Essa chamada também "acorda" o serviço gratuito do Render.

### Testes automatizados

Os testes usam um SQLite temporário e não alteram o MySQL:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

## Front-end e Dashboard (Passo 5)

Rode `python app.py`, abra <http://127.0.0.1:5000> e faça login com o usuário criado em `flask criar-usuario`.

É uma **Single Page Application** em HTML, CSS e JavaScript puro, sem bibliotecas nem etapa de build. O Flask entrega a página [`salao/templates/index.html`](salao/templates/index.html), e o JavaScript (módulos ES em [`salao/static/js/`](salao/static/js/)) troca de tela pelo endereço (`#/agenda`, `#/clientes`...) e busca os dados na `/api/` com `fetch`.

| Tela | O que faz |
|------|-----------|
| **Painel** | indicadores do período (agendamentos, faturamento recebido e previsto, ticket médio, taxa de faltas, pacotes ativos), gráficos de atendimentos e de faturamento por dia, atendimentos de hoje, serviços mais realizados, desempenho por profissional e formas de pagamento |
| **Agenda** | grade **diária** (uma coluna por profissional) e **semanal** (uma coluna por dia), com horários livres e ocupados; clicar num horário livre abre o formulário já preenchido |
| **Agendamento** | vários serviços, **simultâneos** ou **em sequência**, mostrando só horários livres; uso de **pacote**; total calculado na hora |
| **Detalhes** | mudança de status (confirmar, concluir, falta, cancelar), remarcação, **pagamentos** e mensagens de **WhatsApp** com o link `wa.me` e a simulação de resposta do cliente |
| **Clientes / Profissionais / Serviços** | cadastro com busca; CPF parcialmente oculto na lista (LGPD); desativar e reativar profissionais |
| **Pacotes** | venda com pagamento opcional, sessões usadas e restantes, pagamentos e cancelamento |
| **WhatsApp** | histórico de mensagens e botão para gerar os lembretes das próximas 24h |

```
salao/templates/index.html     estrutura da página, login, menu e regiões de aviso (aria-live)
salao/static/css/estilo.css    estilos com contrastes documentados
salao/static/js/
  app.js                       login, roteamento das telas e página de ajuda
  api.js                       cliente fetch da API e sessão
  ui.js                        diálogos acessíveis, avisos, erros de formulário, formatação
  componentes/crud.js          tela genérica de cadastro
  componentes/agendamento.js   formulário e detalhes do agendamento
  componentes/graficos.js      gráficos SVG acessíveis
  paginas/*.js                 dashboard, agenda, clientes, profissionais, servicos, pacotes, notificacoes
```

A acessibilidade (WCAG 2.2 AA) está documentada critério a critério em [`docs/ACESSIBILIDADE.md`](docs/ACESSIBILIDADE.md). A auditoria automática com axe-core encontrou 0 violações em todas as telas e diálogos.

## Andamento

- [x] Passo 1: script DDL do MySQL
- [x] Passo 2: estrutura base do Flask e Models
- [x] Passo 3: API REST (login + CRUD de Clientes, Profissionais e Serviços)
- [x] Passo 4: Agendamentos (disponibilidade), pagamentos, pacotes e WhatsApp em modo simulado
- [x] Passo 5: Front-end acessível (agenda, formulários e dashboard)

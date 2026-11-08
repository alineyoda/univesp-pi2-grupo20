# Sistema de Agendamentos para Salões de Beleza

Projeto Integrador II do Grupo 20 da Univesp. É um sistema web para microempresas de serviços estéticos gerenciarem clientes, profissionais, serviços, agendamentos, pagamentos e pacotes, com lembretes por WhatsApp.

**Stack:** Python (Flask, API REST), MySQL 8 e HTML, CSS e JavaScript puro, com acessibilidade WCAG 2.2. O deploy será feito no Render, com MySQL externo (TiDB Cloud ou Aiven).

## Banco de dados (Passo 1)

1. Abra o **MySQL Workbench** e conecte-se ao servidor local.
2. Use **File → Open SQL Script** para abrir [`database/schema.sql`](database/schema.sql) e execute o script inteiro (ícone ⚡).
3. Para ter dados de demonstração, abra e execute [`database/seed.sql`](database/seed.sql) do mesmo jeito.

O modelo de dados e as extensões ao MER original estão em [`docs/MER.md`](docs/MER.md).

## Andamento

- [x] Passo 1: script DDL do MySQL
- [ ] Passo 2: estrutura base do Flask e Models
- [ ] Passo 3: API REST (CRUD de Clientes, Profissionais e Serviços)
- [ ] Passo 4: Agendamentos (disponibilidade) e WhatsApp em modo simulado
- [ ] Passo 5: Front-end acessível (agenda, formulários e dashboard)

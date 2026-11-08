-- =====================================================================
--  Sistema de Agendamentos para Salões de Beleza - PI2 Univesp Grupo 20
--  Script DDL (MySQL 8.0+ / compatível com TiDB Cloud e Aiven MySQL)
-- ---------------------------------------------------------------------
--  Convenções:
--    * Tabelas do MER original: cliente, profissional, servico,
--      agendamento, item_agendamento, pagamento, pacote_cliente.
--    * Colunas/tabelas marcadas com [EXT] são EXTENSÕES ao MER original,
--      documentadas em docs/MER.md (login/LGPD, notificações e pacotes).
--    * Datas/horas são gravadas no horário local do salão
--      (America/Sao_Paulo) em colunas DATETIME.
--    * Valores monetários usam DECIMAL(10,2) (nunca FLOAT).
-- =====================================================================

-- Em ambiente local (MySQL Workbench) crie e selecione o banco.
-- Em bancos gerenciados (TiDB/Aiven) o banco pode já existir: nesse
-- caso, execute apenas a partir do "USE".
CREATE DATABASE IF NOT EXISTS salao_agenda
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE salao_agenda;

-- Recriação limpa (ordem inversa das dependências).
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS notificacao;
DROP TABLE IF EXISTS pagamento;
DROP TABLE IF EXISTS item_agendamento;
DROP TABLE IF EXISTS pacote_cliente;
DROP TABLE IF EXISTS agendamento;
DROP TABLE IF EXISTS servico;
DROP TABLE IF EXISTS profissional;
DROP TABLE IF EXISTS cliente;
DROP TABLE IF EXISTS usuario;
SET FOREIGN_KEY_CHECKS = 1;


-- ---------------------------------------------------------------------
-- [EXT] USUARIO - acesso ao sistema (autenticação / LGPD)
-- Os dados pessoais de clientes (CPF, telefone) só são acessíveis por
-- usuários autenticados. A senha é armazenada apenas como hash.
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id_usuario      INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nome            VARCHAR(120)  NOT NULL,
    email           VARCHAR(160)  NOT NULL,
    senha_hash      VARCHAR(255)  NOT NULL,
    perfil          ENUM('admin', 'atendente') NOT NULL DEFAULT 'atendente',
    ativo           BOOLEAN       NOT NULL DEFAULT TRUE,
    data_cadastro   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_usuario PRIMARY KEY (id_usuario),
    CONSTRAINT uq_usuario_email UNIQUE (email)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 1. CLIENTE
-- ---------------------------------------------------------------------
CREATE TABLE cliente (
    id_cliente      INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nome            VARCHAR(120)  NOT NULL,
    -- Formato E.164 sem o "+", ex.: 5511987654321 (exigido pelo WhatsApp)
    telefone        VARCHAR(20)   NOT NULL,
    -- Apenas dígitos. Opcional, mas único quando informado.
    cpf             CHAR(11)      NULL,
    data_cadastro   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_cliente PRIMARY KEY (id_cliente),
    CONSTRAINT uq_cliente_cpf UNIQUE (cpf),
    CONSTRAINT ck_cliente_cpf CHECK (cpf IS NULL OR cpf REGEXP '^[0-9]{11}$'),
    INDEX ix_cliente_nome (nome),
    INDEX ix_cliente_telefone (telefone)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 2. PROFISSIONAL
-- Exclusão lógica: profissionais são desativados (ativo = FALSE),
-- preservando o histórico de atendimentos.
-- ---------------------------------------------------------------------
CREATE TABLE profissional (
    id_profissional INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nome            VARCHAR(120)  NOT NULL,
    especialidade   VARCHAR(80)   NOT NULL,
    telefone        VARCHAR(20)   NULL,
    ativo           BOOLEAN       NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_profissional PRIMARY KEY (id_profissional),
    INDEX ix_profissional_ativo (ativo)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 3. SERVICO
-- ---------------------------------------------------------------------
CREATE TABLE servico (
    id_servico      INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    nome            VARCHAR(120)      NOT NULL,
    categoria       VARCHAR(60)       NOT NULL,
    duracao_minutos SMALLINT UNSIGNED NOT NULL,
    preco_base      DECIMAL(10, 2)    NOT NULL,
    CONSTRAINT pk_servico PRIMARY KEY (id_servico),
    CONSTRAINT uq_servico_nome UNIQUE (nome),
    CONSTRAINT ck_servico_duracao CHECK (duracao_minutos BETWEEN 5 AND 600),
    CONSTRAINT ck_servico_preco CHECK (preco_base >= 0),
    INDEX ix_servico_categoria (categoria)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 4. AGENDAMENTO (cabeçalho)
-- Um agendamento agrupa um ou mais itens (serviços), que podem ocorrer
-- em sequência ou simultaneamente com profissionais diferentes.
-- Exclusão de cliente com agendamentos é bloqueada (RESTRICT).
-- ---------------------------------------------------------------------
CREATE TABLE agendamento (
    id_agendamento  INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    cliente_id      INT UNSIGNED   NOT NULL,
    data_criacao    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valor_total     DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    status_geral    ENUM('agendado', 'confirmado', 'concluido', 'cancelado', 'falta')
                                   NOT NULL DEFAULT 'agendado',
    CONSTRAINT pk_agendamento PRIMARY KEY (id_agendamento),
    CONSTRAINT fk_agendamento_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente (id_cliente)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_agendamento_valor CHECK (valor_total >= 0),
    INDEX ix_agendamento_status (status_geral)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 7. PACOTE_CLIENTE (criada antes de item_agendamento por causa da FK)
-- [EXT] servico_id, valor_pacote, data_compra: vinculam o pacote ao
-- serviço coberto e registram seu valor de venda.
-- ---------------------------------------------------------------------
CREATE TABLE pacote_cliente (
    id_pacote_cliente  INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    cliente_id         INT UNSIGNED      NOT NULL,
    descricao          VARCHAR(160)      NOT NULL,
    qtd_sessoes_total  SMALLINT UNSIGNED NOT NULL,
    sessoes_realizadas SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    status_pacote      ENUM('ativo', 'concluido', 'cancelado') NOT NULL DEFAULT 'ativo',
    servico_id         INT UNSIGNED      NOT NULL,               -- [EXT]
    valor_pacote       DECIMAL(10, 2)    NOT NULL DEFAULT 0.00,  -- [EXT]
    data_compra        DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP, -- [EXT]
    CONSTRAINT pk_pacote_cliente PRIMARY KEY (id_pacote_cliente),
    CONSTRAINT fk_pacote_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente (id_cliente)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_pacote_servico FOREIGN KEY (servico_id)
        REFERENCES servico (id_servico)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_pacote_sessoes CHECK (qtd_sessoes_total > 0
                                        AND sessoes_realizadas <= qtd_sessoes_total),
    CONSTRAINT ck_pacote_valor CHECK (valor_pacote >= 0),
    INDEX ix_pacote_status (status_pacote)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 5. ITEM_AGENDAMENTO
-- Cada item = 1 serviço executado por 1 profissional em um intervalo.
-- O índice (profissional_id, data_hora_inicio, data_hora_fim) acelera a
-- verificação de conflito de horário feita pela API:
--   conflito  <=>  inicio_existente < novo_fim  AND  fim_existente > novo_inicio
-- [EXT] pacote_cliente_id: quando preenchido, o item consome 1 sessão
-- do pacote do cliente (subtotal = 0).
-- ---------------------------------------------------------------------
CREATE TABLE item_agendamento (
    id_item            INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    agendamento_id     INT UNSIGNED   NOT NULL,
    servico_id         INT UNSIGNED   NOT NULL,
    profissional_id    INT UNSIGNED   NOT NULL,
    data_hora_inicio   DATETIME       NOT NULL,
    data_hora_fim      DATETIME       NOT NULL,
    subtotal           DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    pacote_cliente_id  INT UNSIGNED   NULL,                      -- [EXT]
    CONSTRAINT pk_item_agendamento PRIMARY KEY (id_item),
    CONSTRAINT fk_item_agendamento FOREIGN KEY (agendamento_id)
        REFERENCES agendamento (id_agendamento)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_item_servico FOREIGN KEY (servico_id)
        REFERENCES servico (id_servico)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_item_profissional FOREIGN KEY (profissional_id)
        REFERENCES profissional (id_profissional)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_item_pacote FOREIGN KEY (pacote_cliente_id)
        REFERENCES pacote_cliente (id_pacote_cliente)
        ON DELETE SET NULL ON UPDATE CASCADE,
    -- Colunas sem FK com ação referencial podem ter CHECK no MySQL.
    CONSTRAINT ck_item_intervalo CHECK (data_hora_fim > data_hora_inicio),
    CONSTRAINT ck_item_subtotal CHECK (subtotal >= 0),
    INDEX ix_item_profissional_horario (profissional_id, data_hora_inicio, data_hora_fim),
    INDEX ix_item_inicio (data_hora_inicio)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 6. PAGAMENTO
-- [EXT] pacote_cliente_id: permite registrar o pagamento da compra de um
-- pacote. Cada pagamento referencia um agendamento OU um pacote.
-- (As FKs desta tabela não usam ações referenciais para permitir o
--  CHECK abaixo - restrição do MySQL; o comportamento padrão é RESTRICT.)
-- ---------------------------------------------------------------------
CREATE TABLE pagamento (
    id_pagamento      INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    agendamento_id    INT UNSIGNED   NULL,
    forma_pagamento   ENUM('dinheiro', 'pix', 'cartao_credito', 'cartao_debito')
                                     NOT NULL,
    valor_pago        DECIMAL(10, 2) NOT NULL,
    data_pagamento    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pacote_cliente_id INT UNSIGNED   NULL,                       -- [EXT]
    CONSTRAINT pk_pagamento PRIMARY KEY (id_pagamento),
    CONSTRAINT fk_pagamento_agendamento FOREIGN KEY (agendamento_id)
        REFERENCES agendamento (id_agendamento),
    CONSTRAINT fk_pagamento_pacote FOREIGN KEY (pacote_cliente_id)
        REFERENCES pacote_cliente (id_pacote_cliente),
    CONSTRAINT ck_pagamento_valor CHECK (valor_pago > 0),
    CONSTRAINT ck_pagamento_origem CHECK (
        (agendamento_id IS NOT NULL AND pacote_cliente_id IS NULL) OR
        (agendamento_id IS NULL AND pacote_cliente_id IS NOT NULL)
    ),
    INDEX ix_pagamento_data (data_pagamento)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- [EXT] NOTIFICACAO - histórico de mensagens de WhatsApp
-- Evita envios duplicados (1 confirmação e 1 lembrete por agendamento)
-- e registra a resposta do cliente. No modo simulado, status_envio =
-- 'simulado' e link_wa guarda o link https://wa.me/... gerado.
-- ---------------------------------------------------------------------
CREATE TABLE notificacao (
    id_notificacao   INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    agendamento_id   INT UNSIGNED  NOT NULL,
    tipo             ENUM('confirmacao', 'lembrete') NOT NULL,
    canal            VARCHAR(20)   NOT NULL DEFAULT 'whatsapp',
    telefone_destino VARCHAR(20)   NOT NULL,
    mensagem         TEXT          NOT NULL,
    link_wa          VARCHAR(1000) NULL,
    status_envio     ENUM('pendente', 'simulado', 'enviado', 'falha')
                                   NOT NULL DEFAULT 'pendente',
    data_envio       DATETIME      NULL,
    resposta_cliente ENUM('confirmou', 'cancelou') NULL,
    data_resposta    DATETIME      NULL,
    CONSTRAINT pk_notificacao PRIMARY KEY (id_notificacao),
    CONSTRAINT fk_notificacao_agendamento FOREIGN KEY (agendamento_id)
        REFERENCES agendamento (id_agendamento)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uq_notificacao_tipo UNIQUE (agendamento_id, tipo),
    INDEX ix_notificacao_status (status_envio)
) ENGINE = InnoDB;

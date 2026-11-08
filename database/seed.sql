-- =====================================================================
--  Dados de demonstração (para o vídeo de apresentação)
--  Execute APÓS o schema.sql. As datas são relativas a CURDATE(), então
--  a agenda sempre terá atendimentos "hoje" e nos próximos dias.
--  O usuário de login é criado pelo comando do Flask (Passo 2), pois a
--  senha precisa ser gravada como hash.
-- =====================================================================
USE salao_agenda;

INSERT INTO cliente (id_cliente, nome, telefone, cpf, data_cadastro) VALUES
 (1, 'Mariana Souza',      '5511987650001', '52998224725', NOW() - INTERVAL 60 DAY),
 (2, 'Juliana Ferreira',   '5511987650002', '11144477735', NOW() - INTERVAL 45 DAY),
 (3, 'Carla Mendes',       '5511987650003', NULL,          NOW() - INTERVAL 30 DAY),
 (4, 'Patrícia Oliveira',  '5511987650004', '39053344705', NOW() - INTERVAL 20 DAY),
 (5, 'Fernanda Lima',      '5511987650005', NULL,          NOW() - INTERVAL 5 DAY);

INSERT INTO profissional (id_profissional, nome, especialidade, telefone, ativo) VALUES
 (1, 'Ana Paula Rocha', 'Cabeleireira', '5511976540001', TRUE),
 (2, 'Beatriz Santos',  'Manicure e Pedicure', '5511976540002', TRUE),
 (3, 'Camila Duarte',   'Esteticista', '5511976540003', TRUE),
 (4, 'Débora Alves',    'Designer de Sobrancelhas', '5511976540004', FALSE);

INSERT INTO servico (id_servico, nome, categoria, duracao_minutos, preco_base) VALUES
 (1, 'Corte feminino',        'Cabelo',      60,  80.00),
 (2, 'Escova',                'Cabelo',      45,  60.00),
 (3, 'Coloração',             'Cabelo',     120, 180.00),
 (4, 'Manicure',              'Unhas',       40,  35.00),
 (5, 'Pedicure',              'Unhas',       50,  40.00),
 (6, 'Limpeza de pele',       'Estética',    90, 150.00),
 (7, 'Design de sobrancelha', 'Sobrancelha', 30,  45.00);

INSERT INTO pacote_cliente (id_pacote_cliente, cliente_id, descricao, qtd_sessoes_total,
                            sessoes_realizadas, status_pacote, servico_id, valor_pacote, data_compra) VALUES
 (1, 2, 'Pacote 5 limpezas de pele', 5, 1, 'ativo',     6, 600.00, NOW() - INTERVAL 40 DAY),
 (2, 1, 'Pacote 4 escovas',          4, 4, 'concluido', 2, 200.00, NOW() - INTERVAL 55 DAY);

-- Agendamentos ------------------------------------------------------------
INSERT INTO agendamento (id_agendamento, cliente_id, data_criacao, valor_total, status_geral) VALUES
 (1, 1, NOW() - INTERVAL 10 DAY, 115.00, 'concluido'),  -- passado, pago
 (2, 2, NOW() - INTERVAL 8 DAY,    0.00, 'concluido'),  -- passado, sessão de pacote
 (3, 4, NOW() - INTERVAL 6 DAY,   80.00, 'falta'),      -- passado, cliente faltou
 (4, 3, NOW() - INTERVAL 2 DAY,  115.00, 'confirmado'), -- HOJE: serviços simultâneos
 (5, 5, NOW() - INTERVAL 1 DAY,  240.00, 'agendado'),   -- HOJE: serviços em sequência
 (6, 1, NOW(),                     45.00, 'agendado');   -- AMANHÃ

INSERT INTO item_agendamento (agendamento_id, servico_id, profissional_id,
                              data_hora_inicio, data_hora_fim, subtotal, pacote_cliente_id) VALUES
 -- 1: corte + manicure (passado)
 (1, 1, 1, CURDATE() - INTERVAL 7 DAY + INTERVAL 600 MINUTE, CURDATE() - INTERVAL 7 DAY + INTERVAL 660 MINUTE, 80.00, NULL),
 (1, 4, 2, CURDATE() - INTERVAL 7 DAY + INTERVAL 660 MINUTE, CURDATE() - INTERVAL 7 DAY + INTERVAL 700 MINUTE, 35.00, NULL),
 -- 2: limpeza de pele usando o pacote 1 (passado)
 (2, 6, 3, CURDATE() - INTERVAL 5 DAY + INTERVAL 840 MINUTE, CURDATE() - INTERVAL 5 DAY + INTERVAL 930 MINUTE,  0.00, 1),
 -- 3: corte (falta)
 (3, 1, 1, CURDATE() - INTERVAL 3 DAY + INTERVAL 540 MINUTE, CURDATE() - INTERVAL 3 DAY + INTERVAL 600 MINUTE, 80.00, NULL),
 -- 4: HOJE 09:00 corte (Ana) e manicure (Beatriz) SIMULTÂNEOS
 (4, 1, 1, CURDATE() + INTERVAL 540 MINUTE, CURDATE() + INTERVAL 600 MINUTE, 80.00, NULL),
 (4, 4, 2, CURDATE() + INTERVAL 540 MINUTE, CURDATE() + INTERVAL 580 MINUTE, 35.00, NULL),
 -- 5: HOJE 14:00 coloração (Ana) e em SEQUÊNCIA escova (Ana)
 (5, 3, 1, CURDATE() + INTERVAL 840 MINUTE, CURDATE() + INTERVAL 960 MINUTE, 180.00, NULL),
 (5, 2, 1, CURDATE() + INTERVAL 960 MINUTE, CURDATE() + INTERVAL 1005 MINUTE, 60.00, NULL),
 -- 6: AMANHÃ 10:30 design de sobrancelha (Camila)
 (6, 7, 3, CURDATE() + INTERVAL 1 DAY + INTERVAL 630 MINUTE, CURDATE() + INTERVAL 1 DAY + INTERVAL 660 MINUTE, 45.00, NULL);

-- Pagamentos ---------------------------------------------------------------
INSERT INTO pagamento (agendamento_id, forma_pagamento, valor_pago, data_pagamento, pacote_cliente_id) VALUES
 (1,    'pix',            115.00, CURDATE() - INTERVAL 7 DAY + INTERVAL 705 MINUTE, NULL),
 (NULL, 'cartao_credito', 600.00, NOW() - INTERVAL 40 DAY, 1),  -- compra do pacote 1
 (NULL, 'dinheiro',       200.00, NOW() - INTERVAL 55 DAY, 2);  -- compra do pacote 2

-- Notificações (modo simulado) ----------------------------------------------
INSERT INTO notificacao (agendamento_id, tipo, telefone_destino, mensagem, link_wa,
                         status_envio, data_envio, resposta_cliente, data_resposta) VALUES
 (4, 'confirmacao', '5511987650003',
  'Olá, Carla! Seu horário no salão está agendado para hoje às 09:00. Responda SIM para confirmar.',
  'https://wa.me/5511987650003?text=Ol%C3%A1%2C%20Carla!%20Seu%20hor%C3%A1rio%20no%20sal%C3%A3o%20est%C3%A1%20agendado%20para%20hoje%20%C3%A0s%2009%3A00.%20Responda%20SIM%20para%20confirmar.',
  'simulado', NOW() - INTERVAL 1 DAY, 'confirmou', NOW() - INTERVAL 20 HOUR);

-- Ajusta os contadores AUTO_INCREMENT após inserções com id explícito.
ALTER TABLE cliente        AUTO_INCREMENT = 100;
ALTER TABLE profissional   AUTO_INCREMENT = 100;
ALTER TABLE servico        AUTO_INCREMENT = 100;
ALTER TABLE agendamento    AUTO_INCREMENT = 100;
ALTER TABLE pacote_cliente AUTO_INCREMENT = 100;

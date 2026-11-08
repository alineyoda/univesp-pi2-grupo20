# Acessibilidade (WCAG 2.2, nível AA)

Este documento mostra como o front-end do sistema atende às Diretrizes de Acessibilidade para Conteúdo Web (WCAG) 2.2 do W3C, no nível AA.

## Como foi verificado

- **Auditoria automática** com a ferramenta [axe-core](https://github.com/dequelabs/axe-core) 4.10, usando as regras WCAG 2.0, 2.1 e 2.2 nos níveis A e AA. O resultado foi **0 violações** em todas as telas: login, painel, agenda diária e semanal, clientes, profissionais, serviços, pacotes, WhatsApp e ajuda. Também passaram os diálogos de cadastro (inclusive com erros de validação), o de novo agendamento e o de detalhes do agendamento.
- **Teste de uso pelo teclado**, feito com o navegador controlado por script:
  - login feito só com o teclado;
  - setas, Home e End funcionando na grade da agenda;
  - Esc fecha o diálogo e o foco volta ao botão que o abriu.
- **Teste em tela de 320px de largura:** a página não precisa de rolagem horizontal.

## Critérios atendidos

| Critério | Nível | Como foi atendido |
|---|---|---|
| 1.1.1 Conteúdo não textual | A | Os ícones decorativos têm `aria-hidden`. Os gráficos são `<svg role="img">` com um resumo em texto (total e maior valor) e trazem a tabela de dados em "Ver dados em tabela". |
| 1.3.1 Informações e relações | A | O HTML é semântico: `header`, `nav`, `main` e `footer`. Os títulos seguem uma hierarquia, e as tabelas têm `caption` e `th scope`. Os formulários usam `label for`, `fieldset` e `legend`, e as listas de definições usam `dl`. A agenda é uma tabela com cabeçalhos de horário e de profissional ou dia. |
| 1.3.5 Identificar o propósito da entrada | AA | Os campos usam `autocomplete`: `name`, `tel-national`, `username` e `current-password`. |
| 1.4.1 Uso de cor | A | A situação do agendamento aparece sempre em texto ("Confirmado", "Falta"...). A página atual do menu é marcada por cor **e** sublinhado, e os campos com erro têm borda **e** mensagem com ícone. |
| 1.4.3 Contraste (mínimo) | AA | Texto principal com contraste de 16,4:1, texto secundário de 8,9:1 e botões primários de 9,9:1. Todas as etiquetas de status têm 7:1 ou mais. Os valores estão comentados em `estilo.css`. |
| 1.4.4 Redimensionar texto / 1.4.10 Refluxo | AA | As medidas usam `rem` e grades flexíveis. A 320px de largura (equivalente a zoom de 400%), o menu recolhe e as tabelas rolam dentro do próprio cartão. |
| 1.4.11 Contraste não textual | AA | As bordas dos campos têm 5,1:1, o indicador de foco tem 6,9:1 e as barras dos gráficos têm 6,3:1. |
| 1.4.13 Conteúdo em foco ou ao passar o mouse | AA | A dica dos gráficos não cobre o elemento apontado e some quando o mouse sai. A mesma informação está na tabela. |
| 2.1.1 Teclado / 2.1.2 Sem armadilha de teclado | A | Todas as funções funcionam pelo teclado. Os diálogos usam `<dialog>` nativo com `showModal()`, que prende o foco no diálogo enquanto ele está aberto, e o Esc o fecha. |
| 2.4.1 Pular blocos | A | O link "Pular para o conteúdo principal" é o primeiro elemento da página. |
| 2.4.2 Página com título | A | O `<title>` muda a cada tela, por exemplo "Agenda · Nome do salão". |
| 2.4.3 Ordem do foco | A | Ao trocar de tela, o foco vai para o `<h1>`. Ao abrir um diálogo, vai para o primeiro campo, e ao fechar, volta para o botão de origem. Na agenda, a grade ocupa uma única parada de Tab (*roving tabindex*) e as setas movem dentro dela. |
| 2.4.4 Finalidade do link | A | Botões repetidos têm nomes completos, como "Editar Maria Souza". O link "Abrir conversa no WhatsApp" avisa que abre em nova aba. |
| 2.4.6 Cabeçalhos e rótulos | AA | Cada seção tem um título, e cada campo tem um rótulo visível. |
| 2.4.7 Foco visível | AA | Contorno azul de 3px com afastamento de 2px em todos os elementos interativos. |
| **2.4.11 Foco não obscurecido** (novo na 2.2) | AA | `scroll-padding-top` impede que o topo fixo cubra o elemento com foco. |
| **2.5.7 Movimentos de arrastar** (novo na 2.2) | AA | A agenda não usa arrastar e soltar: tudo é feito com clique ou Enter. |
| **2.5.8 Tamanho do alvo (mínimo)** (novo na 2.2) | AA | Os botões e campos têm no mínimo 44 × 44px. O critério exige 24px. |
| 3.1.1 Idioma da página | A | `<html lang="pt-BR">`. |
| 3.2.3 Navegação consistente / 3.2.4 Identificação consistente | AA | O mesmo menu aparece em todas as telas. Clientes, Profissionais e Serviços usam o mesmo componente de cadastro (`crud.js`). |
| **3.2.6 Ajuda consistente** (novo na 2.2) | A | O link "Ajuda e atalhos de teclado" fica sempre no rodapé. |
| 3.3.1 Identificação do erro / 3.3.3 Sugestão de correção | A / AA | Quando há erro, aparece um resumo no topo do formulário (`role="alert"`) com links para cada campo. Cada campo recebe `aria-invalid` e uma mensagem ligada por `aria-describedby`, com exemplo de preenchimento (ex.: "(11) 98765-4321"). |
| 3.3.2 Rótulos ou instruções | A | Campos obrigatórios têm asterisco com explicação em texto, e os formatos aparecem como texto de ajuda. |
| **3.3.7 Entrada redundante** (novo na 2.2) | A | "Adicionar serviço no mesmo horário" e "em sequência" já preenchem data, hora e profissional. Ao clicar num horário livre da agenda, o formulário abre com data, hora e profissional preenchidos. |
| **3.3.8 Autenticação acessível (mínima)** (novo na 2.2) | AA | O login não tem quebra-cabeça nem CAPTCHA, aceita colar a senha e gerenciadores de senha, e tem o botão "Mostrar senha". |
| 4.1.2 Nome, função, valor | A | Os botões de alternância usam `aria-pressed`, o menu de celular usa `aria-expanded`, e os diálogos usam `aria-labelledby`. Elementos em carregamento recebem `aria-busy`. |
| 4.1.3 Mensagens de status | AA | Os avisos vão para regiões `aria-live`: `polite` para sucesso e `assertive` para erro. Com um diálogo aberto, o aviso é inserido **dentro** do diálogo, porque o resto da página fica inerte. O total do agendamento e o título da agenda também são anunciados. |

## Preferências do usuário

- `prefers-reduced-motion`: desliga animações e transições.
- `forced-colors` (alto contraste do Windows): mantém bordas e foco visíveis.
- `print`: esconde menu e botões ao imprimir a agenda.

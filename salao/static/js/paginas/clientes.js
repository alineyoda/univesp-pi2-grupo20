/** Tela de Clientes (CRUD). Exclusão bloqueada pela API se houver histórico. */
import { criarPaginaCrud } from "../componentes/crud.js";
import { abrirFormAgendamento } from "../componentes/agendamento.js";
import { cpfMascarado, dataCurta, esc, formatarCpf, formatarTelefone } from "../ui.js";

const pagina = criarPaginaCrud({
  recurso: "clientes",
  idCampo: "id_cliente",
  titulo: "Clientes",
  singular: "cliente",
  textoNovo: "Novo cliente",
  descricao: "Cadastro de clientes. Por privacidade (LGPD), o CPF aparece parcialmente oculto na lista.",
  dicaBusca: "Nome, telefone ou CPF",
  colunas: [
    { rotulo: "Nome", html: (r) => esc(r.nome) },
    { rotulo: "Telefone (WhatsApp)", html: (r) => esc(formatarTelefone(r.telefone)) },
    { rotulo: "CPF", html: (r) => `<span aria-label="CPF parcialmente oculto: final ${esc((r.cpf || "").slice(6, 9))}">${esc(cpfMascarado(r.cpf))}</span>` },
    { rotulo: "Cliente desde", html: (r) => esc(dataCurta(r.data_cadastro)) },
  ],
  campos: (r) => [
    { nome: "nome", rotulo: "Nome completo", valor: r?.nome, obrigatorio: true, autocomplete: "name" },
    { nome: "telefone", rotulo: "Telefone (WhatsApp)", tipo: "tel", valor: formatarTelefone(r?.telefone),
      obrigatorio: true, autocomplete: "tel-national", ajuda: "Com DDD. Ex.: (11) 98765-4321", atributos: `inputmode="tel"` },
    { nome: "cpf", rotulo: "CPF", valor: formatarCpf(r?.cpf), ajuda: "Opcional. Ex.: 123.456.789-09",
      atributos: `inputmode="numeric"` },
  ],
  acoesExtras: (r) => `
    <button type="button" class="botao botao--secundario botao--pequeno" data-acao="agendar" data-id="${r.id_cliente}"
      aria-label="Agendar para ${esc(r.nome)}">Agendar</button>
    <a class="botao botao--fantasma botao--pequeno" href="#/pacotes?cliente_id=${r.id_cliente}"
      aria-label="Pacotes de ${esc(r.nome)}">Pacotes</a>`,
  aoAcao: async (acao, r) => {
    if (acao === "agendar") abrirFormAgendamento({ cliente_id: r.id_cliente });
  },
  exclusao: {
    rotulo: "Excluir",
    mensagem: (r) => `Excluir o cliente “${r.nome}”? Clientes com agendamentos ou pacotes não podem ser excluídos.`,
  },
});

export const renderizar = pagina.renderizar;

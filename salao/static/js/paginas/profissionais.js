/** Tela de Profissionais (CRUD com exclusão lógica: desativar/reativar). */
import { patch } from "../api.js";
import { criarPaginaCrud } from "../componentes/crud.js";
import { anunciar, esc, etiqueta, formatarTelefone } from "../ui.js";

const pagina = criarPaginaCrud({
  recurso: "profissionais",
  idCampo: "id_profissional",
  titulo: "Profissionais",
  singular: "profissional",
  textoNovo: "Novo profissional",
  descricao: "Equipe do salão. Profissionais desativados deixam de aparecer na agenda, mas o histórico é mantido.",
  dicaBusca: "Nome ou especialidade",
  filtros: [{
    nome: "ativo", rotulo: "Situação",
    opcoes: [{ valor: "", rotulo: "Todos" }, { valor: "true", rotulo: "Ativos" }, { valor: "false", rotulo: "Inativos" }],
  }],
  colunas: [
    { rotulo: "Nome", html: (r) => esc(r.nome) },
    { rotulo: "Especialidade", html: (r) => esc(r.especialidade) },
    { rotulo: "Telefone", html: (r) => esc(formatarTelefone(r.telefone)) || "—" },
    { rotulo: "Situação", html: (r) => etiqueta(r.ativo ? "ativo" : "inativo") },
  ],
  campos: (r) => [
    { nome: "nome", rotulo: "Nome", valor: r?.nome, obrigatorio: true, autocomplete: "name" },
    { nome: "especialidade", rotulo: "Especialidade", valor: r?.especialidade, obrigatorio: true,
      ajuda: "Ex.: Cabeleireiro(a), Manicure, Esteticista" },
    { nome: "telefone", rotulo: "Telefone", tipo: "tel", valor: formatarTelefone(r?.telefone),
      autocomplete: "tel-national", ajuda: "Opcional, com DDD", atributos: `inputmode="tel"` },
  ],
  acoesExtras: (r) => r.ativo ? "" : `
    <button type="button" class="botao botao--secundario botao--pequeno" data-acao="reativar" data-id="${r.id_profissional}"
      aria-label="Reativar ${esc(r.nome)}">Reativar</button>`,
  aoAcao: async (acao, r, recarregar) => {
    if (acao !== "reativar") return;
    await patch(`/profissionais/${r.id_profissional}`, { ativo: true });
    anunciar(`${r.nome} foi reativado(a).`, "sucesso");
    await recarregar();
  },
  exclusao: {
    rotulo: "Desativar",
    visivel: (r) => r.ativo,
    mensagem: (r) => `Desativar “${r.nome}”? O histórico de atendimentos será mantido e é possível reativar depois.`,
  },
});

export const renderizar = pagina.renderizar;

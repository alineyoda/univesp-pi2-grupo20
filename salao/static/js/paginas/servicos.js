/** Tela de Serviços (CRUD). Exclusão bloqueada se o serviço já foi usado. */
import { criarPaginaCrud } from "../componentes/crud.js";
import { esc, moeda } from "../ui.js";

const pagina = criarPaginaCrud({
  recurso: "servicos",
  idCampo: "id_servico",
  titulo: "Serviços",
  singular: "serviço",
  textoNovo: "Novo serviço",
  descricao: "Catálogo de serviços com duração e preço base. A duração define o tempo reservado na agenda.",
  dicaBusca: "Nome do serviço",
  colunas: [
    { rotulo: "Serviço", html: (r) => esc(r.nome) },
    { rotulo: "Categoria", html: (r) => esc(r.categoria) },
    { rotulo: "Duração", html: (r) => `${r.duracao_minutos} min`, numero: true },
    { rotulo: "Preço base", html: (r) => esc(moeda(r.preco_base)), numero: true },
  ],
  campos: (r) => [
    { nome: "nome", rotulo: "Nome do serviço", valor: r?.nome, obrigatorio: true },
    { nome: "categoria", rotulo: "Categoria", valor: r?.categoria, obrigatorio: true,
      ajuda: "Ex.: Cabelo, Unhas, Estética" },
    { nome: "duracao_minutos", rotulo: "Duração (minutos)", tipo: "number", valor: r?.duracao_minutos ?? 60,
      obrigatorio: true, atributos: `min="5" max="600" step="5" inputmode="numeric"`, ajuda: "Entre 5 e 600 minutos" },
    { nome: "preco_base", rotulo: "Preço base (R$)", valor: r ? String(r.preco_base.toFixed(2)).replace(".", ",") : "",
      obrigatorio: true, atributos: `inputmode="decimal"`, ajuda: "Ex.: 80,00" },
  ],
  exclusao: {
    rotulo: "Excluir",
    mensagem: (r) => `Excluir o serviço “${r.nome}”? Serviços já usados em agendamentos ou pacotes não podem ser excluídos.`,
  },
});

export const renderizar = pagina.renderizar;

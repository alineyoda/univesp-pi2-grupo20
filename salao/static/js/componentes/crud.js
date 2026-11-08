/**
 * Tela genérica de cadastro (listagem + busca + formulário em diálogo).
 * Usada por Clientes, Profissionais e Serviços para manter a mesma
 * experiência (WCAG 3.2.4 - identificação consistente).
 *
 * cfg = {
 *   recurso: "clientes", idCampo: "id_cliente", titulo, descricao,
 *   singular: "cliente", textoNovo: "Novo cliente",
 *   colunas: [{ rotulo, html: (r) => "...", numero: false }],
 *   campos: (registro|null) => [configs de campoHTML],
 *   converter: (dados) => payload,          // opcional
 *   filtros: [{ nome, rotulo, opcoes }],    // selects extras de filtro
 *   acoesExtras: (r) => "<button data-acao=...>", aoAcao: async (acao, r, recarregar) => {},
 *   exclusao: { rotulo, mensagem: (r) => "...", visivel: (r) => true }
 * }
 */
import { api, del, ehAdmin, get, post } from "../api.js";
import {
  abrirDialogo, anunciar, campoHTML, comBotaoOcupado, confirmar, dadosDoFormulario,
  esc, limparErros, mostrarErros, novoId,
} from "../ui.js";

export function criarPaginaCrud(cfg) {
  return {
    async renderizar(container) {
      const idBusca = novoId("busca");
      container.innerHTML = `
        <div class="cabecalho-pagina">
          <div><h1>${esc(cfg.titulo)}</h1><p>${esc(cfg.descricao)}</p></div>
          <button type="button" class="botao botao--primario" data-novo>+ ${esc(cfg.textoNovo)}</button>
        </div>
        <section class="cartao" aria-label="Lista de ${esc(cfg.titulo.toLowerCase())}">
          <form class="barra-ferramentas" role="search" aria-label="Filtrar ${esc(cfg.titulo.toLowerCase())}">
            <div class="campo">
              <label for="${idBusca}">Buscar</label>
              <input id="${idBusca}" name="busca" type="search" autocomplete="off" placeholder="${esc(cfg.dicaBusca || "Nome")}">
            </div>
            ${(cfg.filtros || []).map((f) => campoHTML({ ...f })).join("")}
            <button type="submit" class="botao botao--secundario">Buscar</button>
          </form>
          <p role="status" class="campo__ajuda" data-contagem></p>
          <div class="tabela-container" data-tabela><p class="carregando">Carregando…</p></div>
        </section>`;

      const form = container.querySelector("form[role=search]");
      const areaTabela = container.querySelector("[data-tabela]");
      const contagem = container.querySelector("[data-contagem]");
      let registros = [];

      async function recarregar() {
        const filtros = dadosDoFormulario(form);
        registros = await get(`/${cfg.recurso}`, filtros);
        const n = registros.length;
        contagem.textContent = `${n} ${n === 1 ? cfg.singular : cfg.titulo.toLowerCase()} encontrado(s).`;
        if (!n) {
          areaTabela.innerHTML = `<p class="vazio">Nenhum registro encontrado.</p>`;
          return;
        }
        areaTabela.innerHTML = `
          <table>
            <caption class="visualmente-oculto">${esc(cfg.titulo)}: ${n} registro(s)</caption>
            <thead><tr>
              ${cfg.colunas.map((c) => `<th scope="col" class="${c.numero ? "numero" : ""}">${esc(c.rotulo)}</th>`).join("")}
              <th scope="col">Ações</th>
            </tr></thead>
            <tbody>
              ${registros.map((r) => `
                <tr class="${r.ativo === false ? "linha-inativa" : ""}">
                  ${cfg.colunas.map((c, i) => i === 0
                    ? `<th scope="row">${c.html(r)}</th>`
                    : `<td class="${c.numero ? "numero" : ""}">${c.html(r)}</td>`).join("")}
                  <td><div class="grupo-botoes">
                    <button type="button" class="botao botao--secundario botao--pequeno" data-acao="editar" data-id="${r[cfg.idCampo]}"
                      aria-label="Editar ${esc(r.nome)}">Editar</button>
                    ${cfg.acoesExtras ? cfg.acoesExtras(r) : ""}
                    ${ehAdmin() && (!cfg.exclusao.visivel || cfg.exclusao.visivel(r)) ? `
                      <button type="button" class="botao botao--fantasma botao--pequeno" data-acao="excluir" data-id="${r[cfg.idCampo]}"
                        aria-label="${esc(cfg.exclusao.rotulo)} ${esc(r.nome)}">${esc(cfg.exclusao.rotulo)}</button>` : ""}
                  </div></td>
                </tr>`).join("")}
            </tbody>
          </table>`;
      }

      function focarBotao(acao, id) {
        container.querySelector(`[data-acao="${acao}"][data-id="${id}"]`)?.focus();
      }

      function abrirFormulario(registro = null) {
        const titulo = registro ? `Editar ${cfg.singular}: ${registro.nome}` : cfg.textoNovo;
        const { dialogo, corpo, fechar } = abrirDialogo({
          titulo,
          conteudo: `
            <form novalidate>
              <p class="campo__ajuda">Campos com <span class="obrigatorio" aria-hidden="true">*</span><span class="visualmente-oculto">asterisco</span> são obrigatórios.</p>
              <div class="grade-form">${cfg.campos(registro).map(campoHTML).join("")}</div>
              <div class="grupo-botoes" style="justify-content:flex-end">
                <button type="button" class="botao botao--fantasma" data-fechar>Cancelar</button>
                <button type="submit" class="botao botao--primario">Salvar</button>
              </div>
            </form>`,
        });
        const formDialogo = corpo.querySelector("form");
        formDialogo.addEventListener("submit", async (e) => {
          e.preventDefault();
          limparErros(formDialogo);
          const dados = dadosDoFormulario(formDialogo);
          const payload = cfg.converter ? cfg.converter(dados) : dados;
          await comBotaoOcupado(formDialogo.querySelector("[type=submit]"), async () => {
            try {
              const salvo = registro
                ? await api(`/${cfg.recurso}/${registro[cfg.idCampo]}`, { metodo: "PUT", dados: payload })
                : await post(`/${cfg.recurso}`, payload);
              fechar("salvo");
              anunciar(`${cfg.singular[0].toUpperCase()}${cfg.singular.slice(1)} “${salvo.nome}” salvo(a) com sucesso.`, "sucesso");
              await recarregar();
              focarBotao("editar", salvo[cfg.idCampo]);
            } catch (erro) {
              mostrarErros(formDialogo, erro);
            }
          });
        });
        return dialogo;
      }

      // Eventos
      container.querySelector("[data-novo]").addEventListener("click", () => abrirFormulario());
      form.addEventListener("submit", (e) => { e.preventDefault(); recarregar(); });
      let atraso;
      form.addEventListener("input", () => { clearTimeout(atraso); atraso = setTimeout(recarregar, 400); });
      form.addEventListener("change", (e) => { if (e.target.tagName === "SELECT") recarregar(); });

      areaTabela.addEventListener("click", async (e) => {
        const botao = e.target.closest("button[data-acao]");
        if (!botao) return;
        const registro = registros.find((r) => String(r[cfg.idCampo]) === botao.dataset.id);
        const acao = botao.dataset.acao;
        try {
          if (acao === "editar") {
            abrirFormulario(registro);
          } else if (acao === "excluir") {
            const ok = await confirmar(cfg.exclusao.mensagem(registro),
              { titulo: `${cfg.exclusao.rotulo} ${cfg.singular}`, textoConfirmar: cfg.exclusao.rotulo, perigo: true });
            if (!ok) return;
            await del(`/${cfg.recurso}/${registro[cfg.idCampo]}`);
            anunciar(`${registro.nome}: ${cfg.exclusao.rotulo.toLowerCase()} concluído.`, "sucesso");
            await recarregar();
            container.querySelector("h1").focus();
          } else if (cfg.aoAcao) {
            await cfg.aoAcao(acao, registro, recarregar);
          }
        } catch (erro) {
          anunciar(erro.message, "erro");
        }
      });

      await recarregar();
    },
  };
}

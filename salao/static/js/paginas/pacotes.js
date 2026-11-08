/** Pacotes de serviços: venda, acompanhamento de sessões e pagamentos. */
import { del, ehAdmin, get, patch, post } from "../api.js";
import {
  abrirDialogo, anunciar, campoHTML, comBotaoOcupado, confirmar, dataCurta, dataHora, esc, etiqueta,
  limparErros, moeda, mostrarErros, novoId, ROTULOS_PAGAMENTO,
} from "../ui.js";

export async function renderizar(container, parametros) {
  const [clientes, servicos] = await Promise.all([get("/clientes"), get("/servicos")]);
  const ids = { cli: novoId("pc-cli"), st: novoId("pc-st") };
  container.innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>Pacotes</h1><p>Combos de várias sessões. Cada agendamento que usa o pacote consome uma sessão.</p></div>
      <button type="button" class="botao botao--primario" data-vender>+ Vender pacote</button>
    </div>
    <section class="cartao" aria-label="Lista de pacotes">
      <form class="barra-ferramentas" role="search" aria-label="Filtrar pacotes">
        <div class="campo"><label for="${ids.cli}">Cliente</label>
          <select id="${ids.cli}" name="cliente_id"><option value="">Todos</option>
            ${clientes.map((c) => `<option value="${c.id_cliente}" ${String(c.id_cliente) === parametros.cliente_id ? "selected" : ""}>${esc(c.nome)}</option>`).join("")}
          </select></div>
        <div class="campo"><label for="${ids.st}">Situação</label>
          <select id="${ids.st}" name="status"><option value="">Todas</option>
            <option value="ativo">Ativo</option><option value="concluido">Concluído</option><option value="cancelado">Cancelado</option>
          </select></div>
      </form>
      <p role="status" class="campo__ajuda" data-contagem></p>
      <div class="tabela-container" data-tabela></div>
    </section>`;

  const filtro = container.querySelector("form");
  const tabela = container.querySelector("[data-tabela]");

  async function recarregar() {
    const pacotes = await get("/pacotes", { cliente_id: filtro.cliente_id.value, status: filtro.status.value });
    container.querySelector("[data-contagem]").textContent = `${pacotes.length} pacote(s) encontrado(s).`;
    tabela.innerHTML = pacotes.length ? `
      <table>
        <caption class="visualmente-oculto">Pacotes: ${pacotes.length}</caption>
        <thead><tr><th scope="col">Pacote</th><th scope="col">Cliente</th><th scope="col">Sessões</th>
          <th scope="col" class="numero">Valor</th><th scope="col" class="numero">Saldo a pagar</th>
          <th scope="col">Situação</th><th scope="col">Ações</th></tr></thead>
        <tbody>${pacotes.map((p) => `<tr>
          <th scope="row">${esc(p.descricao)}<br><span class="campo__ajuda">${esc(p.servico_nome)} · desde ${esc(dataCurta(p.data_compra))}</span></th>
          <td>${esc(p.cliente_nome)}</td>
          <td>${p.sessoes_realizadas} de ${p.qtd_sessoes_total} usadas<br><span class="campo__ajuda">${p.sessoes_restantes} restante(s)</span></td>
          <td class="numero">${esc(moeda(p.valor_pacote))}</td>
          <td class="numero">${esc(moeda(p.saldo_devedor))}</td>
          <td>${etiqueta(p.status_pacote)}</td>
          <td><button type="button" class="botao botao--secundario botao--pequeno" data-detalhe="${p.id_pacote_cliente}"
            aria-label="Detalhes do ${esc(p.descricao)} de ${esc(p.cliente_nome)}">Detalhes</button></td>
        </tr>`).join("")}</tbody>
      </table>` : `<p class="vazio">Nenhum pacote encontrado.</p>`;
  }

  // ---------------- venda ----------------
  function abrirVenda() {
    const p = novoId("venda");
    const { corpo, fechar } = abrirDialogo({
      titulo: "Vender pacote",
      conteudo: `
        <form novalidate>
          <div class="grade-form">
            ${campoHTML({ nome: "cliente_id", rotulo: "Cliente", obrigatorio: true, valor: filtro.cliente_id.value,
              opcoes: [{ valor: "", rotulo: "Selecione" }, ...clientes.map((c) => ({ valor: c.id_cliente, rotulo: c.nome }))] })}
            ${campoHTML({ nome: "servico_id", rotulo: "Serviço do pacote", obrigatorio: true,
              opcoes: [{ valor: "", rotulo: "Selecione" }, ...servicos.map((s) => ({ valor: s.id_servico, rotulo: `${s.nome} (${moeda(s.preco_base)})` }))] })}
            ${campoHTML({ nome: "qtd_sessoes_total", rotulo: "Quantidade de sessões", tipo: "number", valor: 5, obrigatorio: true,
              atributos: `min="1" max="100" inputmode="numeric"` })}
            ${campoHTML({ nome: "valor_pacote", rotulo: "Valor do pacote (R$)", obrigatorio: true, atributos: `inputmode="decimal"`,
              ajuda: "Sugestão: 10% de desconto sobre o preço avulso.", id: `${p}-valor` })}
          </div>
          ${campoHTML({ nome: "descricao", rotulo: "Descrição", ajuda: "Opcional. Ex.: Pacote 5 escovas" })}
          <fieldset>
            <legend>Pagamento na compra (opcional)</legend>
            <div class="grade-form">
              ${campoHTML({ nome: "forma_pagamento", rotulo: "Forma de pagamento",
                opcoes: [{ valor: "", rotulo: "Não registrar agora" }, ...Object.entries(ROTULOS_PAGAMENTO).map(([v, r]) => ({ valor: v, rotulo: r }))] })}
              ${campoHTML({ nome: "valor_pago", rotulo: "Valor pago agora (R$)", atributos: `inputmode="decimal"`, ajuda: "Pode ser uma entrada (parcial)." })}
            </div>
          </fieldset>
          <div class="grupo-botoes" style="justify-content:flex-end">
            <button type="button" class="botao botao--fantasma" data-fechar>Cancelar</button>
            <button type="submit" class="botao botao--primario">Vender pacote</button>
          </div>
        </form>`,
    });
    const form = corpo.querySelector("form");
    let valorEditado = false;
    const sugerir = () => {
      const s = servicos.find((x) => String(x.id_servico) === form.servico_id.value);
      const qtd = Number(form.qtd_sessoes_total.value) || 0;
      if (s && qtd && !valorEditado) form.valor_pacote.value = (s.preco_base * qtd * 0.9).toFixed(2).replace(".", ",");
    };
    form.servico_id.addEventListener("change", sugerir);
    form.qtd_sessoes_total.addEventListener("input", sugerir);
    form.valor_pacote.addEventListener("input", () => { valorEditado = true; });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      limparErros(form);
      const dados = {
        cliente_id: form.cliente_id.value, servico_id: form.servico_id.value,
        qtd_sessoes_total: form.qtd_sessoes_total.value, valor_pacote: form.valor_pacote.value,
        descricao: form.descricao.value,
      };
      if (form.forma_pagamento.value && form.valor_pago.value) {
        dados.pagamento = { forma_pagamento: form.forma_pagamento.value, valor_pago: form.valor_pago.value };
      }
      await comBotaoOcupado(form.querySelector("[type=submit]"), async () => {
        try {
          const pacote = await post("/pacotes", dados);
          fechar("salvo");
          anunciar(`Pacote “${pacote.descricao}” vendido para ${pacote.cliente_nome}.`, "sucesso");
          await recarregar();
        } catch (erro) { mostrarErros(form, erro); }
      });
    });
  }

  // ---------------- detalhes ----------------
  async function abrirDetalhe(id) {
    const { corpo, titulo } = abrirDialogo({ titulo: `Pacote nº ${id}`, conteudo: `<p class="carregando">Carregando…</p>` });
    async function carregar(mensagem) {
      const p = await get(`/pacotes/${id}`);
      const idPg = novoId("pg");
      corpo.innerHTML = `
        <dl class="definicoes">
          <dt>Pacote</dt><dd>${esc(p.descricao)}</dd>
          <dt>Cliente</dt><dd>${esc(p.cliente_nome)}</dd>
          <dt>Serviço</dt><dd>${esc(p.servico_nome)}</dd>
          <dt>Situação</dt><dd>${etiqueta(p.status_pacote)}</dd>
          <dt>Sessões</dt><dd>${p.sessoes_realizadas} de ${p.qtd_sessoes_total} usadas (${p.sessoes_restantes} restantes)</dd>
          <dt>Valor</dt><dd>${esc(moeda(p.valor_pacote))} · pago ${esc(moeda(p.valor_pago))} · <strong>saldo ${esc(moeda(p.saldo_devedor))}</strong></dd>
        </dl>
        <h3>Sessões agendadas com este pacote</h3>
        ${p.sessoes.length ? `<ul class="lista-simples">${p.sessoes.map((s) => `<li>${esc(dataHora(s.data_hora_inicio))} com ${esc(s.profissional_nome)} ${etiqueta(s.status_geral)}</li>`).join("")}</ul>`
          : "<p>Nenhuma sessão usada ainda.</p>"}
        <h3>Pagamentos</h3>
        ${p.pagamentos.length ? `<ul class="lista-simples">${p.pagamentos.map((pg) => `<li>${esc(dataHora(pg.data_pagamento))} – ${esc(ROTULOS_PAGAMENTO[pg.forma_pagamento])}: <strong>${esc(moeda(pg.valor_pago))}</strong></li>`).join("")}</ul>`
          : "<p>Nenhum pagamento registrado.</p>"}
        ${p.saldo_devedor > 0 && p.status_pacote !== "cancelado" ? `
          <form class="cartao" data-pagamento novalidate aria-labelledby="${idPg}">
            <h4 id="${idPg}" style="margin-top:0">Registrar pagamento</h4>
            <div class="grade-form">
              ${campoHTML({ nome: "forma_pagamento", rotulo: "Forma de pagamento", opcoes: Object.entries(ROTULOS_PAGAMENTO).map(([v, r]) => ({ valor: v, rotulo: r })) })}
              ${campoHTML({ nome: "valor_pago", rotulo: "Valor (R$)", valor: p.saldo_devedor.toFixed(2).replace(".", ","), atributos: `inputmode="decimal"` })}
            </div>
            <button type="submit" class="botao botao--primario">Registrar pagamento</button>
          </form>` : ""}
        <div class="grupo-botoes">
          ${p.status_pacote === "ativo" ? `<button type="button" class="botao botao--perigo" data-cancelar-pacote>Cancelar pacote</button>` : ""}
          ${ehAdmin() && !p.sessoes.length && !p.pagamentos.length ? `<button type="button" class="botao botao--fantasma" data-excluir-pacote>Excluir pacote</button>` : ""}
        </div>`;

      const formPg = corpo.querySelector("[data-pagamento]");
      formPg?.addEventListener("submit", async (e) => {
        e.preventDefault();
        limparErros(formPg);
        await comBotaoOcupado(formPg.querySelector("[type=submit]"), async () => {
          try {
            await post("/pagamentos", { pacote_cliente_id: id, forma_pagamento: formPg.forma_pagamento.value, valor_pago: formPg.valor_pago.value });
            await carregar("Pagamento do pacote registrado.");
            recarregar();
          } catch (erro) { mostrarErros(formPg, erro); }
        });
      });
      corpo.querySelector("[data-cancelar-pacote]")?.addEventListener("click", async () => {
        if (!(await confirmar(`Cancelar o pacote “${p.descricao}”? As sessões restantes não poderão mais ser usadas.`, { perigo: true, textoConfirmar: "Cancelar pacote" }))) return;
        try { await patch(`/pacotes/${id}`, { status_pacote: "cancelado" }); await carregar("Pacote cancelado."); recarregar(); }
        catch (erro) { anunciar(erro.message, "erro"); }
      });
      corpo.querySelector("[data-excluir-pacote]")?.addEventListener("click", async () => {
        if (!(await confirmar("Excluir definitivamente este pacote?", { perigo: true, textoConfirmar: "Excluir" }))) return;
        try { await del(`/pacotes/${id}`); corpo.closest("dialog").close(); anunciar("Pacote excluído.", "sucesso"); recarregar(); }
        catch (erro) { anunciar(erro.message, "erro"); }
      });
      if (mensagem) { anunciar(mensagem, "sucesso"); titulo.focus(); }
    }
    try { await carregar(); } catch (e) { corpo.innerHTML = `<div class="alerta alerta--erro" role="alert">${esc(e.message)}</div>`; }
  }

  container.querySelector("[data-vender]").addEventListener("click", abrirVenda);
  filtro.addEventListener("change", recarregar);
  filtro.addEventListener("submit", (e) => { e.preventDefault(); recarregar(); });
  tabela.addEventListener("click", (e) => {
    const b = e.target.closest("[data-detalhe]");
    if (b) abrirDetalhe(Number(b.dataset.detalhe));
  });
  await recarregar();
}

/**
 * Formulário de agendamento (criar/editar) e diálogo de detalhes.
 *
 * Formulário:
 * - Vários serviços por agendamento. Botões para adicionar serviço
 *   SIMULTÂNEO (mesmo horário, outro profissional) ou em SEQUÊNCIA
 *   (começa quando o anterior termina) - evita digitar de novo (WCAG 3.3.7).
 * - O campo "Horário" só oferece horários livres (GET /api/disponibilidade).
 * - Pacotes disponíveis do cliente para o serviço aparecem em "Usar pacote".
 * - Total recalculado e anunciado (aria-live).
 *
 * Detalhes: status, serviços, pagamentos e mensagens de WhatsApp.
 * Toda alteração dispara o evento "agendamentos-alterados" para que a
 * agenda e o painel se atualizem.
 */
import { get, patch, post, put } from "../api.js";
import {
  abrirDialogo, anunciar, comBotaoOcupado, confirmar, dataHora, dataLonga, esc, etiqueta,
  formatarTelefone, hhmm, hojeISO, hora, limparErros, minutosDoDia, moeda, mostrarErros, novoId,
  ROTULOS_PAGAMENTO,
} from "../ui.js";

export function avisarAlteracao() {
  window.dispatchEvent(new CustomEvent("agendamentos-alterados"));
}

// =====================================================================
// FORMULÁRIO
// =====================================================================
export async function abrirFormAgendamento({ agendamento = null, cliente_id = "", data = "", hora: horaInicial = "",
  profissional_id = "" } = {}) {
  const [clientes, profissionais, servicos] = await Promise.all([
    get("/clientes"), get("/profissionais", { ativo: "true" }), get("/servicos"),
  ]);
  const servicoPorId = Object.fromEntries(servicos.map((s) => [String(s.id_servico), s]));
  const profPorId = Object.fromEntries(profissionais.map((p) => [String(p.id_profissional), p]));
  const editando = Boolean(agendamento);

  // Estado: um objeto por serviço
  const itens = editando
    ? agendamento.itens.map((i) => ({
        servico_id: String(i.servico_id), profissional_id: String(i.profissional_id),
        data: i.data_hora_inicio.slice(0, 10), hora: hora(i.data_hora_inicio),
        pacote_cliente_id: i.pacote_cliente_id ? String(i.pacote_cliente_id) : "",
        pacote_original: i.pacote_cliente_id ? String(i.pacote_cliente_id) : "",
      }))
    : [{ servico_id: "", profissional_id: String(profissional_id || ""), data: data || hojeISO(),
         hora: horaInicial, pacote_cliente_id: "" }];
  const idCliente = novoId("ag-cliente");
  const idTotal = novoId("ag-total");

  const { corpo, fechar } = abrirDialogo({
    titulo: editando ? `Remarcar agendamento nº ${agendamento.id_agendamento}` : "Novo agendamento",
    conteudo: `
      <form novalidate>
        <p class="campo__ajuda">Campos com <span class="obrigatorio" aria-hidden="true">*</span><span class="visualmente-oculto">asterisco</span> são obrigatórios.
          O campo Horário mostra apenas horários livres do profissional.</p>
        <div class="campo">
          <label for="${idCliente}">Cliente <span class="obrigatorio" aria-hidden="true">*</span></label>
          <select id="${idCliente}" name="cliente_id" data-campo="cliente_id" required aria-required="true"
            ${editando ? `disabled aria-describedby="${idCliente}-ajuda"` : ""}>
            <option value="">Selecione o cliente</option>
            ${clientes.map((c) => `<option value="${c.id_cliente}" ${String(c.id_cliente) === String(editando ? agendamento.cliente_id : cliente_id) ? "selected" : ""}>
              ${esc(c.nome)} – ${esc(formatarTelefone(c.telefone))}</option>`).join("")}
          </select>
          ${editando ? `<p class="campo__ajuda" id="${idCliente}-ajuda">O cliente não pode ser trocado na remarcação.</p>` : ""}
        </div>
        <div data-itens></div>
        <div class="grupo-botoes" style="margin-bottom:1rem">
          <button type="button" class="botao botao--secundario" data-adicionar="simultaneo">+ Adicionar serviço no mesmo horário</button>
          <button type="button" class="botao botao--secundario" data-adicionar="sequencia">+ Adicionar serviço em sequência</button>
        </div>
        <div class="resumo-total"><span id="${idTotal}">Valor total</span>
          <output aria-labelledby="${idTotal}" aria-live="polite" data-total>R$ 0,00</output></div>
        <div class="campo" style="flex-direction:row;align-items:center;gap:.6rem;margin-top:1rem">
          <input type="checkbox" id="${idCliente}-wa" name="enviar_confirmacao" checked>
          <label for="${idCliente}-wa">Gerar mensagem de confirmação por WhatsApp</label>
        </div>
        <div class="grupo-botoes" style="justify-content:flex-end">
          <button type="button" class="botao botao--fantasma" data-fechar>Cancelar</button>
          <button type="submit" class="botao botao--primario">${editando ? "Salvar remarcação" : "Salvar agendamento"}</button>
        </div>
      </form>`,
  });

  const form = corpo.querySelector("form");
  const areaItens = form.querySelector("[data-itens]");
  const selectCliente = form.querySelector(`#${idCliente}`);
  const cachePacotes = {};
  const requisicoes = {};

  // ---------------- renderização dos itens ----------------
  function htmlItem(item, i) {
    const p = `ag-item-${i}`;
    const opcoesServ = servicos.map((s) => `<option value="${s.id_servico}" ${String(s.id_servico) === item.servico_id ? "selected" : ""}>
      ${esc(s.nome)} – ${s.duracao_minutos} min – ${esc(moeda(s.preco_base))}</option>`).join("");
    const opcoesProf = profissionais.map((pr) => `<option value="${pr.id_profissional}" ${String(pr.id_profissional) === item.profissional_id ? "selected" : ""}>
      ${esc(pr.nome)} (${esc(pr.especialidade)})</option>`).join("");
    return `
      <fieldset class="item-servico" data-indice="${i}">
        <legend>Serviço ${i + 1} de ${itens.length}</legend>
        <div class="grade-form">
          <div class="campo">
            <label for="${p}-servico">Serviço <span class="obrigatorio" aria-hidden="true">*</span></label>
            <select id="${p}-servico" data-prop="servico_id" data-campo="itens[${i}].servico_id" required aria-required="true">
              <option value="">Selecione</option>${opcoesServ}</select>
          </div>
          <div class="campo">
            <label for="${p}-prof">Profissional <span class="obrigatorio" aria-hidden="true">*</span></label>
            <select id="${p}-prof" data-prop="profissional_id" data-campo="itens[${i}].profissional_id" required aria-required="true">
              <option value="">Selecione</option>${opcoesProf}</select>
          </div>
          <div class="campo">
            <label for="${p}-data">Data <span class="obrigatorio" aria-hidden="true">*</span></label>
            <input id="${p}-data" type="date" data-prop="data" value="${esc(item.data)}" min="${hojeISO()}" required aria-required="true">
          </div>
          <div class="campo">
            <label for="${p}-hora">Horário livre <span class="obrigatorio" aria-hidden="true">*</span></label>
            <select id="${p}-hora" data-prop="hora" data-campo="itens[${i}].data_hora_inicio" required aria-required="true"
              aria-describedby="${p}-resumo"><option value="">Escolha serviço, profissional e data</option></select>
          </div>
          <div class="campo">
            <label for="${p}-pacote">Usar pacote</label>
            <select id="${p}-pacote" data-prop="pacote_cliente_id" data-campo="itens[${i}].pacote_cliente_id">
              <option value="">Não usar pacote</option></select>
          </div>
        </div>
        <p class="campo__ajuda" id="${p}-resumo" data-resumo aria-live="polite"></p>
        ${itens.length > 1 ? `<div class="item-servico__acoes">
          <button type="button" class="botao botao--fantasma botao--pequeno" data-remover="${i}">Remover serviço ${i + 1}</button></div>` : ""}
      </fieldset>`;
  }

  function renderizarItens() {
    areaItens.innerHTML = itens.map(htmlItem).join("");
    itens.forEach((_, i) => { atualizarHorarios(i); atualizarPacotes(i); });
    atualizarTotal();
  }

  const fieldset = (i) => areaItens.querySelector(`fieldset[data-indice="${i}"]`);

  function fimDoItem(item) {
    const servico = servicoPorId[item.servico_id];
    if (!servico || !item.hora) return null;
    return hhmm(minutosDoDia(item.hora) + servico.duracao_minutos);
  }

  function atualizarResumo(i, aviso = "") {
    const item = itens[i];
    const servico = servicoPorId[item.servico_id];
    const fim = fimDoItem(item);
    const partes = [];
    if (servico && fim) partes.push(`Das ${item.hora} às ${fim} (${servico.duracao_minutos} min)`);
    if (servico) partes.push(item.pacote_cliente_id ? "Valor: R$ 0,00 (pacote)" : `Valor: ${moeda(servico.preco_base)}`);
    if (aviso) partes.push(aviso);
    const p = fieldset(i)?.querySelector("[data-resumo]");
    if (p) p.textContent = partes.join(" · ");
  }

  async function atualizarHorarios(i) {
    const item = itens[i];
    const select = fieldset(i)?.querySelector("[data-prop=hora]");
    if (!select) return;
    const servico = servicoPorId[item.servico_id];
    if (!servico || !item.profissional_id || !item.data) {
      select.innerHTML = `<option value="">Escolha serviço, profissional e data</option>`;
      atualizarResumo(i);
      return;
    }
    const pedido = (requisicoes[i] = (requisicoes[i] || 0) + 1);
    select.setAttribute("aria-busy", "true");
    select.innerHTML = `<option value="">Carregando horários…</option>`;
    try {
      const resp = await get("/disponibilidade", {
        profissional_id: item.profissional_id, servico_id: item.servico_id, data: item.data,
        ignorar_agendamento_id: editando ? agendamento.id_agendamento : "",
      });
      if (pedido !== requisicoes[i]) return; // resposta antiga
      const livres = resp.horarios;
      let aviso = "";
      if (item.hora && !livres.includes(item.hora)) {
        aviso = `Atenção: ${item.hora} não está livre para ${profPorId[item.profissional_id]?.nome || "este profissional"}. Escolha outro horário.`;
        item.hora = "";
      }
      select.innerHTML = livres.length
        ? `<option value="">Selecione (${livres.length} livres)</option>` +
          livres.map((h) => `<option value="${h}" ${h === item.hora ? "selected" : ""}>${h}</option>`).join("")
        : `<option value="">Nenhum horário livre nesta data</option>`;
      atualizarResumo(i, livres.length ? aviso : "Sem horários livres para este profissional nesta data.");
    } catch (e) {
      select.innerHTML = `<option value="">Erro ao carregar horários</option>`;
      atualizarResumo(i, e.message);
    } finally {
      select.removeAttribute("aria-busy");
    }
  }

  async function atualizarPacotes(i) {
    const item = itens[i];
    const select = fieldset(i)?.querySelector("[data-prop=pacote_cliente_id]");
    const cliente = editando ? agendamento.cliente_id : selectCliente.value;
    if (!select) return;
    if (!cliente || !item.servico_id) {
      select.innerHTML = `<option value="">Não usar pacote</option>`;
      item.pacote_cliente_id = item.pacote_original || "";
      return;
    }
    const chave = `${cliente}-${item.servico_id}`;
    cachePacotes[chave] ??= get("/pacotes", { cliente_id: cliente, servico_id: item.servico_id, disponiveis: "true" });
    const pacotes = await cachePacotes[chave];
    const opcoes = pacotes.map((p) => ({ id: String(p.id_pacote_cliente), rotulo: `${p.descricao} (${p.sessoes_restantes} sessão(ões) restante(s))` }));
    if (item.pacote_original && !opcoes.some((o) => o.id === item.pacote_original)) {
      opcoes.push({ id: item.pacote_original, rotulo: `Pacote nº ${item.pacote_original} (usado neste agendamento)` });
    }
    if (!opcoes.some((o) => o.id === item.pacote_cliente_id)) item.pacote_cliente_id = "";
    select.innerHTML = `<option value="">${opcoes.length ? "Não usar pacote" : "Nenhum pacote disponível"}</option>` +
      opcoes.map((o) => `<option value="${o.id}" ${o.id === item.pacote_cliente_id ? "selected" : ""}>${esc(o.rotulo)}</option>`).join("");
    atualizarResumo(i);
    atualizarTotal();
  }

  function atualizarTotal() {
    const total = itens.reduce((soma, item) => {
      const s = servicoPorId[item.servico_id];
      return soma + (s && !item.pacote_cliente_id ? s.preco_base : 0);
    }, 0);
    form.querySelector("[data-total]").textContent = `${moeda(total)} (${itens.length} serviço${itens.length > 1 ? "s" : ""})`;
  }

  // ---------------- eventos ----------------
  areaItens.addEventListener("change", (e) => {
    const campo = e.target.closest("[data-prop]");
    if (!campo) return;
    const i = Number(campo.closest("fieldset").dataset.indice);
    const prop = campo.dataset.prop;
    itens[i][prop] = campo.value;
    if (["servico_id", "profissional_id", "data"].includes(prop)) atualizarHorarios(i);
    if (prop === "servico_id") atualizarPacotes(i);
    atualizarResumo(i);
    atualizarTotal();
  });

  selectCliente.addEventListener("change", () => itens.forEach((_, i) => atualizarPacotes(i)));

  form.addEventListener("click", (e) => {
    const botaoAdd = e.target.closest("[data-adicionar]");
    const botaoRemover = e.target.closest("[data-remover]");
    if (botaoAdd) {
      const ultimo = itens[itens.length - 1];
      const novo = { servico_id: "", data: ultimo.data, pacote_cliente_id: "" };
      if (botaoAdd.dataset.adicionar === "simultaneo") {
        // mesmo horário, sugerindo um profissional ainda não usado
        const usados = new Set(itens.filter((it) => it.hora === ultimo.hora).map((it) => it.profissional_id));
        novo.hora = ultimo.hora;
        novo.profissional_id = String(profissionais.find((p) => !usados.has(String(p.id_profissional)))?.id_profissional || "");
      } else {
        novo.hora = fimDoItem(ultimo) || "";
        novo.profissional_id = ultimo.profissional_id;
      }
      itens.push(novo);
      renderizarItens();
      fieldset(itens.length - 1).querySelector("select").focus();
      anunciar(`Serviço ${itens.length} adicionado ${botaoAdd.dataset.adicionar === "simultaneo" ? "no mesmo horário" : "em sequência"}${novo.hora ? `, às ${novo.hora}` : ""}.`);
    } else if (botaoRemover) {
      const i = Number(botaoRemover.dataset.remover);
      itens.splice(i, 1);
      renderizarItens();
      form.querySelector("[data-adicionar]").focus();
      anunciar(`Serviço ${i + 1} removido. Restam ${itens.length}.`);
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    limparErros(form);
    // Validação no navegador (a API valida de novo)
    const campos = {};
    if (!editando && !selectCliente.value) campos.cliente_id = "Selecione o cliente.";
    itens.forEach((item, i) => {
      if (!item.servico_id) campos[`itens[${i}].servico_id`] = "Selecione o serviço.";
      if (!item.profissional_id) campos[`itens[${i}].profissional_id`] = "Selecione o profissional.";
      if (!item.hora) campos[`itens[${i}].data_hora_inicio`] = "Selecione um horário livre.";
    });
    if (Object.keys(campos).length) {
      const erro = new Error("Verifique os campos destacados.");
      erro.campos = campos;
      mostrarErros(form, erro);
      return;
    }
    const corpoRequisicao = {
      enviar_confirmacao: form.querySelector("[name=enviar_confirmacao]").checked,
      itens: itens.map((item) => ({
        servico_id: Number(item.servico_id), profissional_id: Number(item.profissional_id),
        data_hora_inicio: `${item.data}T${item.hora}`,
        pacote_cliente_id: item.pacote_cliente_id ? Number(item.pacote_cliente_id) : null,
      })),
    };
    await comBotaoOcupado(form.querySelector("[type=submit]"), async () => {
      try {
        const salvo = editando
          ? await put(`/agendamentos/${agendamento.id_agendamento}`, corpoRequisicao)
          : await post("/agendamentos", { ...corpoRequisicao, cliente_id: Number(selectCliente.value) });
        fechar("salvo");
        const wa = salvo.notificacoes?.length && corpoRequisicao.enviar_confirmacao ? " Mensagem de WhatsApp gerada." : "";
        anunciar(`Agendamento nº ${salvo.id_agendamento} salvo para ${dataHora(salvo.inicio)}. Total ${moeda(salvo.valor_total)}.${wa}`, "sucesso");
        avisarAlteracao();
      } catch (erro) {
        mostrarErros(form, erro);
      }
    });
  });

  renderizarItens();
}

// =====================================================================
// DETALHES
// =====================================================================
export async function abrirDetalheAgendamento(id) {
  const { corpo, titulo } = abrirDialogo({
    titulo: `Agendamento nº ${id}`,
    conteudo: `<p class="carregando" role="status">Carregando…</p>`,
  });

  async function carregar(mensagem) {
    try {
      const ag = await get(`/agendamentos/${id}`);
      corpo.innerHTML = htmlDetalhe(ag);
      ligarEventos(ag);
    } catch (e) {
      corpo.innerHTML = `<div class="alerta alerta--erro" role="alert">${esc(e.message)}</div>`;
    }
    if (mensagem) { anunciar(mensagem, "sucesso"); titulo.focus(); }
  }

  function htmlDetalhe(ag) {
    const ativo = ["agendado", "confirmado"].includes(ag.status_geral);
    const idsAcoes = novoId("acoes");
    return `
      <dl class="definicoes">
        <dt>Cliente</dt><dd>${esc(ag.cliente_nome)}</dd>
        <dt>Situação</dt><dd>${etiqueta(ag.status_geral)}</dd>
        <dt>Data</dt><dd>${ag.inicio ? esc(dataLonga(ag.inicio)) : "—"}</dd>
        <dt>Horário</dt><dd>${esc(hora(ag.inicio))} às ${esc(hora(ag.fim))}</dd>
        <dt>Valor total</dt><dd>${esc(moeda(ag.valor_total))}</dd>
        <dt>Pago</dt><dd>${esc(moeda(ag.valor_pago))}</dd>
        <dt>Saldo a pagar</dt><dd><strong>${esc(moeda(ag.saldo_devedor))}</strong></dd>
      </dl>

      <h3>Serviços</h3>
      <div class="tabela-container"><table>
        <caption class="visualmente-oculto">Serviços do agendamento</caption>
        <thead><tr><th scope="col">Horário</th><th scope="col">Serviço</th><th scope="col">Profissional</th><th scope="col" class="numero">Valor</th></tr></thead>
        <tbody>${ag.itens.map((i) => `<tr>
          <td>${esc(hora(i.data_hora_inicio))}–${esc(hora(i.data_hora_fim))}</td>
          <th scope="row">${esc(i.servico_nome)}</th><td>${esc(i.profissional_nome)}</td>
          <td class="numero">${i.pacote_cliente_id ? "Pacote (R$ 0,00)" : esc(moeda(i.subtotal))}</td></tr>`).join("")}
        </tbody></table></div>

      ${ativo ? `
      <h3 id="${idsAcoes}">Ações</h3>
      <div class="grupo-botoes" role="group" aria-labelledby="${idsAcoes}" style="margin-bottom:1rem">
        ${ag.status_geral === "agendado" ? `<button type="button" class="botao botao--primario" data-status="confirmado">Confirmar presença</button>` : ""}
        <button type="button" class="botao botao--secundario" data-status="concluido">Concluir atendimento</button>
        <button type="button" class="botao botao--secundario" data-status="falta">Registrar falta</button>
        <button type="button" class="botao botao--secundario" data-editar>Remarcar / editar</button>
        <button type="button" class="botao botao--perigo" data-status="cancelado">Cancelar agendamento</button>
      </div>` : ""}

      <h3>Pagamentos</h3>
      ${ag.pagamentos.length ? `<ul class="lista-simples">${ag.pagamentos.map((p) => `
        <li>${esc(dataHora(p.data_pagamento))} – ${esc(ROTULOS_PAGAMENTO[p.forma_pagamento])}: <strong>${esc(moeda(p.valor_pago))}</strong></li>`).join("")}</ul>`
        : `<p>Nenhum pagamento registrado.</p>`}
      ${ag.saldo_devedor > 0 && ag.status_geral !== "cancelado" ? formPagamentoHTML(ag.saldo_devedor) : ""}

      <h3>Mensagens de WhatsApp (modo simulado)</h3>
      ${ag.notificacoes.length ? ag.notificacoes.map((n) => `
        <article class="cartao" aria-label="Mensagem de ${n.tipo === "lembrete" ? "lembrete" : "confirmação"}">
          <p><strong>${n.tipo === "lembrete" ? "Lembrete" : "Confirmação"}</strong> ${etiqueta(n.status_envio)}
            · gerada em ${esc(dataHora(n.data_envio))}
            ${n.resposta_cliente ? ` · Cliente respondeu: <strong>${n.resposta_cliente === "confirmou" ? "SIM (confirmou)" : "NÃO (cancelou)"}</strong>` : ""}</p>
          <p class="mensagem-whatsapp">${esc(n.mensagem)}</p>
          <div class="grupo-botoes">
            <a class="botao botao--secundario botao--pequeno" href="${esc(n.link_wa)}" target="_blank" rel="noopener noreferrer">
              Abrir conversa no WhatsApp<span class="visualmente-oculto"> (abre em nova aba)</span></a>
            ${!n.resposta_cliente && ativo ? `
              <button type="button" class="botao botao--fantasma botao--pequeno" data-resposta="confirmou" data-notificacao="${n.id_notificacao}">Simular resposta SIM</button>
              <button type="button" class="botao botao--fantasma botao--pequeno" data-resposta="cancelou" data-notificacao="${n.id_notificacao}">Simular resposta NÃO</button>` : ""}
          </div>
        </article>`).join("") : `<p>Nenhuma mensagem gerada.</p>`}
      ${ativo ? `<div class="grupo-botoes">
        <button type="button" class="botao botao--secundario botao--pequeno" data-notificar="confirmacao">Gerar confirmação novamente</button>
        <button type="button" class="botao botao--secundario botao--pequeno" data-notificar="lembrete">Gerar lembrete agora</button></div>` : ""}`;
  }

  function formPagamentoHTML(saldo) {
    const p = novoId("pg");
    return `
      <form class="cartao" data-pagamento novalidate aria-labelledby="${p}-tit">
        <h4 id="${p}-tit" style="margin-top:0">Registrar pagamento</h4>
        <div class="grade-form">
          <div class="campo"><label for="${p}-forma">Forma de pagamento</label>
            <select id="${p}-forma" name="forma_pagamento" data-campo="forma_pagamento">
              ${Object.entries(ROTULOS_PAGAMENTO).map(([v, r]) => `<option value="${v}">${esc(r)}</option>`).join("")}
            </select></div>
          <div class="campo"><label for="${p}-valor">Valor (R$)</label>
            <input id="${p}-valor" name="valor_pago" data-campo="valor_pago" inputmode="decimal"
              value="${String(saldo.toFixed(2)).replace(".", ",")}" aria-describedby="${p}-ajuda">
            <p class="campo__ajuda" id="${p}-ajuda">Saldo a pagar: ${esc(moeda(saldo))}. Pagamento parcial é permitido.</p></div>
        </div>
        <button type="submit" class="botao botao--primario">Registrar pagamento</button>
      </form>`;
  }

  function ligarEventos(ag) {
    corpo.querySelectorAll("[data-status]").forEach((b) => b.addEventListener("click", async () => {
      const status = b.dataset.status;
      const textos = { cancelado: "Cancelar este agendamento? As sessões de pacote usadas serão devolvidas.",
        falta: "Registrar falta do cliente? Sessões de pacote serão consideradas usadas." };
      if (textos[status] && !(await confirmar(textos[status], { perigo: true, textoConfirmar: b.textContent.trim() }))) return;
      try {
        await patch(`/agendamentos/${id}/status`, { status });
        avisarAlteracao();
        await carregar(`Agendamento ${status === "concluido" ? "concluído" : status === "falta" ? "marcado como falta" : status}.`);
      } catch (e) { anunciar(e.message, "erro"); }
    }));

    corpo.querySelector("[data-editar]")?.addEventListener("click", async () => {
      corpo.closest("dialog").close();
      await abrirFormAgendamento({ agendamento: ag });
    });

    const formPg = corpo.querySelector("[data-pagamento]");
    formPg?.addEventListener("submit", async (e) => {
      e.preventDefault();
      limparErros(formPg);
      await comBotaoOcupado(formPg.querySelector("[type=submit]"), async () => {
        try {
          await post("/pagamentos", { agendamento_id: id, forma_pagamento: formPg.forma_pagamento.value,
            valor_pago: formPg.valor_pago.value });
          avisarAlteracao();
          await carregar("Pagamento registrado.");
        } catch (erro) { mostrarErros(formPg, erro); }
      });
    });

    corpo.querySelectorAll("[data-resposta]").forEach((b) => b.addEventListener("click", async () => {
      try {
        await post(`/notificacoes/${b.dataset.notificacao}/resposta`, { resposta: b.dataset.resposta });
        avisarAlteracao();
        await carregar(b.dataset.resposta === "confirmou" ? "Cliente confirmou: agendamento confirmado." : "Cliente recusou: agendamento cancelado.");
      } catch (e) { anunciar(e.message, "erro"); }
    }));

    corpo.querySelectorAll("[data-notificar]").forEach((b) => b.addEventListener("click", async () => {
      try {
        await post(`/agendamentos/${id}/notificar`, { tipo: b.dataset.notificar });
        await carregar("Mensagem de WhatsApp gerada.");
      } catch (e) { anunciar(e.message, "erro"); }
    }));
  }

  await carregar();
}

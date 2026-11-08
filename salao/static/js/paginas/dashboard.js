/**
 * Painel gerencial: volume de atendimentos e faturamento.
 * Dados de GET /api/dashboard; atendimentos do dia de GET /api/agenda.
 */
import { get, post } from "../api.js";
import { abrirDetalheAgendamento, abrirFormAgendamento } from "../componentes/agendamento.js";
import { barrasHorizontais, graficoBarras } from "../componentes/graficos.js";
import {
  anunciar, comBotaoOcupado, dataCurta, dataLonga, esc, etiqueta, hojeISO, hora, isoData, lerData,
  moeda, novoId, numero, percentual, ROTULOS_PAGAMENTO, ROTULOS_STATUS, somarDias,
} from "../ui.js";

function periodoPreset(preset) {
  const hoje = hojeISO();
  const d = lerData(hoje);
  switch (preset) {
    case "hoje": return [hoje, hoje];
    case "7dias": return [somarDias(hoje, -6), hoje];
    case "30dias": return [somarDias(hoje, -29), hoje];
    case "mes_anterior": {
      const inicio = new Date(d.getFullYear(), d.getMonth() - 1, 1, 12);
      const fim = new Date(d.getFullYear(), d.getMonth(), 0, 12);
      return [isoData(inicio), isoData(fim)];
    }
    default: return [isoData(new Date(d.getFullYear(), d.getMonth(), 1, 12)), hoje]; // mês atual
  }
}

export async function renderizar(container) {
  const ids = { preset: novoId("dash-preset"), ini: novoId("dash-ini"), fim: novoId("dash-fim") };
  container.innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>Painel gerencial</h1><p>Volume de atendimentos e faturamento do salão.</p></div>
      <div class="grupo-botoes">
        <button type="button" class="botao botao--secundario" data-lembretes>Gerar lembretes de WhatsApp (24h)</button>
        <button type="button" class="botao botao--primario" data-novo>+ Novo agendamento</button>
      </div>
    </div>
    <form class="cartao barra-ferramentas" aria-label="Período dos indicadores" data-filtro>
      <div class="campo"><label for="${ids.preset}">Período</label>
        <select id="${ids.preset}" name="preset">
          <option value="mes">Mês atual</option><option value="hoje">Hoje</option>
          <option value="7dias">Últimos 7 dias</option><option value="30dias">Últimos 30 dias</option>
          <option value="mes_anterior">Mês anterior</option><option value="personalizado">Personalizado</option>
        </select></div>
      <div class="campo"><label for="${ids.ini}">De</label><input type="date" id="${ids.ini}" name="inicio"></div>
      <div class="campo"><label for="${ids.fim}">Até</label><input type="date" id="${ids.fim}" name="fim"></div>
      <button type="submit" class="botao botao--secundario">Atualizar</button>
    </form>
    <div data-painel aria-live="off"><p class="carregando">Carregando indicadores…</p></div>`;

  const form = container.querySelector("[data-filtro]");
  const painel = container.querySelector("[data-painel]");
  const [ini, fim] = periodoPreset("mes");
  form.inicio.value = ini; form.fim.value = fim;

  async function carregar(anunciarResultado = false) {
    painel.setAttribute("aria-busy", "true");
    const [dash, agendaHoje] = await Promise.all([
      get("/dashboard", { inicio: form.inicio.value, fim: form.fim.value }),
      get("/agenda", { inicio: hojeISO(), fim: hojeISO() }),
    ]);
    painel.innerHTML = htmlPainel(dash, agendaHoje);
    const r = dash.resumo;
    const serie = dash.serie_diaria.map((d) => ({
      rotulo: dataCurta(d.data), rotuloCurto: d.data.slice(8, 10), atendimentos: d.atendimentos, recebido: d.recebido,
    }));
    painel.querySelector("[data-grafico-atend]").append(graficoBarras({
      titulo: "Atendimentos por dia", nomeValor: "Agendamentos", inteiro: true,
      descricao: "Agendamentos não cancelados, pela data do primeiro serviço.",
      dados: serie.map((d) => ({ ...d, valor: d.atendimentos })), formatar: (v) => numero(Math.round(v)),
    }));
    painel.querySelector("[data-grafico-receita]").append(graficoBarras({
      titulo: "Faturamento recebido por dia (R$)", nomeValor: "Recebido",
      descricao: "Pagamentos registrados (atendimentos e pacotes).",
      dados: serie.map((d) => ({ ...d, valor: d.recebido })), formatar: (v) => moeda(v),
      formatarEixo: (v) => new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 }).format(v),
    }));
    painel.removeAttribute("aria-busy");
    if (anunciarResultado) {
      anunciar(`Indicadores atualizados: ${r.agendamentos} agendamentos e ${moeda(r.faturamento_recebido)} recebidos no período.`);
    }
  }

  function htmlPainel(dash, agendaHoje) {
    const r = dash.resumo;
    const indicador = (rotulo, valor, detalhe) => `
      <li class="indicador"><p class="indicador__rotulo">${esc(rotulo)}</p>
        <p class="indicador__valor">${esc(valor)}</p><p class="indicador__detalhe">${esc(detalhe)}</p></li>`;
    const proximos = agendaHoje.itens;
    return `
      <h2 class="visualmente-oculto">Resumo de ${esc(dataCurta(dash.periodo.inicio))} a ${esc(dataCurta(dash.periodo.fim))}</h2>
      <ul class="indicadores">
        ${indicador("Agendamentos no período", numero(r.agendamentos), `${r.concluidos} concluídos · ${r.pendentes} a realizar`)}
        ${indicador("Faturamento recebido", moeda(r.faturamento_recebido), `${moeda(r.faturamento_pacotes)} em venda de pacotes`)}
        ${indicador("Faturamento previsto", moeda(r.faturamento_previsto), "Valor dos agendamentos não cancelados")}
        ${indicador("Ticket médio", moeda(r.ticket_medio), "Por atendimento concluído")}
        ${indicador("Taxa de faltas", percentual(r.taxa_faltas), `${r.faltas} falta(s) · ${r.cancelados} cancelamento(s)`)}
        ${indicador("Pacotes ativos", numero(r.pacotes_ativos), `${r.sessoes_restantes} sessão(ões) a realizar`)}
      </ul>

      <div class="grade-2 secao-dashboard">
        <section class="cartao" data-grafico-atend aria-label="Gráfico de atendimentos por dia"></section>
        <section class="cartao" data-grafico-receita aria-label="Gráfico de faturamento por dia"></section>
      </div>

      <div class="grade-2 secao-dashboard">
        <section class="cartao" aria-labelledby="dash-hoje">
          <h2 id="dash-hoje">Atendimentos de hoje</h2>
          <p class="campo__ajuda">${esc(dataLonga(hojeISO()))}</p>
          ${proximos.length ? `<ul class="lista-simples">${proximos.map((i) => `
            <li><button type="button" class="botao botao--fantasma" style="width:100%;justify-content:space-between;text-align:left"
                data-agendamento="${i.agendamento_id}">
              <span><strong>${esc(hora(i.data_hora_inicio))}</strong> ${esc(i.servico_nome)} – ${esc(i.cliente_nome)}
                <span class="campo__ajuda">com ${esc(i.profissional_nome)}</span></span>
              ${etiqueta(i.status_geral)}</button></li>`).join("")}</ul>`
            : `<p class="vazio">Nenhum atendimento hoje.</p>`}
        </section>

        <section class="cartao" aria-labelledby="dash-servicos">
          <h2 id="dash-servicos">Serviços mais realizados</h2>
          ${dash.top_servicos.length ? barrasHorizontais(dash.top_servicos.map((s) => ({
            rotulo: s.servico, valor: s.quantidade, extra: moeda(s.valor) })),
            { formatar: (v) => `${v}×`, rotuloLista: "Serviços mais realizados com quantidade e valor" })
            : `<p class="vazio">Sem atendimentos no período.</p>`}
        </section>
      </div>

      <div class="grade-2 secao-dashboard">
        <section class="cartao" aria-labelledby="dash-prof">
          <h2 id="dash-prof">Desempenho por profissional</h2>
          <div class="tabela-container"><table>
            <caption class="visualmente-oculto">Atendimentos, horas e valor por profissional</caption>
            <thead><tr><th scope="col">Profissional</th><th scope="col" class="numero">Atendimentos</th>
              <th scope="col" class="numero">Horas</th><th scope="col" class="numero">Valor</th></tr></thead>
            <tbody>${dash.por_profissional.map((p) => `<tr><th scope="row">${esc(p.profissional)}</th>
              <td class="numero">${p.quantidade}</td><td class="numero">${(p.minutos / 60).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}</td>
              <td class="numero">${esc(moeda(p.valor))}</td></tr>`).join("") || `<tr><td colspan="4">Sem dados.</td></tr>`}</tbody>
          </table></div>
        </section>

        <section class="cartao" aria-labelledby="dash-status">
          <h2 id="dash-status">Situação dos agendamentos e pagamentos</h2>
          <div class="tabela-container"><table>
            <caption class="visualmente-oculto">Quantidade e valor por situação</caption>
            <thead><tr><th scope="col">Situação</th><th scope="col" class="numero">Qtd.</th><th scope="col" class="numero">Valor</th></tr></thead>
            <tbody>${Object.entries(dash.por_status).map(([s, v]) => `<tr><th scope="row">${esc(ROTULOS_STATUS[s])}</th>
              <td class="numero">${v.quantidade}</td><td class="numero">${esc(moeda(v.valor))}</td></tr>`).join("")}</tbody>
          </table></div>
          <h3 style="margin-top:1rem">Recebido por forma de pagamento</h3>
          ${dash.por_forma_pagamento.length ? barrasHorizontais(dash.por_forma_pagamento.map((f) => ({
            rotulo: ROTULOS_PAGAMENTO[f.forma_pagamento], valor: f.valor, extra: `${f.quantidade} pagamento(s)` })),
            { formatar: moeda, rotuloLista: "Valor recebido por forma de pagamento" })
            : `<p class="vazio">Nenhum pagamento no período.</p>`}
        </section>
      </div>`;
  }

  // ---------------- eventos ----------------
  form.preset.addEventListener("change", () => {
    if (form.preset.value === "personalizado") { form.inicio.focus(); return; }
    const [i, f] = periodoPreset(form.preset.value);
    form.inicio.value = i; form.fim.value = f;
    carregar(true).catch((e) => anunciar(e.message, "erro"));
  });
  form.addEventListener("input", (e) => { if (e.target.type === "date") form.preset.value = "personalizado"; });
  form.addEventListener("submit", (e) => { e.preventDefault(); carregar(true).catch((err) => anunciar(err.message, "erro")); });

  painel.addEventListener("click", (e) => {
    const b = e.target.closest("[data-agendamento]");
    if (b) abrirDetalheAgendamento(Number(b.dataset.agendamento));
  });
  container.querySelector("[data-novo]").addEventListener("click", () => abrirFormAgendamento());
  container.querySelector("[data-lembretes]").addEventListener("click", async (e) => {
    await comBotaoOcupado(e.currentTarget, async () => {
      try {
        const r = await post("/tarefas/lembretes");
        anunciar(r.quantidade
          ? `${r.quantidade} lembrete(s) gerado(s) para as próximas ${r.janela_horas}h. Veja em WhatsApp.`
          : "Nenhum lembrete novo: todos os agendamentos das próximas 24h já foram avisados.", "sucesso");
      } catch (erro) { anunciar(erro.message, "erro"); }
    }, "Gerando…");
  });

  const aoAlterar = () => { if (document.contains(painel)) carregar(); };
  window.addEventListener("agendamentos-alterados", aoAlterar);
  window.addEventListener("hashchange", () => window.removeEventListener("agendamentos-alterados", aoAlterar), { once: true });

  await carregar();
}

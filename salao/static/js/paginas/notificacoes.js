/** Histórico de mensagens de WhatsApp (modo simulado) e rotina de lembretes. */
import { get, post } from "../api.js";
import { abrirDetalheAgendamento, avisarAlteracao } from "../componentes/agendamento.js";
import { anunciar, comBotaoOcupado, dataHora, esc, etiqueta, formatarTelefone, novoId } from "../ui.js";

export async function renderizar(container) {
  const ids = { tipo: novoId("nt-tipo") };
  container.innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>WhatsApp</h1>
        <p>Mensagens de confirmação e lembrete. No modo simulado a mensagem não é enviada de verdade:
          use “Abrir conversa” para enviá-la pelo WhatsApp e simule a resposta do cliente.</p></div>
      <button type="button" class="botao botao--primario" data-lembretes>Gerar lembretes das próximas 24h</button>
    </div>
    <div class="alerta alerta--info">
      Em produção, a rotina de lembretes é executada automaticamente a cada 15 minutos por um agendador externo (cron).
    </div>
    <section class="cartao" aria-label="Histórico de mensagens">
      <form class="barra-ferramentas" aria-label="Filtrar mensagens">
        <div class="campo"><label for="${ids.tipo}">Tipo</label>
          <select id="${ids.tipo}" name="tipo"><option value="">Todos</option>
            <option value="confirmacao">Confirmação</option><option value="lembrete">Lembrete</option></select></div>
      </form>
      <p role="status" class="campo__ajuda" data-contagem></p>
      <div data-lista></div>
    </section>`;

  const lista = container.querySelector("[data-lista]");
  const filtro = container.querySelector("form");

  async function recarregar() {
    const msgs = await get("/notificacoes", { tipo: filtro.tipo.value });
    container.querySelector("[data-contagem]").textContent = `${msgs.length} mensagem(ns).`;
    lista.innerHTML = msgs.length ? `
      <div class="tabela-container"><table>
        <caption class="visualmente-oculto">Mensagens de WhatsApp</caption>
        <thead><tr><th scope="col">Cliente</th><th scope="col">Tipo</th><th scope="col">Atendimento</th>
          <th scope="col">Envio</th><th scope="col">Resposta</th><th scope="col">Mensagem e ações</th></tr></thead>
        <tbody>${msgs.map((n) => `<tr>
          <th scope="row">${esc(n.cliente_nome)}<br><span class="campo__ajuda">${esc(formatarTelefone(n.telefone_destino))}</span></th>
          <td>${n.tipo === "lembrete" ? "Lembrete" : "Confirmação"}</td>
          <td>${esc(dataHora(n.agendamento_inicio))}<br>${etiqueta(n.status_geral)}</td>
          <td>${etiqueta(n.status_envio)}<br><span class="campo__ajuda">${esc(dataHora(n.data_envio))}</span></td>
          <td>${n.resposta_cliente ? (n.resposta_cliente === "confirmou" ? "SIM – confirmou" : "NÃO – cancelou") : "Aguardando"}</td>
          <td>
            <details><summary>Ver mensagem</summary><p class="mensagem-whatsapp">${esc(n.mensagem)}</p></details>
            <div class="grupo-botoes">
              <a class="botao botao--secundario botao--pequeno" href="${esc(n.link_wa)}" target="_blank" rel="noopener noreferrer">
                Abrir conversa<span class="visualmente-oculto"> com ${esc(n.cliente_nome)} no WhatsApp (abre em nova aba)</span></a>
              <button type="button" class="botao botao--fantasma botao--pequeno" data-agendamento="${n.agendamento_id}"
                aria-label="Ver agendamento de ${esc(n.cliente_nome)}">Agendamento</button>
              ${!n.resposta_cliente && ["agendado", "confirmado"].includes(n.status_geral) ? `
                <button type="button" class="botao botao--fantasma botao--pequeno" data-resposta="confirmou" data-id="${n.id_notificacao}"
                  aria-label="Simular resposta SIM de ${esc(n.cliente_nome)}">Simular SIM</button>
                <button type="button" class="botao botao--fantasma botao--pequeno" data-resposta="cancelou" data-id="${n.id_notificacao}"
                  aria-label="Simular resposta NÃO de ${esc(n.cliente_nome)}">Simular NÃO</button>` : ""}
            </div>
          </td></tr>`).join("")}</tbody>
      </table></div>` : `<p class="vazio">Nenhuma mensagem gerada ainda.</p>`;
  }

  container.querySelector("[data-lembretes]").addEventListener("click", async (e) => {
    await comBotaoOcupado(e.currentTarget, async () => {
      try {
        const r = await post("/tarefas/lembretes");
        anunciar(r.quantidade ? `${r.quantidade} lembrete(s) gerado(s).` : "Nenhum lembrete novo para as próximas 24h.", "sucesso");
        await recarregar();
      } catch (erro) { anunciar(erro.message, "erro"); }
    }, "Gerando…");
  });
  filtro.addEventListener("change", recarregar);
  lista.addEventListener("click", async (e) => {
    const ag = e.target.closest("[data-agendamento]");
    const resp = e.target.closest("[data-resposta]");
    if (ag) abrirDetalheAgendamento(Number(ag.dataset.agendamento));
    if (resp) {
      try {
        await post(`/notificacoes/${resp.dataset.id}/resposta`, { resposta: resp.dataset.resposta });
        anunciar(resp.dataset.resposta === "confirmou" ? "Resposta SIM registrada: agendamento confirmado." : "Resposta NÃO registrada: agendamento cancelado.", "sucesso");
        avisarAlteracao();
        await recarregar();
        container.querySelector("h1").focus();
      } catch (erro) { anunciar(erro.message, "erro"); }
    }
  });
  const aoAlterar = () => { if (document.contains(lista)) recarregar(); };
  window.addEventListener("agendamentos-alterados", aoAlterar);
  window.addEventListener("hashchange", () => window.removeEventListener("agendamentos-alterados", aoAlterar), { once: true });
  await recarregar();
}

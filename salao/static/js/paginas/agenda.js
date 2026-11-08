/**
 * Agenda interativa - visão DIÁRIA (colunas = profissionais) e SEMANAL
 * (colunas = dias, para um profissional).
 *
 * Acessibilidade:
 * - Grade em <table> com cabeçalhos de linha (horário) e de coluna, para
 *   que leitores de tela anunciem "09:30, Ana Paula" ao navegar.
 * - "Roving tabindex": a grade ocupa UMA parada de Tab; dentro dela as
 *   setas, Home e End movem entre os horários (padrão ARIA de grade).
 * - Cada horário é um botão com nome completo: livre ("Livre, 09:30,
 *   Ana Paula, criar agendamento") ou ocupado (horário, serviço,
 *   cliente e situação em TEXTO, não só cor).
 * - Sem arrastar e soltar (WCAG 2.5.7): tudo por clique/Enter.
 */
import { get } from "../api.js";
import { abrirDetalheAgendamento, abrirFormAgendamento } from "../componentes/agendamento.js";
import {
  dataLonga, esc, hhmm, hojeISO, hora, isoData, lerData, minutosDoDia, novoId, ROTULOS_STATUS, somarDias,
} from "../ui.js";

const PASSO = 30; // minutos por linha da grade
const NOMES_DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

const estado = { modo: "dia", data: hojeISO(), profissional: "" };

function segundaDaSemana(iso) {
  const d = lerData(iso);
  const diaSemana = (d.getDay() + 6) % 7; // 0 = segunda
  d.setDate(d.getDate() - diaSemana);
  return isoData(d);
}

export async function renderizar(container, parametros) {
  if (parametros.data) estado.data = parametros.data;
  const ids = { data: novoId("ag-data"), prof: novoId("ag-prof"), instr: novoId("ag-instr"), titulo: novoId("ag-tit") };

  container.innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>Agenda</h1><p>Horários ocupados e livres. Escolha um horário livre para agendar.</p></div>
      <button type="button" class="botao botao--primario" data-novo>+ Novo agendamento</button>
    </div>
    <section class="cartao" aria-labelledby="${ids.titulo}">
      <div class="agenda-controles">
        <div class="grupo-botoes" role="group" aria-label="Modo de visualização">
          <button type="button" class="botao botao--fantasma" data-modo="dia" aria-pressed="false">Dia</button>
          <button type="button" class="botao botao--fantasma" data-modo="semana" aria-pressed="false">Semana</button>
        </div>
        <div class="grupo-botoes" role="group" aria-label="Navegar no calendário">
          <button type="button" class="botao botao--fantasma" data-navegar="-1"><span aria-hidden="true">◀</span> <span data-rotulo-anterior>Dia anterior</span></button>
          <button type="button" class="botao botao--fantasma" data-navegar="0">Hoje</button>
          <button type="button" class="botao botao--fantasma" data-navegar="1"><span data-rotulo-proximo>Próximo dia</span> <span aria-hidden="true">▶</span></button>
        </div>
        <div class="campo"><label for="${ids.data}">Ir para a data</label>
          <input type="date" id="${ids.data}" value="${estado.data}"></div>
        <div class="campo"><label for="${ids.prof}">Profissional</label>
          <select id="${ids.prof}"></select></div>
      </div>

      <h2 class="agenda-titulo" id="${ids.titulo}" aria-live="polite"></h2>
      <ul class="legenda" aria-label="Legenda das situações">
        ${["agendado", "confirmado", "concluido", "falta"].map((s) => `<li><span class="etiqueta st-${s}">${ROTULOS_STATUS[s]}</span></li>`).join("")}
        <li><span class="etiqueta" style="border-style:dashed">Livre</span></li>
        <li><span class="etiqueta" style="background:#ecebee">Indisponível (passado)</span></li>
      </ul>
      <p id="${ids.instr}" class="campo__ajuda">Dica de teclado: use Tab para entrar na grade e as setas para mudar de horário; Enter abre o horário.</p>
      <div data-grade><p class="carregando">Carregando agenda…</p></div>
    </section>`;

  const el = {
    grade: container.querySelector("[data-grade]"),
    titulo: container.querySelector(`#${ids.titulo}`),
    data: container.querySelector(`#${ids.data}`),
    prof: container.querySelector(`#${ids.prof}`),
  };
  let ultimaChaveFocada = null;

  // -------------------------------------------------------------- carga
  async function carregar() {
    const inicio = estado.modo === "dia" ? estado.data : segundaDaSemana(estado.data);
    const fim = estado.modo === "dia" ? estado.data : somarDias(inicio, 6);
    const dados = await get("/agenda", { inicio, fim });

    // Seletor de profissional (na semana é obrigatório escolher um)
    if (estado.modo === "semana" && !estado.profissional && dados.profissionais.length) {
      estado.profissional = String(dados.profissionais[0].id_profissional);
    }
    el.prof.innerHTML = (estado.modo === "dia" ? `<option value="">Todos os profissionais</option>` : "") +
      dados.profissionais.map((p) => `<option value="${p.id_profissional}" ${String(p.id_profissional) === estado.profissional ? "selected" : ""}>${esc(p.nome)}</option>`).join("");

    container.querySelectorAll("[data-modo]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.modo === estado.modo)));
    container.querySelector("[data-rotulo-anterior]").textContent = estado.modo === "dia" ? "Dia anterior" : "Semana anterior";
    container.querySelector("[data-rotulo-proximo]").textContent = estado.modo === "dia" ? "Próximo dia" : "Próxima semana";
    el.data.value = estado.data;

    // Colunas
    let colunas;
    if (estado.modo === "dia") {
      const profs = dados.profissionais.filter((p) => !estado.profissional || String(p.id_profissional) === estado.profissional);
      colunas = profs.map((p) => ({ chave: `p${p.id_profissional}`, rotulo: p.nome, data: estado.data,
        profissional_id: p.id_profissional, profissional_nome: p.nome }));
      el.titulo.textContent = `${dataLonga(estado.data)}`;
    } else {
      const prof = dados.profissionais.find((p) => String(p.id_profissional) === estado.profissional);
      colunas = [];
      for (let i = 0; i < 7; i++) {
        const dia = somarDias(inicio, i);
        const semana = (lerData(dia).getDay() + 6) % 7;
        if (!dados.horario.dias_funcionamento.includes(semana)) continue;
        colunas.push({ chave: `d${dia}`, rotulo: `${NOMES_DIAS[lerData(dia).getDay()]} ${dia.slice(8, 10)}/${dia.slice(5, 7)}`,
          data: dia, profissional_id: prof?.id_profissional, profissional_nome: prof?.nome || "" });
      }
      el.titulo.textContent = `Semana de ${lerData(inicio).toLocaleDateString("pt-BR")} a ${lerData(fim).toLocaleDateString("pt-BR")} · ${prof?.nome || ""}`;
    }
    desenharGrade(dados, colunas);
  }

  // -------------------------------------------------------------- grade
  function desenharGrade(dados, colunas) {
    const abertura = minutosDoDia(dados.horario.abertura);
    const fechamento = minutosDoDia(dados.horario.fechamento);
    const nLinhas = Math.ceil((fechamento - abertura) / PASSO);
    const diaSemana = (lerData(estado.data).getDay() + 6) % 7;

    if (estado.modo === "dia" && !dados.horario.dias_funcionamento.includes(diaSemana)) {
      el.grade.innerHTML = `<p class="vazio">O salão não funciona neste dia.</p>`;
      return;
    }
    if (!colunas.length) {
      el.grade.innerHTML = `<p class="vazio">Nenhum profissional ativo para exibir.</p>`;
      return;
    }

    // Agrupa os itens por coluna em "blocos" de linhas (itens que dividem
    // a mesma faixa de 30 min ficam no mesmo bloco).
    const linhaDe = (iso, arredondarParaCima) => {
      const m = minutosDoDia(hora(iso)) - abertura;
      return Math.max(0, Math.min(nLinhas, arredondarParaCima ? Math.ceil(m / PASSO) : Math.floor(m / PASSO)));
    };
    const blocos = colunas.map((col) => {
      const doDia = dados.itens
        .filter((i) => i.data_hora_inicio.slice(0, 10) === col.data && i.profissional_id === col.profissional_id)
        .map((i) => ({ ...i, l0: linhaDe(i.data_hora_inicio, false), l1: Math.max(linhaDe(i.data_hora_fim, true), linhaDe(i.data_hora_inicio, false) + 1) }))
        .sort((a, b) => a.l0 - b.l0);
      const lista = [];
      doDia.forEach((item) => {
        const ultimo = lista[lista.length - 1];
        if (ultimo && item.l0 < ultimo.l1) { ultimo.itens.push(item); ultimo.l1 = Math.max(ultimo.l1, item.l1); }
        else lista.push({ l0: item.l0, l1: item.l1, itens: [item] });
      });
      return lista;
    });

    const agora = new Date();
    const agoraISO = `${isoData(agora)}T${hhmm(agora.getHours() * 60 + agora.getMinutes())}`;
    const linhas = [];
    for (let l = 0; l < nLinhas; l++) {
      const horario = hhmm(abertura + l * PASSO);
      const celulas = colunas.map((col, c) => {
        const bloco = blocos[c].find((b) => b.l0 <= l && l < b.l1);
        if (bloco && bloco.l0 !== l) return ""; // coberta pelo rowspan
        if (bloco) {
          return `<td rowspan="${bloco.l1 - bloco.l0}"><div class="celula-bloco">${bloco.itens.map((i) => `
            <button type="button" class="slot slot--ocupado st-${i.status_geral}" tabindex="-1"
              data-agendamento="${i.agendamento_id}" data-linha="${i.l0}" data-coluna="${c}" data-chave="a${i.id_item}">
              <span class="slot__hora">${esc(hora(i.data_hora_inicio))}–${esc(hora(i.data_hora_fim))}</span>
              <span class="slot__servico">${esc(i.servico_nome)}</span>
              <span class="slot__cliente">${esc(i.cliente_nome)}</span>
              <span class="slot__status">${esc(ROTULOS_STATUS[i.status_geral])}${i.pacote_cliente_id ? " · pacote" : ""}</span>
              <span class="visualmente-oculto">, ${esc(estado.modo === "dia" ? col.profissional_nome : col.rotulo)}. Abrir detalhes.</span>
            </button>`).join("")}</div></td>`;
        }
        const passado = `${col.data}T${horario}` <= agoraISO;
        if (passado) return `<td><span class="slot slot--passado" aria-hidden="true"></span><span class="visualmente-oculto">Horário passado</span></td>`;
        return `<td><button type="button" class="slot slot--livre" tabindex="-1" data-livre
            data-data="${col.data}" data-hora="${horario}" data-profissional="${col.profissional_id ?? ""}"
            data-linha="${l}" data-coluna="${c}" data-chave="l${c}-${l}">
            <span class="slot__texto">Livre</span>
            <span class="visualmente-oculto">, ${horario}, ${esc(estado.modo === "dia" ? col.profissional_nome : col.rotulo)}. Criar agendamento.</span>
          </button></td>`;
      }).join("");
      linhas.push(`<tr class="${horario.endsWith(":00") ? "linha-hora-cheia" : ""}"><th scope="row">${horario}</th>${celulas}</tr>`);
    }

    el.grade.innerHTML = `
      <div class="agenda-container">
        <table class="agenda" aria-describedby="${ids.instr}">
          <caption class="visualmente-oculto">${esc(el.titulo.textContent)}. Linhas: horários; colunas: ${estado.modo === "dia" ? "profissionais" : "dias"}.</caption>
          <thead><tr><th scope="col"><span class="visualmente-oculto">Horário</span></th>
            ${colunas.map((c) => `<th scope="col">${esc(c.rotulo)}</th>`).join("")}</tr></thead>
          <tbody>${linhas.join("")}</tbody>
        </table>
      </div>
      <p class="campo__ajuda">${dados.itens.length} serviço(s) agendado(s) no período.</p>`;

    prepararNavegacao(nLinhas, colunas.length);
  }

  // -------------------------------------------------------------- teclado
  function prepararNavegacao(nLinhas, nColunas) {
    const tabela = el.grade.querySelector("table");
    // Mapa [linha][coluna] -> botão (blocos ocupam várias linhas)
    const mapa = Array.from({ length: nLinhas }, () => Array(nColunas).fill(null));
    // Cada célula aponta para o primeiro botão do seu <td>; dentro de um
    // bloco com vários serviços, ↑/↓ percorrem os serviços do bloco.
    const limites = (td) => {
      const l0 = Number(td.querySelector("button.slot").dataset.linha);
      return [l0, l0 + (td.rowSpan || 1) - 1];
    };
    tabela.querySelectorAll("td").forEach((td) => {
      const primeiro = td.querySelector("button.slot");
      if (!primeiro) return;
      const [l0, l1] = limites(td);
      for (let l = l0; l <= Math.min(l1, nLinhas - 1); l++) mapa[l][Number(primeiro.dataset.coluna)] = primeiro;
    });

    const botoes = [...tabela.querySelectorAll("button.slot")];
    const inicial = (ultimaChaveFocada && tabela.querySelector(`[data-chave="${ultimaChaveFocada}"]`))
      || tabela.querySelector("button.slot--livre") || botoes[0];
    if (inicial) inicial.tabIndex = 0;

    function focar(atual, alvo) {
      atual.tabIndex = -1; alvo.tabIndex = 0; alvo.focus();
    }

    function mover(atual, dl, dc, extremo = false) {
      const td = atual.closest("td");
      const irmaos = [...td.querySelectorAll("button.slot")];
      const pos = irmaos.indexOf(atual);
      if (dl && irmaos[pos + dl]) return focar(atual, irmaos[pos + dl]); // dentro do bloco

      const [l0, l1] = limites(td);
      let l = dl > 0 ? l1 : dl < 0 ? l0 : Number(atual.dataset.linha);
      let c = Number(atual.dataset.coluna);
      // Home (dc=+1): varre a linha a partir da 1ª coluna; End (dc=-1): a partir da última
      if (extremo) c = dc > 0 ? -1 : nColunas;
      for (let passos = 0; passos < nLinhas * nColunas; passos++) {
        l += dl; c += dc;
        if (l < 0 || l >= nLinhas || c < 0 || c >= nColunas) return;
        const alvo = mapa[l][c];
        if (extremo && alvo?.closest("td") === td) return; // já está no extremo
        if (alvo && alvo.closest("td") !== td) {
          // Ao subir para um bloco com vários serviços, entra pelo último
          const destino = dl < 0 ? [...alvo.closest("td").querySelectorAll("button.slot")].pop() : alvo;
          return focar(atual, destino);
        }
      }
    }

    tabela.addEventListener("keydown", (e) => {
      const atual = e.target.closest("button.slot");
      if (!atual) return;
      const teclas = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
      if (teclas[e.key]) { e.preventDefault(); mover(atual, ...teclas[e.key]); }
      else if (e.key === "Home") { e.preventDefault(); mover(atual, 0, 1, true); }
      else if (e.key === "End") { e.preventDefault(); mover(atual, 0, -1, true); }
    });
    tabela.addEventListener("focusin", (e) => {
      const b = e.target.closest("button.slot");
      if (!b) return;
      botoes.forEach((x) => { x.tabIndex = x === b ? 0 : -1; });
      ultimaChaveFocada = b.dataset.chave;
    });
    tabela.addEventListener("click", (e) => {
      const b = e.target.closest("button.slot");
      if (!b) return;
      ultimaChaveFocada = b.dataset.chave;
      if (b.dataset.agendamento) abrirDetalheAgendamento(Number(b.dataset.agendamento));
      else abrirFormAgendamento({ data: b.dataset.data, hora: b.dataset.hora, profissional_id: b.dataset.profissional });
    });
  }

  // -------------------------------------------------------------- eventos
  container.querySelector("[data-novo]").addEventListener("click", () =>
    abrirFormAgendamento({ data: estado.data < hojeISO() ? hojeISO() : estado.data, profissional_id: estado.profissional }));

  container.querySelectorAll("[data-modo]").forEach((b) => b.addEventListener("click", () => {
    estado.modo = b.dataset.modo;
    ultimaChaveFocada = null;
    carregar();
  }));
  container.querySelectorAll("[data-navegar]").forEach((b) => b.addEventListener("click", () => {
    const passo = Number(b.dataset.navegar);
    estado.data = passo === 0 ? hojeISO() : somarDias(estado.data, passo * (estado.modo === "dia" ? 1 : 7));
    ultimaChaveFocada = null;
    carregar();
  }));
  el.data.addEventListener("change", () => {
    if (el.data.value) { estado.data = el.data.value; ultimaChaveFocada = null; carregar(); }
  });
  el.prof.addEventListener("change", () => { estado.profissional = el.prof.value; ultimaChaveFocada = null; carregar(); });

  // Recarrega quando um agendamento é criado/alterado em qualquer diálogo
  const aoAlterar = () => { if (document.contains(el.grade)) carregar(); };
  window.addEventListener("agendamentos-alterados", aoAlterar);
  window.addEventListener("hashchange", () => window.removeEventListener("agendamentos-alterados", aoAlterar), { once: true });

  await carregar();
}

/**
 * Gráficos acessíveis em SVG puro (sem bibliotecas).
 *
 * - Uma série por gráfico, uma cor (sem eixo duplo).
 * - O <svg> tem role="img" e um resumo textual (total, maior valor).
 * - Dica ao passar o mouse sobre as barras; para teclado e leitores de
 *   tela, os mesmos dados ficam numa tabela em <details> logo abaixo.
 * - Barras finas com a ponta arredondada (4px) apoiadas na linha de base.
 */
import { esc, novoId } from "../ui.js";

function escalaBonita(maximo, inteiro) {
  if (maximo <= 0) return { topo: 1, passo: 1 };
  const bruto = maximo / 4;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  let passo = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto);
  if (inteiro) passo = Math.max(1, Math.ceil(passo)); // contagens: sem "0,25 atendimento"
  return { topo: passo * Math.ceil(maximo / passo), passo };
}

function caminhoBarra(x, y, largura, base, raio = 4) {
  const altura = base - y;
  if (altura <= 0) return "";
  const r = Math.min(raio, altura, largura / 2);
  return `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + largura - r} Q${x + largura},${y} ${x + largura},${y + r} V${base} Z`;
}

/**
 * dados: [{ rotulo, rotuloCurto, valor }]
 * formatar: (valor) => texto
 */
export function graficoBarras({ titulo, descricao = "", dados, formatar = String, formatarEixo = null,
  nomeValor = "Valor", inteiro = false }) {
  formatarEixo ??= formatar;
  const L = 640, A = 230, m = { topo: 12, dir: 8, base: 30, esq: 56 };
  const larguraUtil = L - m.esq - m.dir, alturaUtil = A - m.topo - m.base;
  const maximo = Math.max(0, ...dados.map((d) => d.valor));
  const { topo, passo } = escalaBonita(maximo, inteiro);
  const banda = larguraUtil / Math.max(dados.length, 1);
  const larguraBarra = Math.min(28, Math.max(3, banda * 0.65));
  const y = (v) => m.topo + alturaUtil - (v / topo) * alturaUtil;
  const base = m.topo + alturaUtil;
  const cadaRotulo = Math.ceil(dados.length / 12); // evita rótulos sobrepostos

  const total = dados.reduce((s, d) => s + d.valor, 0);
  const maior = dados.reduce((a, d) => (d.valor > (a?.valor ?? -1) ? d : a), null);
  const idTitulo = novoId("graf-tit"), idDesc = novoId("graf-desc");
  const resumo = dados.length
    ? `Total no período: ${formatar(total)}. Maior valor: ${formatar(maior.valor)} em ${maior.rotulo}. ${dados.length} dias.`
    : "Sem dados no período.";

  let grade = "";
  for (let v = 0; v <= topo + 1e-9; v += passo) {
    grade += `<line class="grade" x1="${m.esq}" x2="${L - m.dir}" y1="${y(v)}" y2="${y(v)}"/>
      <text class="eixo-texto" x="${m.esq - 6}" y="${y(v) + 4}" text-anchor="end">${esc(formatarEixo(v))}</text>`;
  }
  const barras = dados.map((d, i) => {
    const x = m.esq + i * banda + (banda - larguraBarra) / 2;
    return `<g data-indice="${i}">
        <rect class="barra-alvo" x="${m.esq + i * banda}" y="${m.topo}" width="${banda}" height="${alturaUtil}"/>
        <path class="barra" d="${caminhoBarra(x, y(d.valor), larguraBarra, base)}"/>
        ${i % cadaRotulo === 0 ? `<text class="eixo-texto" x="${x + larguraBarra / 2}" y="${A - 10}" text-anchor="middle">${esc(d.rotuloCurto ?? d.rotulo)}</text>` : ""}
      </g>`;
  }).join("");

  const figura = document.createElement("figure");
  figura.className = "grafico";
  figura.style.margin = "0";
  figura.innerHTML = `
    <figcaption><h3 id="${idTitulo}" style="margin:0 0 .25rem">${esc(titulo)}</h3>
      <p class="campo__ajuda" id="${idDesc}">${esc(descricao)} ${esc(resumo)}</p></figcaption>
    <svg viewBox="0 0 ${L} ${A}" role="img" aria-labelledby="${idTitulo} ${idDesc}" focusable="false">
      ${grade}${barras}
      <line x1="${m.esq}" x2="${L - m.dir}" y1="${base}" y2="${base}" stroke="#6e6e7a"/>
    </svg>
    <div class="grafico__dica" hidden aria-hidden="true"></div>
    <details class="dados-tabela">
      <summary>Ver dados em tabela: ${esc(titulo)}</summary>
      <div class="tabela-container"><table>
        <caption class="visualmente-oculto">${esc(titulo)}</caption>
        <thead><tr><th scope="col">Dia</th><th scope="col" class="numero">${esc(nomeValor)}</th></tr></thead>
        <tbody>${dados.map((d) => `<tr><th scope="row">${esc(d.rotulo)}</th><td class="numero">${esc(formatar(d.valor))}</td></tr>`).join("")}</tbody>
      </table></div>
    </details>`;

  // Dica ao passar o mouse (área de alvo maior que a barra)
  const dica = figura.querySelector(".grafico__dica");
  const svg = figura.querySelector("svg");
  svg.addEventListener("mousemove", (e) => {
    const g = e.target.closest("g[data-indice]");
    if (!g) { dica.hidden = true; return; }
    const d = dados[Number(g.dataset.indice)];
    const caixa = figura.getBoundingClientRect();
    dica.textContent = `${d.rotulo}: ${formatar(d.valor)}`;
    dica.style.left = `${e.clientX - caixa.left}px`;
    dica.style.top = `${e.clientY - caixa.top}px`;
    dica.hidden = false;
  });
  svg.addEventListener("mouseleave", () => { dica.hidden = true; });
  return figura;
}

/** Barras horizontais em HTML (ranking), com valores sempre em texto. */
export function barrasHorizontais(itens, { formatar = String, rotuloLista }) {
  const maximo = Math.max(1, ...itens.map((i) => i.valor));
  return `<ul class="lista-simples" aria-label="${esc(rotuloLista)}">${itens.map((i) => `
    <li class="barra-horizontal">
      <span>${esc(i.rotulo)}</span>
      <span class="barra-horizontal__trilho" aria-hidden="true"><span class="barra-horizontal__preenchimento" style="width:${(i.valor / maximo) * 100}%;display:block"></span></span>
      <strong>${esc(formatar(i.valor))}${i.extra ? ` <span class="campo__ajuda" style="font-weight:400">${esc(i.extra)}</span>` : ""}</strong>
    </li>`).join("")}</ul>`;
}

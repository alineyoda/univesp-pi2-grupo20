/**
 * Utilitários de interface acessível (WCAG 2.2):
 * diálogos modais, avisos para leitores de tela, erros de formulário,
 * formatação de datas/valores e etiquetas de status.
 */

// ------------------------------------------------------------------ texto
/** Escapa HTML para evitar injeção de código (XSS) ao montar templates. */
export function esc(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

const fmtMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const moeda = (v) => fmtMoeda.format(Number(v || 0));
export const numero = (v) => new Intl.NumberFormat("pt-BR").format(Number(v || 0));
export const percentual = (v) => new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 }).format(v || 0);

/** Date -> "AAAA-MM-DD" no horário local (sem conversão para UTC). */
export function isoData(data) {
  const p = (n) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${p(data.getMonth() + 1)}-${p(data.getDate())}`;
}
/** "AAAA-MM-DD" -> Date local (meio-dia evita problemas de fuso). */
export function lerData(iso) {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d, 12);
}
export const hojeISO = () => isoData(new Date());
export function somarDias(iso, dias) {
  const d = lerData(iso);
  d.setDate(d.getDate() + dias);
  return isoData(d);
}
export const hora = (isoDataHora) => (isoDataHora || "").slice(11, 16);
export const dataCurta = (iso) => iso ? lerData(iso).toLocaleDateString("pt-BR") : "";
export const dataLonga = (iso) => lerData(iso).toLocaleDateString("pt-BR",
  { weekday: "long", day: "numeric", month: "long", year: "numeric" });
export const dataHora = (iso) => iso ? `${dataCurta(iso)} às ${hora(iso)}` : "—";
export const minutosDoDia = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
export const hhmm = (min) => `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;

export function formatarTelefone(t) {
  const d = String(t || "").replace(/\D/g, "");
  const local = d.startsWith("55") && d.length >= 12 ? d.slice(2) : d;
  if (local.length === 11) return `(${local.slice(0, 2)}) ${local.slice(2, 7)}-${local.slice(7)}`;
  if (local.length === 10) return `(${local.slice(0, 2)}) ${local.slice(2, 6)}-${local.slice(6)}`;
  return t || "";
}
/** LGPD: na listagem o CPF aparece parcialmente oculto. */
export function cpfMascarado(cpf) {
  if (!cpf) return "—";
  return `***.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-**`;
}
export const formatarCpf = (cpf) => cpf ? `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9)}` : "";

// ------------------------------------------------------------------ status
export const ROTULOS_STATUS = {
  agendado: "Agendado", confirmado: "Confirmado", concluido: "Concluído",
  cancelado: "Cancelado", falta: "Falta", ativo: "Ativo", inativo: "Inativo",
  simulado: "Simulado", enviado: "Enviado", falha: "Falha", pendente: "Pendente",
};
export const ROTULOS_PAGAMENTO = {
  dinheiro: "Dinheiro", pix: "Pix", cartao_credito: "Cartão de crédito", cartao_debito: "Cartão de débito",
};
/** Etiqueta com texto + cor (a cor nunca é a única informação). */
export function etiqueta(status) {
  return `<span class="etiqueta st-${esc(status)}">${esc(ROTULOS_STATUS[status] || status)}</span>`;
}

// ------------------------------------------------------------------ avisos
/**
 * Mostra um aviso visual e o anuncia para leitores de tela.
 * Erros usam a região "assertive" (interrompe a leitura).
 */
export function anunciar(mensagem, tipo = "info") {
  // Com um diálogo modal aberto, o resto da página fica inerte (invisível
  // para leitores de tela): o aviso precisa ser exibido DENTRO do diálogo.
  const dialogo = [...document.querySelectorAll("dialog[open]")].pop();
  let regiao = document.getElementById("avisos");
  if (dialogo) {
    regiao = dialogo.querySelector(".avisos");
    if (!regiao) {
      regiao = document.createElement("div");
      regiao.className = "avisos";
      regiao.setAttribute("role", "status");
      regiao.setAttribute("aria-live", "polite");
      dialogo.append(regiao);
    }
  }
  const aviso = document.createElement("div");
  aviso.className = `aviso aviso--${tipo}`;
  if (dialogo && tipo === "erro") aviso.setAttribute("role", "alert");
  aviso.textContent = mensagem;
  regiao.appendChild(aviso);
  if (tipo === "erro" && !dialogo) {
    const urgente = document.getElementById("avisos-urgentes");
    urgente.textContent = "";
    setTimeout(() => { urgente.textContent = mensagem; }, 50);
  }
  // Tempo generoso para leitura; erros ficam mais tempo
  setTimeout(() => aviso.remove(), tipo === "erro" ? 10000 : 6000);
}

// ------------------------------------------------------------------ diálogos
let contadorIds = 0;
export const novoId = (prefixo = "id") => `${prefixo}-${++contadorIds}`;

/**
 * Abre um diálogo modal acessível usando <dialog> nativo:
 * - showModal() torna o resto da página inerte e prende o foco no diálogo;
 * - Esc fecha; o foco volta ao elemento que abriu o diálogo;
 * - aria-labelledby liga o diálogo ao seu título.
 * Retorna { dialogo, corpo, rodape, fechar }.
 */
export function abrirDialogo({ titulo, conteudo = "", rodape = "", pequeno = false, papel = "dialog", aoFechar } = {}) {
  const origem = document.activeElement;
  const idTitulo = novoId("dialogo-titulo");
  const dialogo = document.createElement("dialog");
  dialogo.setAttribute("aria-labelledby", idTitulo);
  if (papel === "alertdialog") dialogo.setAttribute("role", "alertdialog");
  if (pequeno) dialogo.classList.add("dialogo--pequeno");
  dialogo.innerHTML = `
    <div class="dialogo__cabecalho">
      <h2 id="${idTitulo}" tabindex="-1">${esc(titulo)}</h2>
      <button type="button" class="botao botao--fantasma" data-fechar aria-label="Fechar: ${esc(titulo)}">✕</button>
    </div>
    <div class="dialogo__corpo"></div>
    <div class="dialogo__rodape"></div>`;
  const corpo = dialogo.querySelector(".dialogo__corpo");
  const areaRodape = dialogo.querySelector(".dialogo__rodape");
  if (typeof conteudo === "string") corpo.innerHTML = conteudo; else corpo.append(conteudo);
  if (typeof rodape === "string") areaRodape.innerHTML = rodape; else areaRodape.append(rodape);
  if (!areaRodape.innerHTML.trim()) areaRodape.hidden = true;

  const fechar = (valor) => dialogo.close(valor ?? "");
  dialogo.addEventListener("click", (e) => { if (e.target.closest("[data-fechar]")) fechar("cancelar"); });
  dialogo.addEventListener("close", () => {
    dialogo.remove();
    if (origem && document.contains(origem)) origem.focus();
    aoFechar?.(dialogo.returnValue);
  });

  document.body.appendChild(dialogo);
  dialogo.showModal();
  // Foco inicial: primeiro campo do formulário; senão, o título.
  const primeiro = corpo.querySelector("input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea");
  (primeiro || dialogo.querySelector("h2")).focus();
  return { dialogo, corpo, rodape: areaRodape, fechar, titulo: dialogo.querySelector("h2") };
}

/** Diálogo de confirmação. Retorna Promise<boolean>. */
export function confirmar(mensagem, { titulo = "Confirmar ação", textoConfirmar = "Confirmar", perigo = false } = {}) {
  return new Promise((resolver) => {
    let confirmado = false;
    const { dialogo, fechar } = abrirDialogo({
      titulo, pequeno: true, papel: "alertdialog",
      conteudo: `<p>${esc(mensagem)}</p>`,
      rodape: `<button type="button" class="botao botao--fantasma" data-fechar data-voltar>Voltar</button>
               <button type="button" class="botao ${perigo ? "botao--perigo" : "botao--primario"}" data-ok>${esc(textoConfirmar)}</button>`,
      aoFechar: () => resolver(confirmado),
    });
    dialogo.querySelector("[data-ok]").addEventListener("click", () => { confirmado = true; fechar("ok"); });
    // Em ações destrutivas o foco inicial fica em "Voltar" (opção segura)
    dialogo.querySelector(perigo ? "[data-voltar]" : "[data-ok]").focus();
  });
}

// ------------------------------------------------------------------ formulários
export function dadosDoFormulario(form) {
  const dados = {};
  new FormData(form).forEach((valor, chave) => { dados[chave] = typeof valor === "string" ? valor.trim() : valor; });
  form.querySelectorAll("input[type=checkbox][name]").forEach((c) => { dados[c.name] = c.checked; });
  return dados;
}

export function limparErros(form) {
  form.querySelectorAll(".campo__erro[data-gerado]").forEach((e) => e.remove());
  form.querySelectorAll("[aria-invalid]").forEach((campo) => {
    campo.removeAttribute("aria-invalid");
    const ids = (campo.getAttribute("aria-describedby") || "").split(" ").filter((id) => !id.startsWith("erro-"));
    if (ids.length) campo.setAttribute("aria-describedby", ids.join(" ")); else campo.removeAttribute("aria-describedby");
  });
  form.querySelector(".resumo-erros")?.remove();
}

/**
 * Mostra os erros devolvidos pela API (WCAG 3.3.1 / 3.3.3):
 * - resumo no topo (role=alert) com links para cada campo;
 * - mensagem junto ao campo, ligada por aria-describedby;
 * - aria-invalid=true e foco no resumo.
 */
export function mostrarErros(form, erro, rotulos = {}) {
  limparErros(form);
  const campos = erro.campos || {};
  const itens = [];
  Object.entries(campos).forEach(([nome, mensagem]) => {
    const campo = form.querySelector(`[data-campo="${CSS.escape(nome)}"]`) || form.querySelector(`[name="${CSS.escape(nome)}"]`);
    const rotulo = rotulos[nome] || campo?.labels?.[0]?.textContent?.replace("*", "").trim() || nome;
    if (campo) {
      const idErro = `erro-${campo.id || novoId("campo")}`;
      const p = document.createElement("p");
      p.className = "campo__erro"; p.id = idErro; p.dataset.gerado = "1"; p.textContent = mensagem;
      const caixa = campo.closest(".campo");
      if (caixa) caixa.append(p); else campo.after(p);
      campo.setAttribute("aria-invalid", "true");
      campo.setAttribute("aria-describedby", `${campo.getAttribute("aria-describedby") || ""} ${idErro}`.trim());
      itens.push(`<li><a href="#${esc(campo.id)}">${esc(rotulo)}: ${esc(mensagem)}</a></li>`);
    } else {
      itens.push(`<li>${esc(rotulo)}: ${esc(mensagem)}</li>`);
    }
  });
  const resumo = document.createElement("div");
  resumo.className = "alerta alerta--erro resumo-erros";
  resumo.setAttribute("role", "alert");
  resumo.tabIndex = -1;
  resumo.innerHTML = `<strong>${esc(erro.message)}</strong>${itens.length ? `<ul>${itens.join("")}</ul>` : ""}`;
  resumo.addEventListener("click", (e) => {
    const link = e.target.closest("a[href^='#']");
    if (link) { e.preventDefault(); form.querySelector(link.getAttribute("href"))?.focus(); }
  });
  form.prepend(resumo);
  resumo.focus();
}

/** Gera o HTML de um campo com rótulo, ajuda e indicação de obrigatório. */
export function campoHTML({ nome, rotulo, tipo = "text", valor = "", obrigatorio = false, ajuda = "",
  autocomplete = "off", opcoes = null, atributos = "", id = null }) {
  const idCampo = id || novoId(`campo-${nome}`);
  const idAjuda = ajuda ? `${idCampo}-ajuda` : "";
  const req = obrigatorio ? `required aria-required="true"` : "";
  const desc = idAjuda ? `aria-describedby="${idAjuda}"` : "";
  let controle;
  if (opcoes) {
    controle = `<select id="${idCampo}" name="${esc(nome)}" data-campo="${esc(nome)}" ${req} ${desc} ${atributos}>
      ${opcoes.map((o) => `<option value="${esc(o.valor)}" ${String(o.valor) === String(valor) ? "selected" : ""}>${esc(o.rotulo)}</option>`).join("")}
    </select>`;
  } else {
    controle = `<input id="${idCampo}" name="${esc(nome)}" data-campo="${esc(nome)}" type="${tipo}"
      value="${esc(valor)}" autocomplete="${autocomplete}" ${req} ${desc} ${atributos}>`;
  }
  return `<div class="campo">
    <label for="${idCampo}">${esc(rotulo)}${obrigatorio ? ` <span class="obrigatorio" aria-hidden="true">*</span>` : ""}</label>
    ${controle}
    ${ajuda ? `<p class="campo__ajuda" id="${idAjuda}">${esc(ajuda)}</p>` : ""}
  </div>`;
}

/** Desabilita o botão de envio durante a requisição (evita duplo envio). */
export async function comBotaoOcupado(botao, tarefa, textoOcupado = "Salvando…") {
  const original = botao.textContent;
  botao.disabled = true;
  botao.setAttribute("aria-busy", "true");
  botao.textContent = textoOcupado;
  try { return await tarefa(); } finally {
    botao.disabled = false;
    botao.removeAttribute("aria-busy");
    botao.textContent = original;
  }
}

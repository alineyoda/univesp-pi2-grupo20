/**
 * Ponto de entrada do front-end (Single Page Application).
 * - Controla login/logout.
 * - Roteamento por hash (#/agenda, #/clientes...): cada tela é um módulo
 *   carregado sob demanda (import dinâmico) com a função renderizar().
 * - Ao trocar de tela: atualiza o <title>, marca o link atual
 *   (aria-current) e move o foco para o título da página (WCAG 2.4.3).
 */
import { definirAoExpirarSessao, get, post, sessao } from "./api.js";
import { anunciar, esc } from "./ui.js";

const ROTAS = {
  dashboard: { titulo: "Painel gerencial", carregar: () => import("./paginas/dashboard.js") },
  agenda: { titulo: "Agenda", carregar: () => import("./paginas/agenda.js") },
  clientes: { titulo: "Clientes", carregar: () => import("./paginas/clientes.js") },
  profissionais: { titulo: "Profissionais", carregar: () => import("./paginas/profissionais.js") },
  servicos: { titulo: "Serviços", carregar: () => import("./paginas/servicos.js") },
  pacotes: { titulo: "Pacotes", carregar: () => import("./paginas/pacotes.js") },
  notificacoes: { titulo: "WhatsApp", carregar: () => import("./paginas/notificacoes.js") },
  ajuda: { titulo: "Ajuda", carregar: async () => ({ renderizar: renderizarAjuda }) },
};

const NOME_SALAO = document.title.split("·")[0].trim();
const telaLogin = document.getElementById("tela-login");
const telaApp = document.getElementById("tela-app");
const conteudo = document.getElementById("conteudo");

// ------------------------------------------------------------------ login
function mostrarLogin(mensagem) {
  sessao.usuario = null;
  telaApp.hidden = true;
  telaLogin.hidden = false;
  document.title = `Entrar · ${NOME_SALAO}`;
  const erro = document.getElementById("login-erro");
  erro.hidden = !mensagem;
  erro.textContent = mensagem || "";
  document.getElementById("login-email").focus();
}

function mostrarApp(usuario) {
  sessao.usuario = usuario;
  document.getElementById("usuario-nome").textContent = `${usuario.nome} (${usuario.perfil})`;
  telaLogin.hidden = true;
  telaApp.hidden = false;
  if (!location.hash || location.hash === "#/") location.hash = "#/dashboard";
  else navegar();
}

document.getElementById("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = evento.currentTarget;
  const email = form.email.value.trim();
  const senha = form.senha.value;
  const erro = document.getElementById("login-erro");
  if (!email || !senha) {
    erro.hidden = false;
    erro.textContent = "Preencha o e-mail e a senha.";
    (email ? form.senha : form.email).focus();
    return;
  }
  const botao = form.querySelector("button[type=submit]");
  botao.disabled = true;
  try {
    const resposta = await post("/auth/login", { email, senha });
    form.reset();
    mostrarApp(resposta.usuario);
    anunciar(`Bem-vindo(a), ${resposta.usuario.nome}.`, "sucesso");
  } catch (e) {
    erro.hidden = false;
    erro.textContent = e.message;
    form.senha.focus();
  } finally {
    botao.disabled = false;
  }
});

// Mostrar/ocultar senha (ajuda pessoas com dificuldade de digitação)
document.getElementById("mostrar-senha").addEventListener("click", (e) => {
  const campo = document.getElementById("login-senha");
  const mostrar = campo.type === "password";
  campo.type = mostrar ? "text" : "password";
  e.currentTarget.setAttribute("aria-pressed", String(mostrar));
  e.currentTarget.textContent = mostrar ? "Ocultar senha" : "Mostrar senha";
});

document.getElementById("botao-sair").addEventListener("click", async () => {
  await post("/auth/logout").catch(() => {});
  location.hash = "";
  mostrarLogin();
  anunciar("Sessão encerrada.");
});

definirAoExpirarSessao(() => mostrarLogin("Sua sessão expirou. Entre novamente."));

// ------------------------------------------------------------------ menu (celular)
const botaoMenu = document.getElementById("botao-menu");
const menu = document.getElementById("menu-principal");
function definirMenuAberto(aberto) {
  botaoMenu.setAttribute("aria-expanded", String(aberto));
  menu.dataset.aberto = String(aberto);
}
botaoMenu.addEventListener("click", () => definirMenuAberto(botaoMenu.getAttribute("aria-expanded") !== "true"));
definirMenuAberto(false);

// ------------------------------------------------------------------ roteamento
/** Lê "#/rota?a=1&b=2" -> { rota, parametros }. */
function lerHash() {
  const [caminho, busca = ""] = location.hash.replace(/^#\/?/, "").split("?");
  return { rota: caminho || "dashboard", parametros: Object.fromEntries(new URLSearchParams(busca)) };
}

let navegacaoAtual = 0;
async function navegar() {
  if (!sessao.usuario) return;
  const { rota, parametros } = lerHash();
  const definicao = ROTAS[rota] || ROTAS.dashboard;
  const chave = ROTAS[rota] ? rota : "dashboard";
  const id = ++navegacaoAtual;

  document.title = `${definicao.titulo} · ${NOME_SALAO}`;
  menu.querySelectorAll("a").forEach((link) => {
    if (link.dataset.rota === chave) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  definirMenuAberto(false);
  conteudo.setAttribute("aria-busy", "true");
  conteudo.innerHTML = `<p class="carregando" role="status">Carregando ${esc(definicao.titulo.toLowerCase())}…</p>`;

  try {
    const modulo = await definicao.carregar();
    if (id !== navegacaoAtual) return; // usuário já trocou de tela
    conteudo.innerHTML = "";
    await modulo.renderizar(conteudo, parametros);
  } catch (e) {
    if (e.status === 401) return;
    conteudo.innerHTML = `<div class="alerta alerta--erro" role="alert"><h1 tabindex="-1">Erro ao carregar</h1><p>${esc(e.message)}</p></div>`;
  } finally {
    conteudo.removeAttribute("aria-busy");
  }
  // Foco no título da nova tela: leitores de tela anunciam a mudança
  const titulo = conteudo.querySelector("h1");
  if (titulo) { titulo.tabIndex = -1; titulo.focus({ preventScroll: false }); }
}
window.addEventListener("hashchange", navegar);

// ------------------------------------------------------------------ ajuda
function renderizarAjuda(container) {
  container.innerHTML = `
    <div class="cabecalho-pagina"><div><h1>Ajuda e atalhos de teclado</h1>
      <p>Todo o sistema pode ser usado somente com o teclado.</p></div></div>
    <section class="cartao" aria-labelledby="ajuda-teclado">
      <h2 id="ajuda-teclado">Navegação pelo teclado</h2>
      <table>
        <caption class="visualmente-oculto">Teclas e funções</caption>
        <thead><tr><th scope="col">Tecla</th><th scope="col">Função</th></tr></thead>
        <tbody>
          <tr><td><kbd>Tab</kbd> / <kbd>Shift</kbd> + <kbd>Tab</kbd></td><td>Avança / volta entre links, botões e campos</td></tr>
          <tr><td><kbd>Enter</kbd> ou <kbd>Espaço</kbd></td><td>Ativa o botão ou link em foco</td></tr>
          <tr><td><kbd>Esc</kbd></td><td>Fecha a janela (diálogo) aberta e devolve o foco para onde você estava</td></tr>
          <tr><td>Setas ← ↑ → ↓ (na agenda)</td><td>Movem entre os horários da grade da agenda</td></tr>
          <tr><td><kbd>Home</kbd> / <kbd>End</kbd> (na agenda)</td><td>Primeira / última coluna da linha de horário</td></tr>
        </tbody>
      </table>
    </section>
    <section class="cartao" aria-labelledby="ajuda-agenda">
      <h2 id="ajuda-agenda">Como agendar</h2>
      <ol>
        <li>Na <a href="#/agenda">Agenda</a>, escolha um horário marcado como <strong>Livre</strong> ou use “Novo agendamento”.</li>
        <li>Escolha o cliente, o serviço, o profissional, a data e um dos horários livres.</li>
        <li>Para serviços <strong>simultâneos</strong> (ex.: coloração e manicure ao mesmo tempo), use “Adicionar serviço no mesmo horário”.
          Para serviços <strong>em sequência</strong>, use “Adicionar serviço em sequência”.</li>
        <li>Se o cliente tiver um pacote, selecione-o no campo “Usar pacote”: o serviço sai por R$ 0,00.</li>
        <li>Ao salvar, a mensagem de confirmação de WhatsApp é gerada automaticamente.</li>
      </ol>
    </section>
    <section class="cartao" aria-labelledby="ajuda-acess">
      <h2 id="ajuda-acess">Acessibilidade</h2>
      <p>O sistema segue as diretrizes WCAG 2.2 (nível AA): contraste adequado, foco sempre visível,
        status indicados por texto (não só por cor), mensagens anunciadas a leitores de tela e
        áreas de clique de no mínimo 44 × 44 pixels. É possível ampliar a página (zoom) até 400% sem perda de conteúdo.</p>
    </section>`;
}

// ------------------------------------------------------------------ início
(async function iniciar() {
  try {
    mostrarApp(await get("/auth/me"));
  } catch {
    mostrarLogin();
  }
})();

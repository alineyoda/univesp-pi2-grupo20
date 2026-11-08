/**
 * Cliente HTTP da API REST (/api/...), baseado em fetch.
 * - Envia e recebe JSON.
 * - Inclui o cookie de sessão (mesma origem).
 * - Converte respostas de erro em ErroApi { status, mensagem, campos }.
 */

export class ErroApi extends Error {
  constructor(status, mensagem, campos = {}) {
    super(mensagem);
    this.status = status;
    this.campos = campos;
  }
}

/** Usuário logado (preenchido pelo app.js). Usado para checar o perfil admin. */
export const sessao = { usuario: null };
export const ehAdmin = () => sessao.usuario?.perfil === "admin";

/** Chamado quando a sessão expira (401): o app volta para o login. */
let aoExpirarSessao = () => {};
export function definirAoExpirarSessao(funcao) { aoExpirarSessao = funcao; }

export async function api(caminho, { metodo = "GET", dados, parametros } = {}) {
  let url = `/api${caminho}`;
  if (parametros) {
    const busca = new URLSearchParams();
    Object.entries(parametros).forEach(([chave, valor]) => {
      if (valor !== undefined && valor !== null && valor !== "") busca.append(chave, valor);
    });
    const texto = busca.toString();
    if (texto) url += `?${texto}`;
  }

  const opcoes = { method: metodo, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (dados !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(dados);
  }

  let resposta;
  try {
    resposta = await fetch(url, opcoes);
  } catch {
    throw new ErroApi(0, "Sem conexão com o servidor. Verifique sua internet e tente novamente.");
  }

  if (resposta.status === 204) return null;
  const corpo = await resposta.json().catch(() => ({}));

  if (!resposta.ok) {
    if (resposta.status === 401 && !caminho.startsWith("/auth/")) aoExpirarSessao();
    throw new ErroApi(resposta.status, corpo.erro || `Erro ${resposta.status}`, corpo.campos || {});
  }
  return corpo;
}

// Atalhos
export const get = (caminho, parametros) => api(caminho, { parametros });
export const post = (caminho, dados = {}) => api(caminho, { metodo: "POST", dados });
export const put = (caminho, dados) => api(caminho, { metodo: "PUT", dados });
export const patch = (caminho, dados) => api(caminho, { metodo: "PATCH", dados });
export const del = (caminho) => api(caminho, { metodo: "DELETE" });

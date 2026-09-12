import type { Estatisticas, Dispositivo } from "./types";
import { createClient } from "./supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function cabecalhoAutorizacao(): Promise<Record<string, string>> {
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const maxTentativas = 3;
  let ultimoErro: Error | null = null;

  for (let tentativa = 0; tentativa < maxTentativas; tentativa++) {
    try {
      const resp = await fetch(`${API_URL}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers || {}),
        },
        cache: "no-store",
      });
      if (!resp.ok) {
        const texto = await resp.text();
        throw new ApiError(resp.status, texto || resp.statusText);
      }
      return resp.json() as Promise<T>;
    } catch (err) {
      ultimoErro = err instanceof Error ? err : new Error(String(err));
      // Só retenta em erros de rede/cold start (não em 4xx)
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) throw err;
      if (tentativa < maxTentativas - 1) {
        await new Promise((r) => setTimeout(r, 1000 * (tentativa + 1)));
      }
    }
  }
  throw ultimoErro;
}

export const api = {
  estatisticas: (dispositivoId: string, horas = 24) =>
    fetchJSON<Estatisticas>(
      `/estatisticas/${dispositivoId}?horas=${horas}`,
    ),

  atualizarLimites: async (
    dispositivoId: string,
    payload: Partial<{
      temperatura_min: number;
      temperatura_max: number;
      umidade_min: number;
      umidade_max: number;
      intervalo_offline_segundos: number;
    }>,
  ) =>
    fetchJSON<Dispositivo>(`/dispositivos/${dispositivoId}/limites`, {
      method: "PATCH",
      headers: await cabecalhoAutorizacao(),
      body: JSON.stringify(payload),
    }),
};

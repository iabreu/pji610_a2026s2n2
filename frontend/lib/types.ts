// Tipos alinhados com o schema do Supabase

export type StatusDispositivo = "online" | "offline";

export type TipoAlerta =
  | "temperatura_alta"
  | "temperatura_baixa"
  | "umidade_alta"
  | "umidade_baixa"
  | "anomalia_temperatura"
  | "anomalia_umidade";

export type MetodoAlerta = "limiar_fixo" | "limiar_dinamico";

export interface Dispositivo {
  id: string;
  nome: string;
  localizacao: string;
  temperatura_min: number;
  temperatura_max: number;
  umidade_min: number;
  umidade_max: number;
  z_limite: number;
  janela_baseline_minutos: number;
  intervalo_offline_segundos: number;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
  // Da view vw_dispositivos_status:
  ultima_temperatura: number | null;
  ultima_umidade: number | null;
  ultima_leitura_em: string | null;
  status: StatusDispositivo;
}

export interface Leitura {
  id: string;
  dispositivo_id: string;
  temperatura: number;
  umidade: number;
  amostras: number;
  descartadas: number;
  desvio_temperatura: number | null;
  desvio_umidade: number | null;
  registrado_em: string;
}

export interface Alerta {
  id: string;
  dispositivo_id: string;
  leitura_id: string;
  tipo: TipoAlerta;
  metodo: MetodoAlerta;
  valor_medido: number;
  limite: number;
  escore_z: number | null;
  registrado_em: string;
}

export interface Baseline {
  dispositivo_id: string;
  janela_minutos: number;
  media_temperatura: number;
  desvio_temperatura: number;
  media_umidade: number;
  desvio_umidade: number;
  amostras: number;
  calculado_em: string;
}

export interface Estatisticas {
  dispositivo_id: string;
  inicio: string;
  fim: string;
  total_leituras: number;
  temperatura_media: number | null;
  temperatura_min: number | null;
  temperatura_max: number | null;
  umidade_media: number | null;
  umidade_min: number | null;
  umidade_max: number | null;
  total_alertas: number;
}

export type PeriodoFiltro = "1h" | "6h" | "24h" | "7d" | "30d";

export const PERIODO_HORAS: Record<PeriodoFiltro, number> = {
  "1h": 1,
  "6h": 6,
  "24h": 24,
  "7d": 24 * 7,
  "30d": 24 * 30,
};

export const PERIODO_LABEL: Record<PeriodoFiltro, string> = {
  "1h": "Última hora",
  "6h": "Últimas 6 horas",
  "24h": "Últimas 24 horas",
  "7d": "Últimos 7 dias",
  "30d": "Últimos 30 dias",
};

export const TIPO_ALERTA_LABEL: Record<TipoAlerta, string> = {
  temperatura_alta: "Temperatura alta",
  temperatura_baixa: "Temperatura baixa",
  umidade_alta: "Umidade alta",
  umidade_baixa: "Umidade baixa",
  anomalia_temperatura: "Anomalia de temperatura",
  anomalia_umidade: "Anomalia de umidade",
};

export const METODO_ALERTA_LABEL: Record<MetodoAlerta, string> = {
  limiar_fixo: "Limiar fixo",
  limiar_dinamico: "Limiar dinâmico",
};

"use client";

import { useMemo } from "react";
import {
  ThermometerSun,
  ThermometerSnowflake,
  Droplets,
  CloudOff,
  Activity,
} from "lucide-react";
import {
  formatarDataHora,
  formatarNumero,
  formatarTempoRelativo,
} from "@/lib/utils";
import { TIPO_ALERTA_LABEL, type Alerta, type Dispositivo, type TipoAlerta } from "@/lib/types";

const iconePorTipo: Record<TipoAlerta, typeof ThermometerSun> = {
  temperatura_alta: ThermometerSun,
  temperatura_baixa: ThermometerSnowflake,
  umidade_alta: Droplets,
  umidade_baixa: CloudOff,
  anomalia_temperatura: Activity,
  anomalia_umidade: Activity,
};

const corPorTipo: Record<TipoAlerta, string> = {
  temperatura_alta: "text-destructive bg-destructive/10",
  temperatura_baixa: "text-sky-600 bg-sky-100 dark:bg-sky-950 dark:text-sky-300",
  umidade_alta: "text-blue-600 bg-blue-100 dark:bg-blue-950 dark:text-blue-300",
  umidade_baixa: "text-amber-600 bg-amber-100 dark:bg-amber-950 dark:text-amber-300",
  anomalia_temperatura:
    "text-violet-600 bg-violet-100 dark:bg-violet-950 dark:text-violet-300",
  anomalia_umidade:
    "text-violet-600 bg-violet-100 dark:bg-violet-950 dark:text-violet-300",
};

const unidadePorTipo: Record<TipoAlerta, string> = {
  temperatura_alta: "°C",
  temperatura_baixa: "°C",
  umidade_alta: "%",
  umidade_baixa: "%",
  anomalia_temperatura: "°C",
  anomalia_umidade: "%",
};

interface ListaAlertasProps {
  alertas: Alerta[];
  dispositivos: Dispositivo[];
}

export function ListaAlertas({ alertas, dispositivos }: ListaAlertasProps) {
  const dispositivoMap = useMemo(
    () => Object.fromEntries(dispositivos.map((d) => [d.id, d])),
    [dispositivos],
  );

  if (alertas.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
        Nenhum alerta no período selecionado.
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {alertas.map((alerta) => {
        const Icone = iconePorTipo[alerta.tipo];
        const dispositivo = dispositivoMap[alerta.dispositivo_id];
        const unidade = unidadePorTipo[alerta.tipo];
        const direcao = alerta.tipo.endsWith("alta") ? "acima do" : "abaixo do";

        return (
          <li
            key={alerta.id}
            className="flex items-start gap-3 rounded-md border bg-card p-4"
          >
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${corPorTipo[alerta.tipo]}`}
            >
              <Icone className="h-5 w-5" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <p className="font-medium">
                  {TIPO_ALERTA_LABEL[alerta.tipo]}
                </p>
                <p className="text-sm text-muted-foreground">
                  em {dispositivo?.nome ?? alerta.dispositivo_id}
                </p>
              </div>
              <p className="mt-1 text-sm">
                Valor medido:{" "}
                <span className="font-semibold tabular-nums">
                  {formatarNumero(alerta.valor_medido)}
                  {unidade}
                </span>
                {", "}
                {direcao} limite de{" "}
                <span className="font-semibold tabular-nums">
                  {formatarNumero(alerta.limite)}
                  {unidade}
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatarDataHora(alerta.registrado_em)} ·{" "}
                {formatarTempoRelativo(alerta.registrado_em)}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

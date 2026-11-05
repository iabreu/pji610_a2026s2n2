"""Geração das séries dos cenários de teste e réplica do algoritmo de detecção.

As séries são determinísticas (semente fixa) para que a execução possa ser
repetida e conferida. O gabarito (quais leituras são anômalas) é definido aqui,
antes de qualquer execução, e não é ajustado depois dos resultados.

Cenário de referência: sala de equipamentos de TI climatizada, com limite fixo
de 18 a 27 °C, faixa recomendada pela ASHRAE TC 9.9 (5. ed., 2021).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field

N_LEITURAS = 150          # uma leitura agregada por minuto -> 150 minutos
NIVEL_BASE = 23.0         # °C, operação normal da sala climatizada
RUIDO_TEMP = 0.35         # desvio-padrão do ruído de temperatura (°C)
OSCILACAO = 0.5           # amplitude da oscilação do ar-condicionado (°C)
PERIODO_OSC = 120         # período da oscilação (min)
UMIDADE_BASE = 50.0       # %
RUIDO_UMID = 1.2          # %

LIMITES = {
    "temperatura_min": 18.0,
    "temperatura_max": 27.0,
    "umidade_min": 30.0,
    "umidade_max": 70.0,
    "z_limite": 3.0,
    "janela_baseline_minutos": 180,
    "intervalo_offline_segundos": 120,
}

LIMIAR_DERIVA = 2.0       # °C acima do nível de operação passa a contar como anômalo


@dataclass
class Cenario:
    chave: str
    titulo: str
    descricao: str
    temperatura: list[float]
    umidade: list[float]
    anomala: list[bool]                 # gabarito para temperatura
    marcos: dict = field(default_factory=dict)


def _base(rng: random.Random) -> tuple[list[float], list[float]]:
    temp, umid = [], []
    for i in range(N_LEITURAS):
        t = NIVEL_BASE + OSCILACAO * math.sin(2 * math.pi * i / PERIODO_OSC) + rng.gauss(0, RUIDO_TEMP)
        u = UMIDADE_BASE + rng.gauss(0, RUIDO_UMID)
        temp.append(round(t, 2))
        umid.append(round(u, 2))
    return temp, umid


def gerar_cenarios(semente: int = 42) -> list[Cenario]:
    cenarios: list[Cenario] = []

    # 1. Operação normal: nenhuma leitura anômala no gabarito.
    rng = random.Random(semente + 1)
    t, u = _base(rng)
    cenarios.append(Cenario(
        "operacao_normal", "Operação normal",
        "Temperatura em torno de 23 °C, com oscilação do ar-condicionado e ruído do sensor. Nenhuma anomalia inserida.",
        t, u, [False] * N_LEITURAS,
    ))

    # 2. Picos isolados: um abaixo e um acima do limite fixo de 27 °C.
    rng = random.Random(semente + 2)
    t, u = _base(rng)
    gab = [False] * N_LEITURAS
    t[90], gab[90] = 26.8, True     # pico que não atinge o limite fixo
    t[120], gab[120] = 28.5, True   # pico que ultrapassa o limite fixo
    cenarios.append(Cenario(
        "pico_isolado", "Picos isolados",
        "Duas leituras pontuais fora do padrão: 26,8 °C no minuto 90, abaixo do limite fixo, e 28,5 °C no minuto 120, acima dele.",
        t, u, gab, {"picos": [90, 120]},
    ))

    # 3. Variação brusca sustentada: degrau de +3,5 °C por 20 minutos.
    rng = random.Random(semente + 3)
    t, u = _base(rng)
    gab = [False] * N_LEITURAS
    for i in range(100, 120):
        t[i] = round(t[i] + 3.5, 2)
        gab[i] = True
    cenarios.append(Cenario(
        "variacao_brusca", "Variação brusca sustentada",
        "Elevação repentina de 3,5 °C entre os minutos 100 e 119, simulando o desligamento temporário da climatização, seguida de retorno ao nível normal.",
        t, u, gab, {"inicio": 100, "fim": 119},
    ))

    # 4. Deriva lenta: subida de 0,05 °C por minuto a partir do minuto 60.
    rng = random.Random(semente + 4)
    t, u = _base(rng)
    gab = [False] * N_LEITURAS
    for i in range(60, N_LEITURAS):
        desvio = 0.05 * (i - 60)
        t[i] = round(t[i] + desvio, 2)
        gab[i] = desvio >= LIMIAR_DERIVA
    cenarios.append(Cenario(
        "deriva_lenta", "Deriva lenta",
        "Aumento gradual de 0,05 °C por minuto a partir do minuto 60. Contam como anômalas as leituras em que a subida acumulada chega a 2 °C.",
        t, u, gab, {"inicio_deriva": 60, "primeira_anomala": gab.index(True)},
    ))

    return cenarios


# ----------------------------------------------------------------------------
# Réplica do algoritmo do banco (fn_recalcular_baseline + fn_detectar_anomalias)
# ----------------------------------------------------------------------------
# O banco grava temperatura em NUMERIC(5,2) e a linha de base em NUMERIC(6,3),
# e a API chama a detecção depois de cada inserção. A réplica reproduz esse
# arredondamento e a execução incremental, para que possa ser comparada com o
# resultado real e para calcular a variante que exclui a própria leitura.

def _r3(x: float) -> float:
    return float(f"{x:.3f}")


def replicar_deteccao(serie: list[float], z_limite: float = 3.0,
                      minimo: int = 30, excluir_propria: bool = False) -> dict[int, int]:
    """Devolve {índice da leitura sinalizada: passo em que o alerta foi criado}."""
    criado_em: dict[int, int] = {}
    for k in range(len(serie)):
        janela = serie[: k + 1]
        if len(janela) < minimo:
            continue
        if not excluir_propria:
            media = _r3(statistics.fmean(janela))
            desvio = _r3(statistics.stdev(janela))
            if desvio <= 0:
                continue
            for j, x in enumerate(janela):
                if j not in criado_em and abs((x - media) / desvio) > z_limite:
                    criado_em[j] = k
        else:
            for j, x in enumerate(janela):
                if j in criado_em:
                    continue
                resto = janela[:j] + janela[j + 1:]
                if len(resto) < minimo:
                    continue
                media = statistics.fmean(resto)
                desvio = statistics.stdev(resto)
                if desvio > 0 and abs((x - media) / desvio) > z_limite:
                    criado_em[j] = k
    return criado_em


def replicar_fixo(serie: list[float], minimo_c: float, maximo_c: float) -> dict[int, int]:
    return {i: i for i, x in enumerate(serie) if x > maximo_c or x < minimo_c}


def metricas(criado_em: dict[int, int], gabarito: list[bool]) -> dict:
    """criado_em: {índice da leitura sinalizada: passo em que o alerta surgiu}."""
    sinalizadas = set(criado_em)
    anomalas = {i for i, a in enumerate(gabarito) if a}
    vp = len(sinalizadas & anomalas)
    fp = len(sinalizadas - anomalas)
    fn = len(anomalas - sinalizadas)
    m = {
        "alertas": len(sinalizadas),
        "verdadeiros_positivos": vp,
        "falsos_positivos": fp,
        "nao_detectadas": fn,
        "anomalas_no_gabarito": len(anomalas),
        "sensibilidade": round(vp / (vp + fn), 3) if (vp + fn) else None,
        "precisao": round(vp / (vp + fp), 3) if (vp + fp) else None,
        "minutos_ate_primeiro_alerta_correto": None,
    }
    if anomalas and vp:
        inicio = min(anomalas)
        primeiro = min(criado_em[i] for i in sinalizadas & anomalas)
        m["minutos_ate_primeiro_alerta_correto"] = primeiro - inicio
    return m

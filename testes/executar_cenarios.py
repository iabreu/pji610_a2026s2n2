"""Executa os cenários de teste contra o banco real do projeto (Supabase/PostgreSQL).

Reproduz o mesmo caminho que a API percorre a cada leitura recebida:
    1. INSERT em pji610.leituras (dispara o gatilho do limiar fixo);
    2. SELECT pji610.fn_detectar_anomalias(dispositivo) (limiar dinâmico).
A única diferença é o carimbo de tempo, informado pelo script para reproduzir
150 minutos de operação em poucos minutos de execução.

Uso:
    export DATABASE_URL="postgresql://postgres.<ref>:<senha>@<host>:5432/postgres"
    python executar_cenarios.py                  # roda tudo
    python executar_cenarios.py --remover-testes # apaga dispositivos TESTE-* antes

Saídas (pasta ../resultados):
    results.json, leituras_<cenario>.csv, alertas.csv, fig_cenarios.png
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import secrets
import sys
import time
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).parent))
from cenarios import (LIMITES, N_LEITURAS, gerar_cenarios, metricas,  # noqa: E402
                      replicar_deteccao, replicar_fixo)

SAIDA = Path(__file__).resolve().parent.parent / "resultados"
PREFIXO = "TESTE-"


def conectar(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    ok = conn.execute(
        "select to_regprocedure('pji610.fn_detectar_anomalias(uuid)') is not null as ok"
    ).fetchone()["ok"]
    if not ok:
        sys.exit("Função pji610.fn_detectar_anomalias não encontrada. Confira o DATABASE_URL.")
    return conn


def criar_dispositivo(conn, nome: str) -> str:
    return conn.execute(
        """insert into pji610.dispositivos
               (nome, localizacao, api_key, temperatura_min, temperatura_max,
                umidade_min, umidade_max, z_limite, janela_baseline_minutos,
                intervalo_offline_segundos)
           values (%s, 'Cenário de teste - PI VI', %s, %s, %s, %s, %s, %s, %s, %s)
           returning id""",
        (nome, secrets.token_hex(32), LIMITES["temperatura_min"], LIMITES["temperatura_max"],
         LIMITES["umidade_min"], LIMITES["umidade_max"], LIMITES["z_limite"],
         LIMITES["janela_baseline_minutos"], LIMITES["intervalo_offline_segundos"]),
    ).fetchone()["id"]


def rodar_cenario(conn, cen) -> dict:
    dev = criar_dispositivo(conn, f"{PREFIXO}{cen.chave}")
    agora = conn.execute("select now() as t").fetchone()["t"]
    t0 = agora - timedelta(minutes=N_LEITURAS + 3)

    ids: list[str] = []
    criado_dyn_temp: dict[int, int] = {}
    criado_dyn_umid: dict[int, int] = {}
    inicio = time.time()

    for i in range(N_LEITURAS):
        lid = conn.execute(
            """insert into pji610.leituras
                   (dispositivo_id, temperatura, umidade, amostras, descartadas, registrado_em)
               values (%s, %s, %s, 6, 0, %s) returning id""",
            (dev, cen.temperatura[i], cen.umidade[i], t0 + timedelta(minutes=i)),
        ).fetchone()["id"]
        ids.append(str(lid))
        conn.execute("select pji610.fn_detectar_anomalias(%s)", (dev,))

        novos = conn.execute(
            """select leitura_id::text, tipo from pji610.alertas
               where dispositivo_id = %s and metodo = 'limiar_dinamico'""", (dev,)
        ).fetchall()
        idx = {v: k for k, v in enumerate(ids)}
        for a in novos:
            j = idx.get(a["leitura_id"])
            if j is None:
                continue
            alvo = criado_dyn_temp if a["tipo"] == "anomalia_temperatura" else criado_dyn_umid
            alvo.setdefault(j, i)

    duracao = time.time() - inicio
    idx = {v: k for k, v in enumerate(ids)}

    alertas = conn.execute(
        """select leitura_id::text, tipo, metodo, valor_medido::float, limite::float,
                  escore_z::float, registrado_em
           from pji610.alertas where dispositivo_id = %s order by registrado_em""", (dev,)
    ).fetchall()

    fixo_temp = {idx[a["leitura_id"]]: idx[a["leitura_id"]] for a in alertas
                 if a["metodo"] == "limiar_fixo" and a["tipo"].startswith("temperatura")}
    fixo_umid = [a for a in alertas if a["metodo"] == "limiar_fixo" and a["tipo"].startswith("umidade")]

    base = conn.execute(
        "select media_temperatura::float, desvio_temperatura::float, amostras from pji610.baselines where dispositivo_id = %s",
        (dev,),
    ).fetchone()

    # Conferência: o banco produziu o mesmo que a réplica?
    rep = replicar_deteccao(cen.temperatura, LIMITES["z_limite"])
    rep_fixo = replicar_fixo(cen.temperatura, LIMITES["temperatura_min"], LIMITES["temperatura_max"])
    loo = replicar_deteccao(cen.temperatura, LIMITES["z_limite"], excluir_propria=True)

    with open(SAIDA / f"leituras_{cen.chave}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["minuto", "temperatura", "umidade", "anomala_gabarito",
                    "alerta_fixo", "alerta_dinamico", "passo_alerta_dinamico"])
        for i in range(N_LEITURAS):
            w.writerow([i, cen.temperatura[i], cen.umidade[i], int(cen.anomala[i]),
                        int(i in fixo_temp), int(i in criado_dyn_temp),
                        criado_dyn_temp.get(i, "")])

    return {
        "chave": cen.chave,
        "titulo": cen.titulo,
        "descricao": cen.descricao,
        "dispositivo_id": str(dev),
        "duracao_execucao_s": round(duracao, 1),
        "marcos": cen.marcos,
        "linha_de_base_final": base,
        "temperatura": {
            "limiar_fixo": metricas(fixo_temp, cen.anomala),
            "limiar_dinamico": metricas(criado_dyn_temp, cen.anomala),
            "dinamico_excluindo_propria_leitura": metricas(loo, cen.anomala),
        },
        "umidade_alertas": {
            "limiar_fixo": len(fixo_umid),
            "limiar_dinamico": len(criado_dyn_umid),
        },
        "conferencia_replica": {
            "fixo_igual": set(fixo_temp) == set(rep_fixo),
            "dinamico_igual": criado_dyn_temp == rep,
            "so_no_banco": sorted(set(criado_dyn_temp) - set(rep)),
            "so_na_replica": sorted(set(rep) - set(criado_dyn_temp)),
        },
        "series": {
            "temperatura": cen.temperatura,
            "anomala": cen.anomala,
            "alerta_fixo": sorted(fixo_temp),
            "alerta_dinamico": sorted(criado_dyn_temp),
        },
        "_alertas": [dict(a, cenario=cen.chave, minuto=idx[a["leitura_id"]]) for a in alertas],
    }


def verificacoes_funcionais(conn) -> list[dict]:
    res = []

    # Leitura fisicamente impossível deve ser recusada pelo banco.
    dev = criar_dispositivo(conn, f"{PREFIXO}leitura_invalida")
    try:
        with conn.transaction():
            conn.execute(
                "insert into pji610.leituras (dispositivo_id, temperatura, umidade) values (%s, 150, 50)",
                (dev,),
            )
        res.append({"verificacao": "Leitura de 150 °C recusada pelo banco", "passou": False,
                    "detalhe": "a leitura foi aceita"})
    except psycopg.errors.CheckViolation as e:
        res.append({"verificacao": "Leitura de 150 °C recusada pelo banco", "passou": True,
                    "detalhe": e.diag.constraint_name or "violação de restrição"})

    # Interrupção do envio: dispositivo deve passar a offline e voltar a online.
    dev = criar_dispositivo(conn, f"{PREFIXO}interrupcao")
    agora = conn.execute("select now() as t").fetchone()["t"]
    for i in range(40):
        conn.execute(
            "insert into pji610.leituras (dispositivo_id, temperatura, umidade, registrado_em) values (%s, 23, 50, %s)",
            (dev, agora - timedelta(minutes=55 - i)),
        )
    st1 = conn.execute("select status from pji610.vw_dispositivos_status where id = %s", (dev,)).fetchone()["status"]
    conn.execute("insert into pji610.leituras (dispositivo_id, temperatura, umidade) values (%s, 23, 50)", (dev,))
    st2 = conn.execute("select status from pji610.vw_dispositivos_status where id = %s", (dev,)).fetchone()["status"]
    res.append({"verificacao": "Dispositivo sem envio há 15 min aparece como offline", "passou": st1 == "offline", "detalhe": st1})
    res.append({"verificacao": "Dispositivo volta a online após nova leitura", "passou": st2 == "online", "detalhe": st2})
    return res


def verificacao_api(api_url: str, api_key: str) -> list[dict]:
    import urllib.error
    import urllib.request

    def post(corpo: dict) -> int:
        req = urllib.request.Request(
            api_url.rstrip("/") + "/leituras", data=json.dumps(corpo).encode(),
            headers={"Content-Type": "application/json", "X-API-Key": api_key}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    r1 = post({"temperatura": 150, "umidade": 50})
    r2 = post({"temperatura": 23.4, "umidade": 51.0, "amostras": 6, "descartadas": 0})
    r3 = None
    req = urllib.request.Request(api_url.rstrip("/") + "/leituras",
                                 data=json.dumps({"temperatura": 23, "umidade": 50}).encode(),
                                 headers={"Content-Type": "application/json", "X-API-Key": "chave-invalida"},
                                 method="POST")
    try:
        urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as e:
        r3 = e.code
    return [
        {"verificacao": "API recusa temperatura de 150 °C (HTTP 422)", "passou": r1 == 422, "detalhe": r1},
        {"verificacao": "API aceita leitura válida (HTTP 201)", "passou": r2 == 201, "detalhe": r2},
        {"verificacao": "API recusa chave de dispositivo inválida (HTTP 401)", "passou": r3 == 401, "detalhe": r3},
    ]


def figura(resultados: list[dict], caminho: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5})
    fig, eixos = plt.subplots(2, 2, figsize=(10, 6.2), dpi=220, sharey=True)
    for ax, r in zip(eixos.flat, resultados):
        s = r["series"]
        x = list(range(len(s["temperatura"])))
        ax.plot(x, s["temperatura"], color="#3a3a3a", linewidth=0.9, zorder=2, label="Leituras")
        ax.axhline(LIMITES["temperatura_max"], color="#b03a2e", linestyle="--", linewidth=1.1,
                   zorder=1, label="Limiar fixo (27 °C)")
        for i, a in enumerate(s["anomala"]):
            if a:
                ax.axvspan(i - 0.5, i + 0.5, color="#f3d9a4", alpha=0.6, zorder=0, linewidth=0)
        fx, dn = s["alerta_fixo"], s["alerta_dinamico"]
        ax.scatter(fx, [s["temperatura"][i] for i in fx], marker="x", s=34, color="#b03a2e",
                   zorder=4, label="Alerta do limiar fixo")
        ax.scatter(dn, [s["temperatura"][i] for i in dn], marker="o", s=26, facecolors="none",
                   edgecolors="#2f6a9e", linewidths=1.2, zorder=5, label="Alerta do limiar dinâmico")
        ax.set_title(r["titulo"], fontsize=9.5)
        ax.grid(True, linewidth=0.3, alpha=0.5)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
    for ax in eixos[1]:
        ax.set_xlabel("Tempo (min)")
    for ax in eixos[:, 0]:
        ax.set_ylabel("Temperatura (°C)")
    from matplotlib.patches import Patch
    h, l = eixos[0, 0].get_legend_handles_labels()
    h.append(Patch(facecolor="#f3d9a4", alpha=0.6)); l.append("Anômala no gabarito")
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(caminho, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--remover-testes", action="store_true",
                    help="apaga dispositivos com nome TESTE-* antes de rodar")
    ap.add_argument("--api-url", default=os.environ.get("API_URL"))
    ap.add_argument("--api-key", default=os.environ.get("API_KEY"))
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args()
    if not args.database_url:
        sys.exit("Informe DATABASE_URL (variável de ambiente ou --database-url).")

    SAIDA.mkdir(parents=True, exist_ok=True)
    conn = conectar(args.database_url)

    if args.remover_testes:
        n = conn.execute("delete from pji610.dispositivos where nome like %s", (PREFIXO + "%",)).rowcount
        print(f"Removidos {n} dispositivos de teste anteriores.")

    resultados = []
    for cen in gerar_cenarios(args.semente):
        print(f"Rodando cenário: {cen.titulo} ...", flush=True)
        r = rodar_cenario(conn, cen)
        print(f"  ok em {r['duracao_execucao_s']} s | fixo={r['temperatura']['limiar_fixo']['alertas']} "
              f"dinâmico={r['temperatura']['limiar_dinamico']['alertas']} "
              f"| réplica confere: {r['conferencia_replica']['dinamico_igual']}")
        resultados.append(r)

    func = verificacoes_funcionais(conn)
    if args.api_url:
        chave = args.api_key
        if not chave:
            # usa a chave de um dispositivo de teste, para não misturar leituras com o dispositivo real
            dev_api = criar_dispositivo(conn, f"{PREFIXO}api")
            chave = conn.execute("select api_key from pji610.dispositivos where id = %s",
                                 (dev_api,)).fetchone()["api_key"]
        func += verificacao_api(args.api_url, chave)

    alertas = [a for r in resultados for a in r.pop("_alertas")]
    with open(SAIDA / "alertas.csv", "w", newline="", encoding="utf-8") as f:
        campos = ["cenario", "minuto", "tipo", "metodo", "valor_medido", "limite", "escore_z", "registrado_em", "leitura_id"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for a in alertas:
            w.writerow({k: a.get(k) for k in campos})

    figura(resultados, SAIDA / "fig_cenarios.png")

    versao = conn.execute("select current_setting('server_version') as v").fetchone()["v"]
    executado = conn.execute("select now() as t").fetchone()["t"]
    saida = {
        "executado_em": executado.isoformat(),
        "postgres": versao,
        "semente": args.semente,
        "parametros": {**LIMITES, "leituras_por_cenario": N_LEITURAS, "intervalo_min": 1},
        "cenarios": resultados,
        "verificacoes_funcionais": func,
    }
    with open(SAIDA / "results.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2, default=str)

    print("\nVerificações funcionais:")
    for v in func:
        print(f"  [{'OK' if v['passou'] else 'FALHOU'}] {v['verificacao']} ({v['detalhe']})")
    print(f"\nResultados gravados em {SAIDA}")


if __name__ == "__main__":
    main()

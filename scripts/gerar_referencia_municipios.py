"""Gera os arquivos de referência dos 92 municípios do RJ a partir das APIs do IBGE.

Uso único, em desenvolvimento. Os dois artefatos gerados são versionados para que o
app rode offline, sem depender do IBGE no deploy:

    data/malha_municipios_rj.json   malha municipal (GeoJSON, ~47 KB)
    data/municipios_rj.csv          cod_ibge, municipio, populacao

Rode a partir da raiz do repositório:

    python scripts/gerar_referencia_municipios.py
"""

from __future__ import annotations

import csv
import json
import logging
import os
import ssl
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

UF_RJ = "33"

# A malha sai com uma propriedade só, `codarea`, que é o código IBGE de 7 dígitos —
# o mesmo valor da coluna `fmun_cod` do CSV do ISP. É o que permite o join sem
# depender de nome (imune a acento e a mudança de grafia).
URL_MALHA = (
    f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{UF_RJ}"
    "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima"
)

# Censo 2022, agregado 4709, variável 93 = população residente.
URL_POP = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/4709/periodos/2022/variaveis/93"
    "?localidades=" + urllib.parse.quote(f"N6[N3[{UF_RJ}]]", safe="")
)

MUNICIPIOS_RJ = 92


def _baixar(url: str) -> bytes:
    """Mesmo padrão de garantir_dados_isp(): User-Agent, contexto SSL e timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=90) as resp:
        return resp.read()


def gerar_malha(path: str = "data/malha_municipios_rj.json") -> int:
    bruto = _baixar(URL_MALHA)
    geo = json.loads(bruto)
    feats = geo.get("features", [])
    if len(feats) != MUNICIPIOS_RJ:
        raise ValueError(f"Esperava {MUNICIPIOS_RJ} municípios na malha, recebi {len(feats)}.")
    if not all(f.get("properties", {}).get("codarea") for f in feats):
        raise ValueError("Alguma feature veio sem a propriedade 'codarea'.")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # separators sem espaço: a malha é o maior arquivo versionado aqui.
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(geo, fh, ensure_ascii=False, separators=(",", ":"))
    logger.info("Malha gravada em %s (%d municípios, %d bytes)",
                path, len(feats), os.path.getsize(path))
    return len(feats)


def gerar_populacao(path: str = "data/municipios_rj.csv") -> int:
    dados = json.loads(_baixar(URL_POP))
    series = dados[0]["resultados"][0]["series"]
    if len(series) != MUNICIPIOS_RJ:
        raise ValueError(f"Esperava {MUNICIPIOS_RJ} municípios na população, recebi {len(series)}.")

    linhas = []
    for s in series:
        loc = s["localidade"]
        # A API devolve "Angra dos Reis - RJ"; o sufixo de UF é redundante aqui.
        nome = loc["nome"].rsplit(" - ", 1)[0].strip()
        (valor,) = s["serie"].values()
        linhas.append((loc["id"], nome, int(valor)))
    linhas.sort(key=lambda r: r[1])

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cod_ibge", "municipio", "populacao"])
        w.writerows(linhas)
    logger.info("População gravada em %s (%d municípios)", path, len(linhas))
    return len(linhas)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        n_malha = gerar_malha()
        n_pop = gerar_populacao()
    except Exception as e:
        logger.error("Falhou: %s", e)
        return 1
    print(f"OK — malha: {n_malha} municípios, população: {n_pop} municípios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

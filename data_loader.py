"""Carrega e normaliza os dados de roubo de carga (ISP-RJ, mensal por município)."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.request

import pandas as pd

logger = logging.getLogger(__name__)

ISP_URL = "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv"

MUNICIPIOS_RJ = 92

COLUNAS = ["id", "cod_ibge", "municipio", "regiao", "ano", "mes", "qtd", "fonte"]

# O CSV do ISP traz `fmun_cod`, que é o código IBGE de 7 dígitos: 1:1 com o nome e
# estável. Todo join (malha, população) é feito por ele, nunca por nome — assim uma
# mudança de acento ou grafia na base do ISP não derruba nenhum município.
_COL_COD = ["fmun_cod", "cod", "codigo", "cod_ibge"]
_COL_MUNIC = ["fmun", "munic", "municipio", "município", "mun"]
_COL_CARGA = ["roubo_carga", "roubo_de_carga", "roubocarga"]

_INSTRUCAO_REFERENCIA = (
    "Gere os arquivos de referência do IBGE com: "
    "python scripts/gerar_referencia_municipios.py"
)


def garantir_dados_isp(path: str = "data/BaseMunicipioMensal.csv") -> str:
    """Baixa o CSV do ISP se ainda não existir (necessário no deploy)."""
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        req = urllib.request.Request(ISP_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=90) as resp:
            conteudo = resp.read()
        with open(path, "wb") as f:
            f.write(conteudo)
        logger.info("Dados do ISP baixados: %d bytes", len(conteudo))
    except Exception as e:
        logger.warning("Não consegui baixar o CSV do ISP: %s", e)
    return path


def _achar_coluna(cols, candidatos):
    low = {c.lower().strip(): c for c in cols}
    for cand in candidatos:
        if cand in low:
            return low[cand]
    return None


def load_isp_municipio(path: str = "data/BaseMunicipioMensal.csv") -> pd.DataFrame:
    """Lê o BaseMunicipioMensal.csv do ISP e devolve o esquema unificado.

    Todos os municípios presentes no CSV são preservados: o total devolvido fecha com
    o total da coluna `roubo_carga` da entrada. Não há lista fixa de municípios.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} não encontrado. Baixe em "
            "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv"
        )

    raw = None
    for sep, enc in ((";", "latin-1"), (";", "utf-8"), (",", "latin-1")):
        try:
            tmp = pd.read_csv(path, sep=sep, encoding=enc)
            if tmp.shape[1] > 1:
                raw = tmp
                break
        except Exception:
            continue
    if raw is None:
        raise ValueError("Não consegui ler o CSV do ISP (separador/encoding).")

    col_cod = _achar_coluna(raw.columns, _COL_COD)
    col_mun = _achar_coluna(raw.columns, _COL_MUNIC)
    col_carga = _achar_coluna(raw.columns, _COL_CARGA)
    col_mes = _achar_coluna(raw.columns, ["mes", "mês"])
    col_ano = _achar_coluna(raw.columns, ["ano"])
    if not (col_cod and col_mun and col_carga and col_mes and col_ano):
        raise ValueError(f"Colunas esperadas não encontradas. Presentes: {list(raw.columns)}")

    col_regiao = _achar_coluna(raw.columns, ["regiao", "região"])

    usadas = [col_cod, col_mun, col_ano, col_mes, col_carga]
    nomes = ["cod_ibge", "municipio", "ano", "mes", "qtd"]
    if col_regiao:
        usadas.append(col_regiao)
        nomes.append("regiao")

    df = raw[usadas].copy()
    df.columns = nomes
    if not col_regiao:
        df["regiao"] = pd.NA

    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0).astype(int)
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce")
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df = df[(df["qtd"] > 0) & df["mes"].notna() & df["ano"].notna()]

    # Código como string: é identificador, não número. Evita que um zero à esquerda
    # ou uma conversão para float corrompa o join com a malha e a população.
    df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip().str.split(".").str[0]
    df["municipio"] = df["municipio"].astype(str).str.strip()
    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df["id"] = range(1, len(df) + 1)
    df["fonte"] = "isp"
    return df[COLUNAS].reset_index(drop=True)


def carregar_malha(path: str = "data/malha_municipios_rj.json") -> dict:
    """Devolve a malha municipal do RJ (GeoJSON do IBGE) usada no mapa coroplético."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} não encontrado. {_INSTRUCAO_REFERENCIA}")
    with open(path, encoding="utf-8") as fh:
        geo = json.load(fh)
    n = len(geo.get("features", []))
    if n != MUNICIPIOS_RJ:
        logger.warning("Malha com %d municípios (esperado %d).", n, MUNICIPIOS_RJ)
    return geo


def carregar_populacao(path: str = "data/municipios_rj.csv") -> pd.DataFrame:
    """Devolve cod_ibge, municipio e populacao (Censo 2022 do IBGE)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} não encontrado. {_INSTRUCAO_REFERENCIA}")
    pop = pd.read_csv(path, dtype={"cod_ibge": str})
    faltando = {"cod_ibge", "municipio", "populacao"} - set(pop.columns)
    if faltando:
        raise ValueError(f"{path} sem as colunas {sorted(faltando)}.")
    pop["cod_ibge"] = pop["cod_ibge"].str.strip()
    pop["populacao"] = pd.to_numeric(pop["populacao"], errors="coerce")
    return pop[["cod_ibge", "municipio", "populacao"]]


def ranking_municipios(df: pd.DataFrame, populacao: pd.DataFrame | None = None,
                       por_100k: bool = False) -> pd.DataFrame:
    """Agrega por município e ordena por volume ou por taxa por 100 mil habitantes.

    Devolve cod_ibge, municipio, qtd e — quando houver população — populacao e taxa.
    Município sem população conhecida fica com taxa nula e sai da ordenação por taxa,
    em vez de aparecer como zero (que leria como "sem risco").
    """
    rank = (df.groupby(["cod_ibge", "municipio"], as_index=False)["qtd"].sum())

    if populacao is not None:
        rank = rank.merge(populacao[["cod_ibge", "populacao"]], on="cod_ibge", how="left")
        pop_valida = rank["populacao"].where(rank["populacao"] > 0)
        rank["taxa"] = 1e5 * rank["qtd"] / pop_valida
        sem_pop = rank["taxa"].isna().sum()
        if sem_pop:
            logger.warning("%d município(s) sem população conhecida.", sem_pop)

    if por_100k:
        if "taxa" not in rank.columns:
            raise ValueError("Ordenação por 100 mil habitantes exige a tabela de população.")
        rank = rank.dropna(subset=["taxa"]).sort_values("taxa", ascending=False)
    else:
        rank = rank.sort_values("qtd", ascending=False)

    return rank.reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    d = load_isp_municipio()
    print(f"{len(d)} linhas carregadas, {d['cod_ibge'].nunique()} municípios")
    print(ranking_municipios(d, carregar_populacao(), por_100k=False).head(10).to_string(index=False))

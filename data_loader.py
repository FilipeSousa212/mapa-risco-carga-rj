"""Carrega e normaliza os dados de roubo de carga (ISP-RJ, mensal por município)."""

from __future__ import annotations

import logging
import os

import pandas as pd

import logging
import ssl
import urllib.request

logger = logging.getLogger(__name__)

ISP_URL = "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv"


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

logger = logging.getLogger(__name__)

COLUNAS = ["id", "data", "ano", "mes", "dia_semana", "hora",
           "lat", "lon", "municipio", "corredor", "qtd", "fonte"]

CENTROIDES_MUNIC = {
    "Rio de Janeiro": (-22.9068, -43.1729), "Duque de Caxias": (-22.7856, -43.3117),
    "São João de Meriti": (-22.8039, -43.3722), "Nova Iguaçu": (-22.7592, -43.4510),
    "Belford Roxo": (-22.7642, -43.3993), "Nilópolis": (-22.8075, -43.4136),
    "Mesquita": (-22.7833, -43.4292), "Queimados": (-22.7166, -43.5552),
    "Japeri": (-22.6433, -43.6533), "São Gonçalo": (-22.8268, -43.0634),
    "Niterói": (-22.8832, -43.1034), "Itaboraí": (-22.7444, -42.8592),
    "Magé": (-22.6531, -43.0408), "Itaguaí": (-22.8523, -43.7758),
    "Seropédica": (-22.7440, -43.7075), "Nova Friburgo": (-22.2820, -42.5310),
    "Petrópolis": (-22.5050, -43.1786), "Volta Redonda": (-22.5231, -44.1041),
    "Barra Mansa": (-22.5443, -44.1719), "Resende": (-22.4686, -44.4466),
    "Campos dos Goytacazes": (-21.7545, -41.3244), "Macaé": (-22.3708, -41.7869),
    "Cabo Frio": (-22.8894, -42.0286), "Angra dos Reis": (-23.0067, -44.3181),
    "Maricá": (-22.9194, -42.8186), "Rio das Ostras": (-22.5267, -41.9450),
    "Teresópolis": (-22.4120, -42.9660), "Três Rios": (-22.1167, -43.2094),
    "Paracambi": (-22.6089, -43.7108), "Guapimirim": (-22.5350, -42.9892),
}

_COL_MUNIC = ["fmun", "munic", "municipio", "município", "mun"]
_COL_CARGA = ["roubo_carga", "roubo_de_carga", "roubocarga"]


def _achar_coluna(cols, candidatos):
    low = {c.lower().strip(): c for c in cols}
    for cand in candidatos:
        if cand in low:
            return low[cand]
    return None


def load_isp_municipio(path: str = "data/BaseMunicipioMensal.csv") -> pd.DataFrame:
    """Lê o BaseMunicipioMensal.csv do ISP e devolve o esquema unificado."""
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

    col_mun = _achar_coluna(raw.columns, _COL_MUNIC)
    col_carga = _achar_coluna(raw.columns, _COL_CARGA)
    col_mes = _achar_coluna(raw.columns, ["mes", "mês"])
    col_ano = _achar_coluna(raw.columns, ["ano"])
    if not (col_mun and col_carga and col_mes and col_ano):
        raise ValueError(f"Colunas esperadas não encontradas. Presentes: {list(raw.columns)}")

    df = raw[[col_mun, col_ano, col_mes, col_carga]].copy()
    df.columns = ["municipio", "ano", "mes", "qtd"]
    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0).astype(int)
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce")
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df = df[(df["qtd"] > 0) & df["mes"].notna() & df["ano"].notna()]

    df["municipio"] = df["municipio"].astype(str).str.strip()
    faltando = sorted(set(df["municipio"]) - set(CENTROIDES_MUNIC))
    if faltando:
        logger.warning("Municípios sem centroide (ignorados): %s", faltando[:10])
    df = df[df["municipio"].isin(CENTROIDES_MUNIC)]

    df["lat"] = df["municipio"].map(lambda m: CENTROIDES_MUNIC[m][0])
    df["lon"] = df["municipio"].map(lambda m: CENTROIDES_MUNIC[m][1])
    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df["dia_semana"] = pd.NA
    df["hora"] = pd.NA
    df["corredor"] = df["municipio"]
    df["data"] = pd.NA
    df["id"] = range(1, len(df) + 1)
    df["fonte"] = "isp"
    return df[COLUNAS]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    d = load_isp_municipio()
    print(f"{len(d)} linhas carregadas")
    print(d.groupby("municipio")["qtd"].sum().sort_values(ascending=False).head(10))
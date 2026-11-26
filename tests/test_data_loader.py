"""Testes do data_loader: esquema, coerção, erros e cobertura de municípios.

Usam CSV sintético em tmp_path — não dependem do download do ISP nem do IBGE.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import data_loader

# Inclui de propósito municípios que a versão antiga do loader descartava
# (Piraí, Araruama, Silva Jardim, Mangaratiba) ao lado de dois que ela mantinha.
LINHAS = [
    # fmun_cod, fmun,               ano,  mes, regiao,               roubo_carga
    ("3304557", "Rio de Janeiro",   2025, 1, "Capital",            100),
    ("3301702", "Duque de Caxias",  2025, 1, "Baixada Fluminense",  50),
    ("3304003", "Piraí",            2025, 1, "Interior",             9),
    ("3300209", "Araruama",         2025, 1, "Interior",             4),
    ("3305505", "Silva Jardim",     2025, 1, "Interior",             3),
    ("3302601", "Mangaratiba",      2025, 1, "Interior",             1),
    ("3304557", "Rio de Janeiro",   2025, 2, "Capital",             80),
    ("3304003", "Piraí",            2025, 2, "Interior",             7),
    ("3300100", "Angra dos Reis",   2025, 2, "Interior",             0),  # zero: sai
]

CABECALHO = ["fmun_cod", "fmun", "ano", "mes", "regiao", "roubo_carga"]


def _escrever_csv(path, linhas=LINHAS, cabecalho=CABECALHO, sep=";", enc="latin-1"):
    """Grava um CSV no formato do ISP (aspas, ponto e vírgula, latin-1)."""
    with open(path, "w", encoding=enc, newline="") as fh:
        fh.write(sep.join(f'"{c}"' for c in cabecalho) + "\n")
        for linha in linhas:
            fh.write(sep.join(str(v) for v in linha) + "\n")
    return str(path)


@pytest.fixture
def csv_isp(tmp_path):
    return _escrever_csv(tmp_path / "base.csv")


@pytest.fixture
def populacao(tmp_path):
    path = tmp_path / "municipios_rj.csv"
    pd.DataFrame({
        "cod_ibge": ["3304557", "3301702", "3304003", "3300209", "3305505"],
        "municipio": ["Rio de Janeiro", "Duque de Caxias", "Piraí", "Araruama",
                      "Silva Jardim"],
        "populacao": [6211223, 808161, 27474, 129671, 21352],
    }).to_csv(path, index=False)
    # Mangaratiba de fora de propósito: exercita o caminho "sem população".
    return data_loader.carregar_populacao(str(path))


# --------------------------------------------------------------------------- #
# Cobertura — o teste que trava a regressão dos 30 municípios
# --------------------------------------------------------------------------- #

def test_nenhum_municipio_e_descartado(csv_isp):
    """Todo município com ocorrência na entrada tem de sobreviver ao load."""
    df = data_loader.load_isp_municipio(csv_isp)
    esperados = {nome for _, nome, _, _, _, qtd in LINHAS if qtd > 0}
    assert set(df["municipio"]) == esperados
    # Os quatro que a lista fixa antiga não continha:
    for nome in ("Piraí", "Araruama", "Silva Jardim", "Mangaratiba"):
        assert nome in set(df["municipio"]), f"{nome} foi descartado silenciosamente"


def test_total_fecha_com_a_entrada(csv_isp):
    """A soma devolvida tem de ser igual à soma de roubo_carga do CSV."""
    df = data_loader.load_isp_municipio(csv_isp)
    assert int(df["qtd"].sum()) == sum(qtd for *_, qtd in LINHAS)


def test_municipio_novo_na_base_e_preservado(tmp_path):
    """Um código desconhecido não pode virar motivo de descarte."""
    linhas = LINHAS + [("3399999", "Município Novo", 2025, 3, "Interior", 42)]
    df = data_loader.load_isp_municipio(_escrever_csv(tmp_path / "novo.csv", linhas))
    assert "Município Novo" in set(df["municipio"])
    assert int(df.loc[df["municipio"] == "Município Novo", "qtd"].iloc[0]) == 42


# --------------------------------------------------------------------------- #
# Esquema e tipos
# --------------------------------------------------------------------------- #

def test_esquema_de_colunas(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    assert list(df.columns) == data_loader.COLUNAS


def test_tipos(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    assert df["cod_ibge"].map(type).eq(str).all(), "cod_ibge tem de ser string"
    for col in ("ano", "mes", "qtd"):
        assert pd.api.types.is_integer_dtype(df[col]), f"{col} deveria ser inteiro"


def test_regiao_preservada(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    assert df.loc[df["municipio"] == "Rio de Janeiro", "regiao"].iloc[0] == "Capital"


def test_regiao_ausente_nao_quebra(tmp_path):
    cab = ["fmun_cod", "fmun", "ano", "mes", "roubo_carga"]
    linhas = [(c, n, a, m, q) for c, n, a, m, _, q in LINHAS]
    df = data_loader.load_isp_municipio(
        _escrever_csv(tmp_path / "sem_regiao.csv", linhas, cab))
    assert df["regiao"].isna().all()
    assert len(df) == sum(1 for *_, q in linhas if q > 0)


# --------------------------------------------------------------------------- #
# Coerção e filtragem
# --------------------------------------------------------------------------- #

def test_zeros_sao_filtrados(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    assert "Angra dos Reis" not in set(df["municipio"])
    assert (df["qtd"] > 0).all()


def test_qtd_nao_numerica_vira_zero_e_sai(tmp_path):
    linhas = [("3304557", "Rio de Janeiro", 2025, 1, "Capital", "n/d"),
              ("3304003", "Piraí", 2025, 1, "Interior", 5)]
    df = data_loader.load_isp_municipio(_escrever_csv(tmp_path / "ndq.csv", linhas))
    assert set(df["municipio"]) == {"Piraí"}


def test_linhas_sem_ano_ou_mes_caem(tmp_path):
    linhas = [("3304557", "Rio de Janeiro", "", 1, "Capital", 10),
              ("3301702", "Duque de Caxias", 2025, "", "Baixada Fluminense", 10),
              ("3304003", "Piraí", 2025, 1, "Interior", 5)]
    df = data_loader.load_isp_municipio(_escrever_csv(tmp_path / "vazios.csv", linhas))
    assert set(df["municipio"]) == {"Piraí"}


def test_codigo_nao_perde_formato(tmp_path):
    """Código lido como float não pode chegar ao join como '3304557.0'."""
    linhas = [("3304557.0", "Rio de Janeiro", 2025, 1, "Capital", 10)]
    df = data_loader.load_isp_municipio(_escrever_csv(tmp_path / "float.csv", linhas))
    assert df["cod_ibge"].iloc[0] == "3304557"


@pytest.mark.parametrize("sep,enc", [(";", "latin-1"), (";", "utf-8"), (",", "latin-1")])
def test_combinacoes_de_separador_e_encoding(tmp_path, sep, enc):
    path = _escrever_csv(tmp_path / f"base_{sep}_{enc}.csv", sep=sep, enc=enc)
    df = data_loader.load_isp_municipio(path)
    assert int(df["qtd"].sum()) == sum(qtd for *_, qtd in LINHAS)


# --------------------------------------------------------------------------- #
# Erros
# --------------------------------------------------------------------------- #

def test_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        data_loader.load_isp_municipio(str(tmp_path / "nao_existe.csv"))


def test_coluna_obrigatoria_ausente(tmp_path):
    cab = ["fmun_cod", "fmun", "ano", "mes", "regiao", "outra_coisa"]
    with pytest.raises(ValueError, match="Colunas esperadas"):
        data_loader.load_isp_municipio(_escrever_csv(tmp_path / "ruim.csv", cabecalho=cab))


def test_malha_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError, match="gerar_referencia_municipios"):
        data_loader.carregar_malha(str(tmp_path / "nao_existe.json"))


def test_populacao_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError, match="gerar_referencia_municipios"):
        data_loader.carregar_populacao(str(tmp_path / "nao_existe.csv"))


def test_populacao_sem_colunas(tmp_path):
    path = tmp_path / "pop_ruim.csv"
    pd.DataFrame({"cod_ibge": ["3304557"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="populacao"):
        data_loader.carregar_populacao(str(path))


# --------------------------------------------------------------------------- #
# Ranking e taxa por 100 mil
# --------------------------------------------------------------------------- #

def test_ranking_por_volume(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    rank = data_loader.ranking_municipios(df)
    assert list(rank["municipio"][:3]) == ["Rio de Janeiro", "Duque de Caxias", "Piraí"]
    assert int(rank["qtd"].iloc[0]) == 180  # 100 + 80


def test_taxa_por_100k_inverte_o_ranking(csv_isp, populacao):
    """Piraí tem 16 ocorrências contra 180 do Rio, mas 1/226 da população."""
    df = data_loader.load_isp_municipio(csv_isp)
    rank = data_loader.ranking_municipios(df, populacao, por_100k=True)
    assert rank["municipio"].iloc[0] == "Piraí"
    assert rank["taxa"].iloc[0] == pytest.approx(1e5 * 16 / 27474, rel=1e-6)
    assert list(rank["municipio"]).index("Rio de Janeiro") > 0


def test_municipio_sem_populacao_sai_da_taxa(csv_isp, populacao):
    """Mangaratiba não está na tabela de população: não pode aparecer como 0."""
    df = data_loader.load_isp_municipio(csv_isp)
    com_taxa = data_loader.ranking_municipios(df, populacao, por_100k=True)
    assert "Mangaratiba" not in set(com_taxa["municipio"])
    # No ranking por volume ele continua presente, só sem taxa.
    por_volume = data_loader.ranking_municipios(df, populacao, por_100k=False)
    assert "Mangaratiba" in set(por_volume["municipio"])
    assert pd.isna(por_volume.loc[por_volume["municipio"] == "Mangaratiba", "taxa"].iloc[0])


def test_taxa_exige_populacao(csv_isp):
    df = data_loader.load_isp_municipio(csv_isp)
    with pytest.raises(ValueError, match="população"):
        data_loader.ranking_municipios(df, None, por_100k=True)


# --------------------------------------------------------------------------- #
# Artefatos versionados do IBGE
# --------------------------------------------------------------------------- #

def test_malha_versionada_cobre_os_92_municipios():
    malha = data_loader.carregar_malha()
    feats = malha["features"]
    assert len(feats) == data_loader.MUNICIPIOS_RJ
    assert all(f["properties"].get("codarea") for f in feats)


def test_populacao_versionada_cobre_os_92_municipios():
    pop = data_loader.carregar_populacao()
    assert len(pop) == data_loader.MUNICIPIOS_RJ
    assert pop["populacao"].gt(0).all()
    assert pop["cod_ibge"].is_unique


def test_malha_e_populacao_usam_os_mesmos_codigos():
    """O join do coroplético depende dessa igualdade."""
    malha = data_loader.carregar_malha()
    codigos_malha = {f["properties"]["codarea"] for f in malha["features"]}
    assert codigos_malha == set(data_loader.carregar_populacao()["cod_ibge"])


def test_codigos_do_isp_existem_na_referencia():
    """Nenhum município do ISP pode ficar sem polígono nem sem população."""
    df = data_loader.load_isp_municipio()
    referencia = set(data_loader.carregar_populacao()["cod_ibge"])
    assert set(df["cod_ibge"]) <= referencia

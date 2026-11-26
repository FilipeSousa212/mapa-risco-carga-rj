"""Dashboard — risco de roubo de carga no RJ (dados reais do ISP, mensal por município)."""

from __future__ import annotations

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from branca.colormap import StepColormap

import data_loader

st.set_page_config(page_title="Risco de Roubo de Carga — RJ", layout="wide")
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
POR_100K = "Por 100 mil habitantes"

# Rampa sequencial de uma só hue (azul 200→700), clara→escura. Multi-hue tipo
# YlOrRd é rampa-arco-íris: a ordem das cores não é lida como ordem de grandeza.
# O azul também separa melhor do basemap cinza e do cinza de "sem ocorrência".
# Cinco passos a partir do 300, não seis a partir do 200: o passo 200 tinha a mesma
# luminosidade do cinza de "sem ocorrência" (1,4:1 entre os dois, indistinguíveis),
# e com cinco classes os intervalos ficam maiores. Nesta forma o ramp passa todos
# os checks de rampa ordinal, inclusive a ponta clara contra o cinza do basemap.
RAMPA = ["#6aabf1", "#338ced", "#2370cd", "#1757ac", "#0e3d7e"]
COR_ZERO = "#efefef"      # município sem ocorrência no recorte: fora da rampa
COR_BORDA = "#9c9c9c"     # borda neutra: legível sobre fundo claro e sobre azul escuro
COR_SERIE = "#257de0"     # série única dos gráficos de barra, mesma família do mapa

# Faixas fixas, em passos ~logarítmicos. Duas razões para serem fixas e não por
# quantil: o dado é muito assimétrico (mediana 4, máximo 1.496 em 2025), e com
# faixas fixas uma cor significa sempre a mesma coisa — dá para comparar 2024 com
# 2025 a olho. Faixas por quantil se re-ancoram a cada filtro e repintariam
# municípios cujo valor não mudou.
FAIXAS_VOLUME = [1, 3, 12, 50, 200]
FAIXAS_TAXA = [0.5, 2, 6, 20, 60]
_TETO = float("inf")


def _num(x: float) -> str:
    """1.0 -> '1'; 0.5 -> '0,5' (vírgula decimal)."""
    return (f"{x:g}" if x == int(x) else f"{x:.1f}").replace(".", ",")


def rotulos_faixas(faixas: list[float], inteiro: bool) -> list[str]:
    """['1–2', '3–9', ..., '300+'] — o que cada cor da rampa significa."""
    rots = []
    for i, ini in enumerate(faixas):
        if i + 1 == len(faixas):
            rots.append(f"{_num(ini)}+")
        else:
            fim = faixas[i + 1]
            # Contagem é discreta (3–9); taxa é contínua, então o limite superior
            # é aberto e mostrar "2–5" com o 5 na faixa seguinte seria ambíguo.
            rots.append(f"{_num(ini)}–{_num(fim - 1)}" if inteiro
                        else f"{_num(ini)}–{_num(fim)}")
    return rots


def legenda_html(faixas: list[float], inteiro: bool, titulo: str) -> str:
    """Legenda de escala própria, com uma célula por classe, todas da mesma largura.

    A legenda do branca desenha um eixo linear entre o primeiro e o último limite,
    o que esmaga as faixas baixas (1–3 virava um fio e 100–300 ocupava metade da
    barra) e não tem como mostrar o cinza de "sem ocorrência".
    """
    celulas = "".join(
        f'<div style="flex:1;min-width:0"><div style="height:12px;background:{cor};'
        f'border:1px solid rgba(0,0,0,.08)"></div>'
        f'<div style="font-size:11px;color:#666;text-align:center;padding-top:3px">{rot}</div></div>'
        for cor, rot in zip(RAMPA, rotulos_faixas(faixas, inteiro)))
    return (
        f'<div style="font-size:12px;color:#666;padding-bottom:4px">{titulo}</div>'
        f'<div style="display:flex;gap:2px;align-items:flex-end">{celulas}'
        f'<div style="width:14px"></div>'
        f'<div style="flex:1;min-width:0"><div style="height:12px;background:{COR_ZERO};'
        f'border:1px solid rgba(0,0,0,.08)"></div>'
        f'<div style="font-size:11px;color:#666;text-align:center;padding-top:3px">nenhuma</div></div>'
        f'</div>')


@st.cache_data
def carregar() -> pd.DataFrame:
    # garantir_dados_isp devolve o caminho; repassá-lo evita que os dois
    # defaults divirjam se um dia mudar só um deles.
    caminho = data_loader.garantir_dados_isp()   # baixa o CSV se não existir (deploy)
    return data_loader.load_isp_municipio(caminho)


@st.cache_data
def carregar_populacao() -> pd.DataFrame:
    return data_loader.carregar_populacao()


@st.cache_data
def carregar_malha() -> dict:
    return data_loader.carregar_malha()


st.title("🚚 Mapa de risco de roubo de carga — Rio de Janeiro")

try:
    df = carregar()
    pop = carregar_populacao()
    malha = carregar_malha()
except Exception as e:
    st.error(str(e))
    st.stop()

with st.sidebar:
    st.header("Filtros")
    anos = sorted(df["ano"].unique(), reverse=True)
    ano_sel = st.selectbox("Ano", options=anos, index=0)  # padrão: ano mais recente
    meses_sel = st.multiselect("Mês", options=list(range(1, 13)),
                               format_func=lambda m: MESES[m - 1],
                               default=list(range(1, 13)))
    metrica = st.radio("Ordenar por", ["Volume absoluto", POR_100K])
    st.caption("A taxa por 100 mil habitantes usa a população do Censo 2022 (IBGE).")

por_100k = metrica == POR_100K

f = df[(df["ano"] == ano_sel) & (df["mes"].isin(meses_sel))].copy()
if f.empty:
    st.warning("Nenhum registro para os filtros selecionados.")
    st.stop()

# Meses que a base realmente cobre no ano escolhido. O ISP publica mês a mês, então o
# ano corrente vem parcial: tratá-lo como ano fechado faria o total parecer uma queda.
meses_no_ano = sorted(df.loc[df["ano"] == ano_sel, "mes"].unique())
if len(meses_no_ano) < 12:
    inicio, fim = MESES[meses_no_ano[0] - 1], MESES[meses_no_ano[-1] - 1]
    st.info(f"**{ano_sel} está parcial na base do ISP:** cobre {inicio}–{fim} "
            f"({len(meses_no_ano)} de 12 meses). O total não é comparável a um ano fechado.")

total = int(f["qtd"].sum())
rank = data_loader.ranking_municipios(f, pop, por_100k=por_100k)
topo = rank.iloc[0]

c1, c2, c3 = st.columns(3)
c1.metric("Ocorrências no recorte", f"{total:,}".replace(",", "."))
if por_100k:
    c2.metric("Município #1 (por 100 mil)", topo["municipio"], f"{topo['taxa']:.1f} /100 mil".replace(".", ","))
else:
    c2.metric("Município #1 (volume)", topo["municipio"], f"{int(topo['qtd'])} ocorrências")
c3.metric("Municípios com registro", f"{rank['cod_ibge'].nunique()} de {data_loader.MUNICIPIOS_RJ}")
st.caption("Ocorrências: ISP-RJ (oficial, mensal por município). "
           "Malha municipal e população: IBGE (Censo 2022).")

col_mapa, col_graf = st.columns([3, 2])
with col_mapa:
    st.subheader("Mapa")
    # Basemap sem chave de API. Os dois provedores óbvios não servem:
    # a Carto passou a exigir API key (devolve um tile "API KEY REQUIRED"),
    # e o OSM responde 403 "not following the tile usage policy" para uso
    # embutido em aplicação, por rodar em servidores voluntários.
    # A Esri serve por CDN comercial, sem chave; a atribuição é obrigatória
    # e o folium já a insere no rodapé do mapa.
    m = folium.Map(location=[-22.2, -42.8], zoom_start=7,
                   tiles="Esri.WorldGrayCanvas")

    col_valor = "taxa" if por_100k else "qtd"
    faixas = FAIXAS_TAXA if por_100k else FAIXAS_VOLUME
    legenda = "Roubos de carga por 100 mil hab." if por_100k else "Roubos de carga (ocorrências)"

    # O folium monta as faixas com np.linspace entre o mínimo e o máximo. Com este
    # dado isso colapsa a leitura: em 2025, 34 dos 36 municípios caíam na MESMA
    # faixa — São Gonçalo (223), Nova Iguaçu (103) e Mangaratiba (1) saíam da mesma
    # cor. Por isso a escala é montada à mão, com as faixas fixas de cima.
    # A escala só classifica; a legenda é desenhada à parte (ver legenda_html).
    escala = StepColormap(RAMPA, index=faixas + [_TETO],
                          vmin=faixas[0], vmax=faixas[-1])

    # Coroplético em vez de ponto: o dado é agregado por município, então pintar o
    # polígono é o que a granularidade permite afirmar. Um marcador implicaria um
    # local exato que a base não tem.
    # Uma camada só, com preenchimento e tooltip: o folium.Choropleth não aceita
    # tooltip, o que antes obrigava a sobrepor uma segunda camada transparente.
    valores = dict(zip(rank["cod_ibge"], rank[col_valor]))
    nomes = dict(zip(pop["cod_ibge"], pop["municipio"]))
    for feat in malha["features"]:
        cod = feat["properties"]["codarea"]
        v = valores.get(cod)
        feat["properties"]["municipio"] = nomes.get(cod, cod)
        if v is None or pd.isna(v):
            feat["properties"]["valor"] = "sem ocorrência no recorte"
        elif por_100k:
            feat["properties"]["valor"] = f"{v:.1f} por 100 mil hab.".replace(".", ",")
        else:
            feat["properties"]["valor"] = f"{int(v)} ocorrências"

    def estilo(feat):
        v = valores.get(feat["properties"]["codarea"])
        vazio = v is None or pd.isna(v)
        return {"fillColor": COR_ZERO if vazio else escala(v),
                "fillOpacity": 0.45 if vazio else 0.85,
                "color": COR_BORDA, "weight": 0.6}

    folium.GeoJson(
        malha,
        style_function=estilo,
        # Realce no hover: dá o alvo de leitura sem depender só da cor do preenchimento.
        highlight_function=lambda _: {"weight": 2.5, "color": "#191919"},
        tooltip=folium.GeoJsonTooltip(fields=["municipio", "valor"],
                                      aliases=["Município", ""]),
    ).add_to(m)

    # components.html embute o HTML via srcdoc. O st_folium faria um
    # GET /component/... extra, que depende do servidor estar acessível a
    # partir do iframe — frágil atrás de proxy (Codespaces, por exemplo).
    # O retorno do st_folium não era usado, então a troca não perde nada
    # e remove uma dependência.
    components.html(m.get_root().render(), height=520, scrolling=False)
    st.markdown(legenda_html(faixas, inteiro=not por_100k, titulo=legenda),
                unsafe_allow_html=True)
    st.caption("As faixas são fixas, iguais em todos os recortes: uma cor significa "
               "sempre o mesmo valor, então dá para comparar anos a olho. Passe o "
               "mouse para ver o número exato de cada município.")

with col_graf:
    st.subheader("Municípios com mais ocorrências (top 10)")
    top = rank.head(10).copy()
    if por_100k:
        top["valor"] = top["taxa"].round(1)
        rotulo = "Ocorrências por 100 mil hab."
    else:
        top["valor"] = top["qtd"]
        rotulo = "Ocorrências"
    # Uma série, uma cor. Colorir as barras pelo próprio valor gastaria o canal de
    # cor repetindo o que o comprimento da barra já diz.
    fig = px.bar(top, x="valor", y="municipio", orientation="h",
                 labels={"valor": rotulo, "municipio": ""},
                 color_discrete_sequence=[COR_SERIE])
    # Sem número em cima de cada barra: o eixo e o hover já dão o valor, e rótulo
    # em todas as dez barras é ruído. O comprimento da barra faz a comparação.
    fig.update_traces(marker_line_width=0)
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=320,
                      margin=dict(l=0, r=8, t=10, b=0),
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=True, gridcolor="#efefef", zeroline=False)
    st.plotly_chart(fig)
    if por_100k:
        st.caption("Volume e taxa respondem a perguntas diferentes: a taxa aproxima a "
                   "exposição relativa, mas o denominador é população, não tráfego de carga.")

    st.subheader("Sazonalidade mensal")
    # Reindexar só nos meses que a base cobre: preencher Jul–Dez de um ano parcial com
    # zero desenharia meses sem dado como meses sem ocorrência.
    porm = (f.groupby("mes")["qtd"].sum()
            .reindex(meses_no_ano).fillna(0).reset_index())
    porm["mes"] = porm["mes"].map(lambda x: MESES[int(x) - 1])
    figm = px.bar(porm, x="mes", y="qtd", labels={"mes": "", "qtd": "Ocorrências"},
                  color_discrete_sequence=[COR_SERIE])
    figm.update_traces(marker_line_width=0)
    figm.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                       plot_bgcolor="rgba(0,0,0,0)")
    figm.update_yaxes(showgrid=True, gridcolor="#efefef", zeroline=False)
    st.plotly_chart(figm)
    st.caption("O mês mais recente da base do ISP costuma vir provisório e subnotificado.")

st.download_button("⬇️ Baixar recorte (CSV)",
                   data=f.to_csv(index=False).encode("utf-8"),
                   file_name="recorte_filtrado.csv", mime="text/csv")

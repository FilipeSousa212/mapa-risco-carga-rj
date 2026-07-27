"""Dashboard — risco de roubo de carga no RJ (dados reais do ISP, mensal por município)."""

from __future__ import annotations

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium

import data_loader

st.set_page_config(page_title="Risco de Roubo de Carga — RJ", layout="wide")
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

@st.cache_data
def carregar() -> pd.DataFrame:
    data_loader.garantir_dados_isp()   # baixa o CSV se não existir (deploy)
    return data_loader.load_isp_municipio()

@st.cache_data
def carregar() -> pd.DataFrame:
    return data_loader.load_isp_municipio()


st.title("🚚 Mapa de risco de roubo de carga — Rio de Janeiro")

try:
    df = carregar()
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
    camada = st.radio("Camada do mapa", ["Mapa de calor", "Marcadores agrupados"])

f = df[(df["ano"] == ano_sel) & (df["mes"].isin(meses_sel))].copy()
if f.empty:
    st.warning("Nenhum registro para os filtros selecionados.")
    st.stop()

total = int(f["qtd"].sum())
rank = f.groupby("municipio")["qtd"].sum().sort_values(ascending=False)

c1, c2, c3 = st.columns(3)
c1.metric("Ocorrências no recorte", f"{total:,}".replace(",", "."))
c2.metric("Município #1", rank.index[0])
c3.metric("Granularidade", "Mensal / município")
st.caption("Fonte: ISP-RJ (oficial, mensal por município). Marcadores no centroide de cada município.")

col_mapa, col_graf = st.columns([3, 2])
with col_mapa:
    st.subheader("Mapa")
    m = folium.Map(location=[-22.85, -43.35], zoom_start=9, tiles="cartodbpositron")
    if camada == "Mapa de calor":
        heat = f.groupby(["lat", "lon"])["qtd"].sum().reset_index()
        HeatMap(heat[["lat", "lon", "qtd"]].values.tolist(), radius=22, blur=28).add_to(m)
    else:
        cluster = MarkerCluster().add_to(m)
        agg = f.groupby(["lat", "lon", "municipio"])["qtd"].sum().reset_index()
        for _, r in agg.iterrows():
            folium.CircleMarker([r["lat"], r["lon"]], radius=5, color="crimson",
                                fill=True, fill_opacity=0.7,
                                popup=f"{r['municipio']}: {int(r['qtd'])}").add_to(cluster)
    st_folium(m, height=520, use_container_width=True)

with col_graf:
    st.subheader("Municípios mais perigosos")
    top = rank.head(10).reset_index()
    top.columns = ["Município", "Ocorrências"]
    fig = px.bar(top, x="Ocorrências", y="Município", orientation="h")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=320,
                      margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sazonalidade mensal")
    porm = f.groupby("mes")["qtd"].sum().reindex(range(1, 13)).fillna(0).reset_index()
    porm["mes"] = porm["mes"].map(lambda x: MESES[int(x) - 1])
    figm = px.bar(porm, x="mes", y="qtd", labels={"mes": "", "qtd": "Ocorrências"})
    figm.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(figm, use_container_width=True)

st.download_button("⬇️ Baixar recorte (CSV)",
                   data=f.to_csv(index=False).encode("utf-8"),
                   file_name="recorte_filtrado.csv", mime="text/csv")
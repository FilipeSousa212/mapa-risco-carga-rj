# Mapa de Risco de Roubo de Carga — RJ

Dashboard interativo em Python que usa os **dados abertos do ISP-RJ** (Instituto de
Segurança Pública do Rio de Janeiro) para mapear onde o roubo de carga se concentra no
estado, por município, ano e mês.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-app-red)
![Tests](https://img.shields.io/badge/tests-pytest-green)
![Data](https://img.shields.io/badge/dados-ISP--RJ-informational)

<!-- Depois de rodar, adicione um print: salve em docs/screenshot.png e descomente a linha abaixo -->
<!-- ![Dashboard](docs/screenshot.png) -->

## Funcionalidades

- Mapa coroplético das ocorrências de roubo de carga nos **92 municípios** do estado,
  em classes fixas de escala logarítmica — o dado é muito assimétrico (em 2025 a
  mediana foi 4 e o máximo 1.496), então faixas de largura igual jogariam quase todos
  os municípios na mesma cor. Sendo fixas, uma cor significa sempre o mesmo valor e
  dá para comparar anos a olho.
- Filtros por **ano** (2014 em diante) e **mês**.
- Ranking dos municípios mais afetados no recorte, por **volume absoluto** ou por
  **taxa por 100 mil habitantes** — as duas leituras mudam bastante o pódio.
- Gráfico de sazonalidade mensal, com aviso quando o ano está parcial na base.
- Exportação do recorte filtrado em CSV.

## Stack

Python · pandas · Streamlit · Folium · Plotly · pytest

## Fonte dos dados

**Ocorrências** — base oficial e pública do ISP-RJ, `BaseMunicipioMensal.csv` (mensal,
por município), coluna `roubo_carga`. Série histórica a partir de **janeiro de 2014**,
atualizada mensalmente.

**Malha municipal e população** — IBGE, baixados uma vez por
`scripts/gerar_referencia_municipios.py` e versionados em `data/`, para que o app rode
sem depender da API do IBGE no deploy:

| Arquivo | Conteúdo | Fonte |
|---|---|---|
| `data/malha_municipios_rj.json` | polígonos dos 92 municípios | malhas territoriais do IBGE |
| `data/municipios_rj.csv` | `cod_ibge, municipio, populacao` | Censo 2022 (agregado 4709) |

O join entre as três bases é feito pelo **código IBGE de 7 dígitos** (`fmun_cod` no CSV
do ISP, `codarea` na malha), nunca pelo nome do município — assim uma mudança de acento
ou de grafia na base do ISP não derruba nenhum município do mapa nem do ranking.

> Os dados públicos são **mensais e por município** — não contêm hora nem dia da
> semana. Por isso o dashboard filtra por ano e mês. Para análise por hora/dia seria
> necessária uma base própria (transportadora/seguradora) com data-hora e coordenadas.

## Como rodar

Pré-requisitos: Python 3.11+ instalado.

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USUARIO/mapa-risco-carga-rj.git
cd mapa-risco-carga-rj

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
```

### Dados (já vêm no repositório)

Não é preciso baixar nada: o CSV do ISP e os dois arquivos de referência do IBGE estão
versionados em `data/`. Se o arquivo do ISP faltar, o app o baixa sozinho na primeira
execução.

Para **atualizar** a base do ISP com o mês mais recente:

```bash
curl -o data/BaseMunicipioMensal.csv https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv
```

Para regenerar a malha e a população do IBGE (raro — só se mudar o recorte territorial
ou sair um novo censo):

```bash
python scripts/gerar_referencia_municipios.py
```

### Executar

```bash
streamlit run app.py
```

Abre em https://mapaderiscorj.streamlit.app/

## Testes

```bash
pip install pytest
pytest
```

Os testes usam um CSV sintético (não dependem do download), validando o esquema de
colunas, coerção de tipos, tratamento de erros e o cálculo da taxa por 100 mil.

O teste central é o de **cobertura**: ele falha se alguma mudança voltar a descartar
municípios, garantindo que o total devolvido pelo loader feche com o total da coluna
`roubo_carga` da entrada. Uma versão anterior do loader filtrava por uma lista fixa de
30 municípios e perdia ~1.260 ocorrências da série sem avisar.

## Estrutura

```
mapa-risco-carga-rj/
├── app.py                 # Dashboard Streamlit
├── data_loader.py         # Leitura e normalização dos dados do ISP
├── requirements.txt       # Dependências
├── pytest.ini             # Config dos testes
├── .gitignore
├── scripts/
│   └── gerar_referencia_municipios.py   # baixa malha e população do IBGE (uso único)
├── data/
│   ├── BaseMunicipioMensal.csv          # ocorrências (ISP-RJ)
│   ├── malha_municipios_rj.json         # polígonos dos 92 municípios (IBGE)
│   └── municipios_rj.csv                # população por município (IBGE)
└── tests/
    └── test_data_loader.py
```

## Roadmap

- [x] Dashboard com dados reais do ISP (mensal por município)
- [x] Filtro por ano e mês
- [x] Testes automatizados
- [x] Cobertura dos 92 municípios do estado, com join por código IBGE
- [x] Mapa coroplético por município
- [x] Ranking por volume e por taxa por 100 mil habitantes
- [x] Deploy no Streamlit Cloud
- [ ] Traçado das rodovias com geometria real (OSMnx)
- [ ] Camada de base própria com hora/dia
- [ ] Motor de rotas que evita zonas de maior risco

## Limitações e uso responsável

Ferramenta de apoio à decisão logística. Os números refletem **ocorrências registradas**,
sujeitas a subnotificação; a composição do indicador "roubo de carga" mudou em 2009. O
mapa não substitui inteligência de segurança oficial e não deve ser usado para
estigmatizar territórios. Se integrar dados pessoais (ex.: base de transportadora),
respeite a LGPD.

Três ressalvas sobre a leitura dos indicadores:

- **Volume não é risco.** O ranking por volume absoluto favorece municípios grandes: a
  capital concentra cerca de metade das ocorrências do estado em boa parte por tamanho.
- **A taxa por 100 mil é uma aproximação.** Não existe dado público de volume de tráfego
  de carga por município, então o denominador é população residente. Isso mede exposição
  relativa do território, **não** risco por viagem ou por carga transportada — que é o
  que uma decisão de rota precisaria.
- **O mês mais recente vem provisório.** O ISP revisa os números nas publicações
  seguintes, então a última barra da sazonalidade tende a subnotificar. Quando o ano
  selecionado está parcial, o dashboard avisa e não desenha os meses ausentes como zero.

## Fontes

- [ISP Dados Abertos](https://www.ispdados.rj.gov.br/)
- [Base mensal por município](https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv)
- [Divisão territorial (CISP)](https://www.ispdados.rj.gov.br/divisaoTerritorial.html)
- [IBGE — malhas territoriais](https://servicodados.ibge.gov.br/api/docs/malhas)
- [IBGE — Censo 2022, população residente](https://sidra.ibge.gov.br/tabela/4709)

## Licença

MIT — sinta-se livre para usar e adaptar, citando as fontes dos dados (ISP-RJ e IBGE).
#

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

- Mapa de calor das ocorrências de roubo de carga na Região Metropolitana e no estado.
- Filtros por **ano** (2014 em diante) e **mês**.
- Ranking dos municípios mais afetados no recorte selecionado.
- Gráfico de sazonalidade mensal.
- Exportação do recorte filtrado em CSV.

## Stack

Python · pandas · Streamlit · Folium · Plotly · pytest

## Fonte dos dados

Base oficial e pública do ISP-RJ — `BaseMunicipioMensal.csv` (mensal, por município),
com a coluna `roubo_carga`. Série histórica a partir de **janeiro de 2014**, atualizada
mensalmente.

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

### Baixar os dados (obrigatório)

O CSV do ISP **não** vem no repositório (está no `.gitignore`). Baixe e salve em `data/`:

```bash
# Windows (PowerShell):
Invoke-WebRequest -Uri "https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv" -OutFile "data\BaseMunicipioMensal.csv"
```

Ou baixe manualmente em
<https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv> e salve como
`data/BaseMunicipioMensal.csv`.

### Executar

```bash
streamlit run app.py
```

Abre em <http://localhost:8501>.

## Testes

```bash
pip install pytest
pytest
```

Os testes usam um CSV sintético (não dependem do download), validando o esquema de
colunas, valores válidos, filtragem de municípios e tratamento de erros.

## Estrutura

```
mapa-risco-carga-rj/
├── app.py                 # Dashboard Streamlit
├── data_loader.py         # Leitura e normalização dos dados do ISP
├── requirements.txt       # Dependências
├── pytest.ini             # Config dos testes
├── .gitignore
├── data/                  # CSV do ISP (não versionado)
│   └── BaseMunicipioMensal.csv
└── tests/
    └── test_data_loader.py
```

## Roadmap

- [x] Dashboard com dados reais do ISP (mensal por município)
- [x] Filtro por ano e mês
- [x] Testes automatizados
- [x] Traçado das rodovias com geometria real (OSMnx)
- [x] Camada de base própria com hora/dia
- [x] Motor de rotas que evita zonas de maior risco
- [x] Deploy no Streamlit Cloud

## Limitações e uso responsável

Ferramenta de apoio à decisão logística. Os números refletem **ocorrências registradas**,
sujeitas a subnotificação; a composição do indicador "roubo de carga" mudou em 2009. O
mapa não substitui inteligência de segurança oficial e não deve ser usado para
estigmatizar territórios. Se integrar dados pessoais (ex.: base de transportadora),
respeite a LGPD.

## Fontes

- [ISP Dados Abertos](https://www.ispdados.rj.gov.br/)
- [Base mensal por município](https://www.ispdados.rj.gov.br/Arquivos/BaseMunicipioMensal.csv)
- [Divisão territorial (CISP)](https://www.ispdados.rj.gov.br/divisaoTerritorial.html)

## Licença

MIT — sinta-se livre para usar e adaptar, citando a fonte dos dados (ISP-RJ).
#

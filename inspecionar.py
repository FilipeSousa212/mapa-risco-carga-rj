import pandas as pd

df = pd.read_csv("data/BaseMunicipioMensal.csv", sep=";", encoding="latin-1")
print("Colunas:", list(df.columns))
print(df.head())
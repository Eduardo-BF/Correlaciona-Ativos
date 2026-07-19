import numpy as np
import pandas as pd

from config import HIGH_CORRELATION_THRESHOLD, LOW_CORRELATION_THRESHOLD


def calcular_retornos(precos: pd.DataFrame, frequencia: str) -> pd.DataFrame:
    """Calcula retornos logarítmicos na frequência escolhida."""
    if precos.empty:
        return pd.DataFrame()

    precos_periodicos = precos.resample(frequencia).last()
    retornos = np.log(precos_periodicos / precos_periodicos.shift(1))
    return retornos.replace([np.inf, -np.inf], np.nan).dropna(how="all")


def calcular_correlacao(retornos: pd.DataFrame) -> pd.DataFrame:
    if retornos.empty:
        return pd.DataFrame()
    return retornos.corr(method="pearson")


def listar_pares_correlacao(matriz: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Ativo 1", "Ativo 2", "Correlação", "Classificação"]
    if matriz.empty:
        return pd.DataFrame(columns=colunas)

    pares = []
    for indice, ativo_1 in enumerate(matriz.columns):
        for ativo_2 in matriz.columns[indice + 1 :]:
            correlacao = matriz.loc[ativo_1, ativo_2]
            if pd.isna(correlacao):
                continue
            if correlacao >= HIGH_CORRELATION_THRESHOLD:
                classificacao = "Alta correlação"
            elif correlacao <= LOW_CORRELATION_THRESHOLD:
                classificacao = "Baixa correlação"
            else:
                classificacao = "Correlação moderada"
            pares.append(
                {
                    "Ativo 1": ativo_1,
                    "Ativo 2": ativo_2,
                    "Correlação": correlacao,
                    "Classificação": classificacao,
                }
            )

    return pd.DataFrame(pares, columns=colunas).sort_values(
        "Correlação", ascending=False, ignore_index=True
    )

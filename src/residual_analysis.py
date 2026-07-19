import numpy as np
import pandas as pd

from config import MIN_COMMON_OBSERVATIONS


def calcular_residuos_mercado(
    retornos_ativos: pd.DataFrame, retorno_indice: pd.Series
) -> pd.DataFrame:
    """Remove de cada ativo a parcela linear explicada pelo índice."""
    if retornos_ativos.empty or retorno_indice.empty:
        return pd.DataFrame()

    residuos = {}
    indice = retorno_indice.rename("__indice__")

    for ativo in retornos_ativos.columns:
        dados_alinhados = pd.concat(
            [retornos_ativos[ativo], indice], axis=1, join="inner"
        ).dropna()

        if len(dados_alinhados) < MIN_COMMON_OBSERVATIONS:
            continue

        retorno_mercado = dados_alinhados["__indice__"].to_numpy(dtype=float)
        retorno_ativo = dados_alinhados[ativo].to_numpy(dtype=float)
        if np.isclose(np.var(retorno_mercado), 0.0):
            continue

        regressores = np.column_stack([np.ones(len(retorno_mercado)), retorno_mercado])
        try:
            alpha, beta = np.linalg.lstsq(
                regressores, retorno_ativo, rcond=None
            )[0]
        except np.linalg.LinAlgError:
            continue

        valores_ajustados = alpha + beta * retorno_mercado
        residuos[ativo] = pd.Series(
            retorno_ativo - valores_ajustados,
            index=dados_alinhados.index,
            name=ativo,
        )

    return pd.DataFrame(residuos)


def calcular_correlacao_residual(
    retornos_ativos: pd.DataFrame, retorno_indice: pd.Series
) -> pd.DataFrame:
    residuos = calcular_residuos_mercado(retornos_ativos, retorno_indice)
    if residuos.empty:
        return pd.DataFrame()

    desvios = residuos.std(skipna=True)
    colunas_variaveis = desvios[~np.isclose(desvios, 0.0)].index
    residuos = residuos.loc[:, colunas_variaveis]
    if residuos.shape[1] < 2:
        return pd.DataFrame()

    return residuos.corr(
        method="pearson", min_periods=MIN_COMMON_OBSERVATIONS
    )

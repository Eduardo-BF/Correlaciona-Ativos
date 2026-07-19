import pandas as pd


def normalizar_ticker(ticker: str) -> str:
    ticker_normalizado = ticker.strip().upper()
    if not ticker_normalizado or "." in ticker_normalizado or ticker_normalizado.startswith("^"):
        return ticker_normalizado
    return f"{ticker_normalizado}.SA"


def normalizar_lista_tickers(tickers: list[str]) -> list[str]:
    resultado = []
    vistos = set()
    for ticker in tickers:
        ticker_normalizado = normalizar_ticker(ticker)
        if ticker_normalizado and ticker_normalizado not in vistos:
            resultado.append(ticker_normalizado)
            vistos.add(ticker_normalizado)
    return resultado


def filtrar_ativos_com_dados_suficientes(
    precos: pd.DataFrame, min_observations: int
) -> pd.DataFrame:
    if precos.empty:
        return pd.DataFrame(index=precos.index)
    colunas_validas = precos.count()[lambda contagem: contagem >= min_observations].index
    return precos.loc[:, colunas_validas]

import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=60 * 60 * 24)
def buscar_precos(tickers: list[str], period: str) -> pd.DataFrame:
    """Busca preços ajustados e devolve um ativo por coluna."""
    if not tickers:
        return pd.DataFrame()

    try:
        dados = yf.download(
            tickers=tickers,
            period=period,
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        if dados.empty:
            return pd.DataFrame()

        if isinstance(dados.columns, pd.MultiIndex):
            nivel_precos = dados.columns.get_level_values(0)
            campo = "Adj Close" if "Adj Close" in nivel_precos else "Close"
            precos = dados[campo]
        else:
            campo = "Adj Close" if "Adj Close" in dados.columns else "Close"
            if campo not in dados.columns:
                return pd.DataFrame()
            precos = dados[campo]

        if isinstance(precos, pd.Series):
            precos = precos.to_frame(name=tickers[0])

        precos = precos.reindex(columns=[ticker for ticker in tickers if ticker in precos.columns])
        return precos.dropna(axis=1, how="all")
    except Exception:
        return pd.DataFrame()

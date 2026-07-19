from pathlib import Path

import pandas as pd

from utils import normalizar_ticker


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "ativos_b3.csv"
REQUIRED_COLUMNS = {"ticker", "nome", "ticker_yahoo"}
LABEL_SEPARATOR = " \u2014 "


def carregar_catalogo(caminho: Path = CATALOG_PATH) -> pd.DataFrame:
    if not caminho.exists():
        return pd.DataFrame(columns=sorted(REQUIRED_COLUMNS))

    try:
        catalogo = pd.read_csv(caminho, dtype=str, encoding="utf-8-sig").fillna("")
    except UnicodeDecodeError:
        catalogo = pd.read_csv(caminho, dtype=str, encoding="latin1").fillna("")
    if not REQUIRED_COLUMNS.issubset(catalogo.columns):
        return pd.DataFrame(columns=sorted(REQUIRED_COLUMNS))

    catalogo = catalogo.copy()
    catalogo["ticker"] = catalogo["ticker"].str.strip().str.upper()
    catalogo["ticker_yahoo"] = catalogo["ticker_yahoo"].str.strip().str.upper()
    catalogo["nome"] = catalogo["nome"].str.strip()
    catalogo = catalogo[catalogo["ticker_yahoo"].ne("")]
    return catalogo.drop_duplicates(subset=["ticker_yahoo"], keep="first")


def ticker_limpo(ticker_yahoo: str) -> str:
    ticker = str(ticker_yahoo).strip().upper()
    if ticker.endswith(".SA"):
        return ticker[:-3]
    return ticker


def montar_label_ativo(ticker: str, nome: str) -> str:
    ticker = ticker_limpo(ticker)
    nome = str(nome).strip()
    if not nome:
        return ticker
    return f"{ticker}{LABEL_SEPARATOR}{nome}"


def opcoes_ativos(catalogo: pd.DataFrame) -> list[str]:
    if catalogo.empty:
        return []

    labels = [
        montar_label_ativo(row.ticker or row.ticker_yahoo, row.nome)
        for row in catalogo.itertuples(index=False)
    ]
    return sorted(labels)


def tickers_para_labels(tickers_yahoo: list[str], catalogo: pd.DataFrame) -> list[str]:
    if catalogo.empty:
        return [ticker_limpo(ticker) for ticker in tickers_yahoo]

    labels_por_yahoo = {
        row.ticker_yahoo: montar_label_ativo(row.ticker or row.ticker_yahoo, row.nome)
        for row in catalogo.itertuples(index=False)
    }
    return [labels_por_yahoo.get(ticker.upper(), ticker_limpo(ticker)) for ticker in tickers_yahoo]


def selecoes_para_tickers_yahoo(
    selecoes: list[str], catalogo: pd.DataFrame
) -> list[str]:
    labels_para_yahoo = {}
    if not catalogo.empty:
        labels_para_yahoo = {
            montar_label_ativo(row.ticker or row.ticker_yahoo, row.nome): row.ticker_yahoo
            for row in catalogo.itertuples(index=False)
        }

    tickers = []
    vistos = set()
    for selecao in selecoes:
        texto = str(selecao).strip()
        if not texto:
            continue

        ticker = labels_para_yahoo.get(texto)
        if ticker is None:
            ticker_digitado = texto.split(LABEL_SEPARATOR, 1)[0]
            ticker = normalizar_ticker(ticker_digitado)

        if ticker and ticker not in vistos:
            tickers.append(ticker)
            vistos.add(ticker)

    return tickers


def renomear_para_tickers_limpos(dados: pd.DataFrame) -> pd.DataFrame:
    return dados.rename(index=ticker_limpo, columns=ticker_limpo)

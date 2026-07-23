DEFAULT_TICKERS = [
    "PETR4.SA",
    "PRIO3.SA",
    "VALE3.SA",
    "CMIN3.SA",
    "ITUB4.SA",
    "BBDC4.SA",
]

PERIOD_OPTIONS = {
    "1 ano": "1y",
    "3 anos": "3y",
    "5 anos": "5y",
    "10 anos": "10y",
}

FREQUENCY_OPTIONS = {
    "Semanal": "W",
    "Mensal": "M",
    "Trimestral": "Q",
}

ANALYSIS_MODES = [
    "Correlação tradicional",
    "Correlação ajustada por índice",
]

REFERENCE_INDEXES = {
    "Ibovespa": "^BVSP",
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
}

MIN_OBSERVATIONS = 20
MIN_COMMON_OBSERVATIONS = 5
VERY_HIGH_CORRELATION_THRESHOLD = 0.70
HIGH_CORRELATION_THRESHOLD = 0.50
MODERATE_CORRELATION_THRESHOLD = 0.15
LOW_CORRELATION_THRESHOLD = 0.15
HIGH_DECORRELATION_THRESHOLD = -0.50

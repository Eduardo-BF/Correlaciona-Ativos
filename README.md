# Correlação de Ativos

App em Streamlit para comparar ativos financeiros pela correlação de seus retornos logarítmicos. O foco é identificar ativos com comportamento parecido e possíveis casos de falsa diversificação.

## Funcionalidades

- Catálogo local de ativos em `data/ativos_b3.csv`.
- Busca por ticker ou nome, com suporte a tickers manuais fora do CSV.
- Normalização automática de ativos brasileiros para o formato Yahoo (`.SA`).
- Preços históricos obtidos via `yfinance`.
- Retornos logarítmicos semanais, mensais ou trimestrais.
- Correlação tradicional de Pearson.
- Correlação ajustada por benchmark via regressão linear e correlação dos resíduos.
- Benchmarks disponíveis: Nenhum, Ibovespa, S&P 500 e Nasdaq 100.
- Alinhamento em uma única janela comum para todos os ativos e, no modo ajustado, também para o benchmark.
- Heatmap interativo com destaque de linha no hover.
- Ranking de pares, tabela detalhada e download da matriz em CSV.

## Dados e catálogo

O CSV `data/ativos_b3.csv` funciona como catálogo de sugestões, não como limitação. Ativos ausentes no CSV podem ser digitados manualmente no campo de busca.

Formato esperado do CSV:

```csv
ticker,nome,tipo,setor,ticker_yahoo
PETR4,Petrobras PN,Ação,Petróleo e Gás,PETR4.SA
```

No front, o app exibe preferencialmente o ticker limpo, sem `.SA`. Internamente, os downloads usam o ticker Yahoo.

## Modos de análise

Com `Benchmark de ajuste = Nenhum`, o app calcula a correlação tradicional de Pearson sobre os retornos logarítmicos.

Com um benchmark selecionado, o app remove de cada ativo a parcela explicada pelo índice por regressão linear e calcula a correlação de Pearson entre os resíduos.

## Janela de cálculo

O app usa uma única janela comum de retornos para toda a matriz. Isso evita que pares diferentes sejam calculados com períodos diferentes.

Antes da matriz, o app mostra:

- período solicitado;
- frequência;
- período efetivamente usado;
- número de observações;
- ativos removidos por ticker inválido ou falta de dados.

## Instalação

Requer Python 3.10 ou superior.

```bash
pip install -r requirements.txt
```

## Como rodar

Na raiz do projeto:

```bash
streamlit run src/app.py
```

## Limitações

- O `yfinance` pode falhar ou não ter dados para alguns ativos.
- Ativos com histórico curto podem limitar a janela efetiva da análise.
- Correlação histórica não garante comportamento futuro.
- O app é informativo e não constitui recomendação de investimento.

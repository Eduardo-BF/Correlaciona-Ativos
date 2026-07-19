# Correlação de Ativos

MVP em Streamlit para comparar ativos financeiros por meio da correlação de seus retornos logarítmicos, com foco em investidores Buy & Hold.

## Funcionalidades do MVP

- Seleção de múltiplos ativos e normalização de códigos brasileiros.
- Preços históricos obtidos pelo `yfinance`.
- Retornos logarítmicos semanais, mensais ou trimestrais.
- Correlação tradicional ou ajustada por um índice de referência.
- Matriz de correlação de Pearson e heatmap interativo.
- Ranking de pares, leitura de possível falsa diversificação e download em CSV.

## Modos de análise

### Correlação tradicional

Mede a relação histórica direta entre os retornos dos ativos.

### Correlação ajustada por índice

Remove, por regressão linear, a parcela dos retornos explicada por um índice de referência e calcula a correlação entre os resíduos. Estão disponíveis Ibovespa, S&P 500 e Nasdaq 100.

A correlação ajustada depende do índice escolhido, da janela histórica e da frequência dos dados. Ela não garante comportamento futuro e não é recomendação de investimento.

## Instalação

Requer Python 3.10 ou superior. Em um ambiente virtual, execute:

```bash
pip install -r requirements.txt
```

## Como rodar

Na raiz do projeto, execute:

```bash
streamlit run src/app.py
```

## Exemplo de uso

Selecione `PETR4.SA`, `VALE3.SA` e `IVVB11.SA`, escolha o período de 5 anos e a frequência semanal. Clique em **Calcular correlação** para visualizar o heatmap, comparar os pares e baixar a matriz.

## Limitações conhecidas

- O `yfinance` pode falhar ou ter dados indisponíveis.
- Ativos brasileiros precisam do sufixo `.SA`, embora o app tente normalizá-lo automaticamente.
- Correlação histórica não garante comportamento futuro.
- Esta análise é informativa e não constitui recomendação de investimento.

## Próximos passos

- Análise por setor.
- Carteira com pesos.
- Correlação móvel.
- Integração com a brapi ou outra API brasileira.

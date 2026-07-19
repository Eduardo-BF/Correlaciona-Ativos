import plotly.express as px
import streamlit as st

from analytics import calcular_correlacao, calcular_retornos, listar_pares_correlacao
from assets_catalog import (
    carregar_catalogo,
    opcoes_ativos,
    renomear_para_tickers_limpos,
    selecoes_para_tickers_yahoo,
    ticker_limpo,
    tickers_para_labels,
)
from config import (
    ANALYSIS_MODES,
    DEFAULT_TICKERS,
    FREQUENCY_OPTIONS,
    HIGH_CORRELATION_THRESHOLD,
    LOW_CORRELATION_THRESHOLD,
    MIN_OBSERVATIONS,
    PERIOD_OPTIONS,
    REFERENCE_INDEXES,
)
from data_loader import buscar_precos
from residual_analysis import calcular_correlacao_residual
from utils import filtrar_ativos_com_dados_suficientes, normalizar_lista_tickers

st.set_page_config(
    page_title="Correlação de Ativos",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Correlação de Ativos")
st.write(
    "Compare o comportamento de diferentes ativos e identifique possíveis casos "
    "de falsa diversificação em uma carteira Buy & Hold."
)
st.info(
    "Correlação próxima de 100% indica ativos que tendem a andar juntos; próxima "
    "de 0% indica menor relação; e próxima de -100% indica tendência a movimentos "
    "opostos."
)

catalogo_ativos = carregar_catalogo()
opcoes_catalogo = opcoes_ativos(catalogo_ativos)
ativos_padrao = tickers_para_labels(DEFAULT_TICKERS, catalogo_ativos)
opcoes_seletor = sorted(set(opcoes_catalogo + ativos_padrao))

with st.sidebar:
    st.header("Configuração")
    tickers_selecionados = st.multiselect(
        "Ativos",
        options=opcoes_seletor,
        default=ativos_padrao,
        accept_new_options=True,
        help="Digite outros códigos, como AAPL ou PETR4.",
    )
    periodo_nome = st.selectbox(
        "Período", options=list(PERIOD_OPTIONS), index=list(PERIOD_OPTIONS).index("5 anos")
    )
    frequencia_nome = st.selectbox(
        "Frequência",
        options=list(FREQUENCY_OPTIONS),
        index=list(FREQUENCY_OPTIONS).index("Mensal"),
    )
    modo_analise = st.selectbox("Modo de análise", options=ANALYSIS_MODES)
    indice_nome = None
    if modo_analise == "Correlação ajustada por índice":
        indice_nome = st.selectbox(
            "Índice de referência", options=list(REFERENCE_INDEXES)
        )
    calcular = st.button("Calcular correlação", type="primary", use_container_width=True)

if modo_analise == "Correlação tradicional":
    st.caption(
        "Este modo calcula a correlação diretamente sobre os retornos "
        "históricos dos ativos."
    )
else:
    st.caption(
        "Este modo remove dos ativos a parcela do movimento explicada pelo índice "
        "escolhido. Assim, a correlação resultante mostra se os ativos ainda se "
        "comportam de forma parecida por fatores próprios."
    )

if calcular:
    tickers = selecoes_para_tickers_yahoo(tickers_selecionados, catalogo_ativos)
    tickers = normalizar_lista_tickers(tickers)
    if len(tickers) < 2:
        st.error("Selecione pelo menos dois ativos diferentes para comparar.")
        st.stop()

    with st.spinner("Buscando dados e calculando correlações..."):
        precos = buscar_precos(tickers, PERIOD_OPTIONS[periodo_nome])
        if precos.empty:
            st.error(
                "Não foi possível baixar os dados dos ativos. Confira os códigos "
                "ou tente novamente mais tarde."
            )
            st.stop()

        precos_filtrados = filtrar_ativos_com_dados_suficientes(
            precos, MIN_OBSERVATIONS
        )

        if precos_filtrados.shape[1] < 2:
            st.error(
                "Não foi possível obter dados suficientes para pelo menos dois ativos. "
                "Confira os códigos ou tente novamente mais tarde."
            )
            st.stop()

        retornos = calcular_retornos(
            precos_filtrados, FREQUENCY_OPTIONS[frequencia_nome]
        )

        if modo_analise == "Correlação ajustada por índice":
            ticker_indice = REFERENCE_INDEXES[indice_nome]
            precos_indice = buscar_precos(
                [ticker_indice], PERIOD_OPTIONS[periodo_nome]
            )
            if (
                precos_indice.empty
                or precos_indice[ticker_indice].count() < MIN_OBSERVATIONS
            ):
                st.error(
                    "Não foi possível obter dados suficientes para o índice "
                    "selecionado. Tente outro período ou novamente mais tarde."
                )
                st.stop()

            retornos_indice = calcular_retornos(
                precos_indice, FREQUENCY_OPTIONS[frequencia_nome]
            )
            matriz = calcular_correlacao_residual(
                retornos, retornos_indice[ticker_indice]
            )
        else:
            matriz = calcular_correlacao(retornos)

        pares = listar_pares_correlacao(matriz)

    if matriz.empty or pares.empty:
        st.error(
            "Os dados em comum não foram suficientes para calcular a correlação. "
            "Tente aumentar o período ou usar uma frequência mais frequente."
        )
        st.stop()

    ativos_ignorados = [ticker for ticker in tickers if ticker not in precos_filtrados]
    if ativos_ignorados:
        st.caption(
            "Ativos ignorados por falta de dados suficientes: "
            + ", ".join(ticker_limpo(ticker) for ticker in ativos_ignorados)
        )

    if modo_analise == "Correlação ajustada por índice":
        ativos_sem_sobreposicao = [
            ticker for ticker in precos_filtrados.columns if ticker not in matriz.columns
        ]
        if ativos_sem_sobreposicao:
            st.caption(
                "Ativos ignorados por falta de dados em comum com o índice: "
                + ", ".join(ticker_limpo(ticker) for ticker in ativos_sem_sobreposicao)
            )

    titulo_matriz = (
        "Matriz de correlação residual"
        if modo_analise == "Correlação ajustada por índice"
        else "Matriz de correlação"
    )
    st.subheader(titulo_matriz)
    matriz_exibicao = renomear_para_tickers_limpos(matriz)
    pares_exibicao = listar_pares_correlacao(matriz_exibicao)
    matriz_percentual = matriz_exibicao * 100
    figura = px.imshow(
        matriz_percentual,
        color_continuous_scale=[
            (0.0, "#2F5FA7"),
            (0.3, "#7296cc"),
            (0.5, "#FFFFFF"),
            (0.8, "#f2cece"),
            (1.0, "#EF6A6A"),
        ],
        zmin=-100,
        zmax=100,
        text_auto=".2f",
        aspect="auto",
    )
    figura.update_traces(
        texttemplate="<b>%{z:.2f}%</b>",
        textfont={"color": "#111827"},
        hovertemplate="%{x} × %{y}<br>Correlação: %{z:.2f}%<extra></extra>",
    )
    figura.update_layout(
        coloraxis_colorbar={
            "title": "Correlação",
            "ticksuffix": "%",
            "tickvals": [-100, -50, 0, 50, 100],
        }
    )
    st.plotly_chart(figura, use_container_width=True)

    st.subheader("Pares de ativos")
    pares_exibicao["Correlação"] = pares_exibicao["Correlação"] * 100
    st.dataframe(
        pares_exibicao,
        column_config={
            "Correlação": st.column_config.NumberColumn(format="%.2f%%")
        },
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Leitura rápida")
    quantidade_altos = int((pares["Correlação"] >= HIGH_CORRELATION_THRESHOLD).sum())
    quantidade_baixos = int((pares["Correlação"] <= LOW_CORRELATION_THRESHOLD).sum())
    if quantidade_altos:
        st.warning(
            f"Foram encontrados {quantidade_altos} pares com correlação alta. "
            "Isso pode indicar sobreposição de comportamento entre esses ativos."
        )
    else:
        st.success("Não foram encontrados pares com correlação alta neste período.")

    if quantidade_baixos:
        st.info(
            f"Foram encontrados {quantidade_baixos} pares com correlação baixa, "
            "o que pode contribuir para a diversificação."
        )

    st.download_button(
        "Baixar matriz em CSV",
        data=matriz_exibicao.to_csv().encode("utf-8-sig"),
        file_name="matriz_correlacao.csv",
        mime="text/csv",
    )

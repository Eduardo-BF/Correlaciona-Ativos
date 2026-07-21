from html import escape

import plotly.graph_objects as go
import pandas as pd
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


def formatar_correlacao(valor: float) -> str:
    return f"{valor * 100:.2f}%"


def classificar_correlacao_visual(valor: float) -> str:
    if valor >= HIGH_CORRELATION_THRESHOLD:
        return "Alta correlação positiva"
    if valor < -LOW_CORRELATION_THRESHOLD:
        return "Correlação negativa"
    if abs(valor) <= LOW_CORRELATION_THRESHOLD:
        return "Baixa correlação"
    return "Correlação moderada"


def interpretar_correlacao(valor: float) -> str:
    if valor >= HIGH_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram movimentos históricos semelhantes."
    if abs(valor) <= LOW_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram pouca relação linear no período."
    if valor < -LOW_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram tendência de movimentos opostos."
    return "Os ativos apresentaram relação moderada no período analisado."


def estilo_classificacao(classificacao: str) -> dict[str, str]:
    estilos = {
        "Alta correlação positiva": {
            "background": "rgba(239, 106, 106, 0.16)",
            "color": "#B42318",
        },
        "Correlação moderada": {
            "background": "rgba(242, 206, 206, 0.30)",
            "color": "#8A3A3A",
        },
        "Baixa correlação": {
            "background": "rgba(114, 150, 204, 0.18)",
            "color": "#2F5FA7",
        },
        "Correlação negativa": {
            "background": "rgba(47, 95, 167, 0.20)",
            "color": "#248671",
        },
    }
    return estilos.get(classificacao, estilos["Correlação moderada"])


def preparar_pares_exibicao(pares: list[dict]) -> list[dict]:
    return [
        {
            **par,
            "Classificação": classificar_correlacao_visual(par["Correlação"]),
            "Interpretação": interpretar_correlacao(par["Correlação"]),
        }
        for par in pares
    ]


def pares_da_matriz(matriz) -> list[dict]:
    pares = []
    colunas = list(matriz.columns)
    for indice, ativo_1 in enumerate(colunas):
        for ativo_2 in colunas[indice + 1 :]:
            correlacao = matriz.loc[ativo_1, ativo_2]
            if correlacao != correlacao:
                continue
            pares.append(
                {
                    "Ativo 1": ativo_1,
                    "Ativo 2": ativo_2,
                    "Correlação": float(correlacao),
                }
            )
    return preparar_pares_exibicao(pares)


def obter_cards_resumo(pares: list[dict]) -> list[tuple[str, dict]]:
    cards = []
    pares_positivos = [par for par in pares if par["Correlação"] > 0]
    pares_negativos = [par for par in pares if par["Correlação"] < 0]

    if pares_positivos:
        cards.append(
            (
                "Maior correlação positiva",
                max(pares_positivos, key=lambda par: par["Correlação"]),
            )
        )
    if pares:
        cards.append(
            (
                "Par mais próximo de zero",
                min(pares, key=lambda par: abs(par["Correlação"])),
            )
        )
    if pares_negativos:
        cards.append(
            (
                "Maior correlação negativa",
                min(pares_negativos, key=lambda par: par["Correlação"]),
            )
        )

    return cards


def ordenar_pares(pares: list[dict], criterio: str) -> list[dict]:
    if criterio == "menor correlação":
        return sorted(pares, key=lambda par: par["Correlação"])
    if criterio == "maior correlação absoluta":
        return sorted(pares, key=lambda par: abs(par["Correlação"]), reverse=True)
    if criterio == "mais próximo de zero":
        return sorted(pares, key=lambda par: abs(par["Correlação"]))
    return sorted(pares, key=lambda par: par["Correlação"], reverse=True)


def filtrar_pares(pares: list[dict], filtro: str) -> list[dict]:
    if filtro == "Todos":
        return pares
    return [par for par in pares if par["Classificação"] == filtro]


def extrair_ponto_selecionado(evento_grafico) -> tuple[int, int] | None:
    if not evento_grafico:
        return None

    selection = (
        evento_grafico.get("selection", {})
        if isinstance(evento_grafico, dict)
        else getattr(evento_grafico, "selection", {})
    )
    pontos = (
        selection.get("points", [])
        if isinstance(selection, dict)
        else getattr(selection, "points", [])
    )
    if not pontos:
        return None

    ponto = pontos[0]
    x = ponto.get("x") if isinstance(ponto, dict) else getattr(ponto, "x", None)
    y = ponto.get("y") if isinstance(ponto, dict) else getattr(ponto, "y", None)
    if x is None or y is None:
        return None
    return int(x), int(y)


def adicionar_destaque_heatmap(
    figura, tamanho: int, x_selecionado: int, y_selecionado: int
) -> None:
    for y in range(tamanho):
        for x in range(tamanho):
            if x == x_selecionado or y == y_selecionado:
                continue
            figura.add_shape(
                type="rect",
                x0=x - 0.5,
                x1=x + 0.5,
                y0=y - 0.5,
                y1=y + 0.5,
                line={"width": 0},
                fillcolor="rgba(17, 24, 39, 0.18)",
                layer="above",
            )

    figura.add_shape(
        type="rect",
        x0=-0.5,
        x1=tamanho - 0.5,
        y0=y_selecionado - 0.5,
        y1=y_selecionado + 0.5,
        line={"width": 1, "color": "rgba(17, 24, 39, 0.18)"},
        fillcolor="rgba(255, 255, 255, 0.18)",
        layer="above",
    )
    figura.add_shape(
        type="rect",
        x0=x_selecionado - 0.5,
        x1=x_selecionado + 0.5,
        y0=-0.5,
        y1=tamanho - 0.5,
        line={"width": 1, "color": "rgba(17, 24, 39, 0.18)"},
        fillcolor="rgba(255, 255, 255, 0.18)",
        layer="above",
    )
    figura.add_shape(
        type="rect",
        x0=x_selecionado - 0.5,
        x1=x_selecionado + 0.5,
        y0=y_selecionado - 0.5,
        y1=y_selecionado + 0.5,
        line={"width": 3, "color": "rgba(17, 24, 39, 0.90)"},
        fillcolor="rgba(255, 255, 255, 0)",
        layer="above",
    )


def renderizar_card_resumo(titulo: str, par: dict) -> None:
    estilo = estilo_classificacao(par["Classificação"])
    st.markdown(
        f"""
        <div class="correlation-card">
            <div class="card-title">{escape(titulo)}</div>
            <div class="card-pair">{escape(par["Ativo 1"])} × {escape(par["Ativo 2"])}</div>
            <div class="card-value">{formatar_correlacao(par["Correlação"])}</div>
            <span class="correlation-badge" style="background:{estilo['background']};color:{estilo['color']};">
                {escape(par["Classificação"])}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_ranking_pares(pares: list[dict]) -> None:
    for par in pares:
        valor = par["Correlação"]
        largura = min(abs(valor), 1) * 50
        estilo = estilo_classificacao(par["Classificação"])
        barra_negativa = largura if valor < 0 else 0
        barra_positiva = largura if valor >= 0 else 0
        st.markdown(
            f"""
            <div class="pair-row">
                <div class="pair-main">
                    <div class="pair-name">{escape(par["Ativo 1"])} × {escape(par["Ativo 2"])}</div>
                    <span class="correlation-badge" style="background:{estilo['background']};color:{estilo['color']};">
                        {escape(par["Classificação"])}
                    </span>
                </div>
                <div class="pair-value">{formatar_correlacao(valor)}</div>
                <div class="correlation-bar">
                    <div class="bar-center"></div>
                    <div class="bar-negative" style="width:{barra_negativa:.2f}%;"></div>
                    <div class="bar-positive" style="width:{barra_positiva:.2f}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def renderizar_resumo_par(par: dict) -> None:
    estilo = estilo_classificacao(par["Classificação"])
    st.markdown(
        f"""
        <div class="selected-pair">
            <div>
                <div class="card-title">Par em destaque</div>
                <div class="card-pair">{escape(par["Ativo 1"])} × {escape(par["Ativo 2"])}</div>
                <div class="pair-interpretation">{escape(par["Interpretação"])}</div>
            </div>
            <div class="selected-pair-side">
                <div class="card-value">{formatar_correlacao(par["Correlação"])}</div>
                <span class="correlation-badge" style="background:{estilo['background']};color:{estilo['color']};">
                    {escape(par["Classificação"])}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


PLOTLY_CONFIG = {
    "displayModeBar": False,
    "editable": False,
    "scrollZoom": False,
}

RESULTADO_CORRELACAO_KEY = "resultado_correlacao"
HEATMAP_DESTACADO_KEY = "celula_heatmap_destacada"


RESULTADOS_CSS = """
    <style>
    .correlation-card,
    .pair-row,
    .selected-pair {
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.035);
        padding: 0.9rem;
    }
    .card-title {
        color: rgba(128, 128, 128, 0.95);
        font-size: 0.82rem;
        margin-bottom: 0.35rem;
    }
    .card-pair,
    .pair-name {
        font-weight: 700;
        color: inherit;
    }
    .card-value,
    .pair-value {
        font-size: 1.35rem;
        font-weight: 800;
        color: inherit;
        white-space: nowrap;
    }
    .correlation-badge {
        display: inline-flex;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        line-height: 1;
        margin-top: 0.45rem;
        padding: 0.35rem 0.55rem;
    }
    .pair-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 0.6rem 1rem;
        margin-bottom: 0.6rem;
    }
    .pair-main {
        min-width: 0;
    }
    .correlation-bar {
        grid-column: 1 / -1;
        position: relative;
        height: 0.45rem;
        border-radius: 999px;
        background: rgba(128, 128, 128, 0.16);
        overflow: hidden;
    }
    .bar-center {
        position: absolute;
        left: 50%;
        top: 0;
        bottom: 0;
        width: 1px;
        background: rgba(128, 128, 128, 0.55);
    }
    .bar-negative,
    .bar-positive {
        position: absolute;
        top: 0;
        bottom: 0;
    }
    .bar-negative {
        right: 50%;
        background: #2F5FA7;
    }
    .bar-positive {
        left: 50%;
        background: #EF6A6A;
    }
    .selected-pair {
        align-items: center;
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-top: 0.6rem;
    }
    .selected-pair-side {
        text-align: right;
    }
    .pair-interpretation {
        color: rgba(128, 128, 128, 0.95);
        margin-top: 0.25rem;
    }
    @media (max-width: 720px) {
        .selected-pair,
        .pair-row {
            display: block;
        }
        .pair-value,
        .selected-pair-side {
            margin-top: 0.55rem;
            text-align: left;
        }
    }
    </style>
    """

st.set_page_config(
    page_title="Correlação de Ativos",
    page_icon="📊",
    layout="wide",
)

st.markdown(RESULTADOS_CSS, unsafe_allow_html=True)

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
    with st.expander("Configurações", expanded=False):
        periodo_nome = st.selectbox(
            "Período",
            options=list(PERIOD_OPTIONS),
            index=list(PERIOD_OPTIONS).index("5 anos"),
        )
        frequencia_nome = st.selectbox(
            "Frequência",
            options=list(FREQUENCY_OPTIONS),
            index=list(FREQUENCY_OPTIONS).index("Mensal"),
        )
        benchmark_nome = st.selectbox(
            "Benchmark de ajuste",
            options=["Nenhum", *REFERENCE_INDEXES],
            index=1,
        )
    calcular = st.button("Calcular correlação", type="primary", use_container_width=True)

ajuste_por_benchmark = benchmark_nome != "Nenhum"

if not ajuste_por_benchmark:
    st.caption(
        "Este modo calcula a correlação diretamente sobre os retornos "
        "históricos dos ativos."
    )
else:
    st.caption(
        f"Este modo remove dos ativos a parcela do movimento explicada pelo "
        f"{benchmark_nome}. Assim, a correlação resultante mostra se os ativos "
        "ainda se comportam de forma parecida por fatores próprios."
    )

if calcular or RESULTADO_CORRELACAO_KEY in st.session_state:
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

            if ajuste_por_benchmark:
                ticker_indice = REFERENCE_INDEXES[benchmark_nome]
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
            precos_filtrados_colunas = list(precos_filtrados.columns)
            ativos_ignorados = [
                ticker for ticker in tickers if ticker not in precos_filtrados_colunas
            ]
            ativos_sem_sobreposicao = (
                [
                    ticker
                    for ticker in precos_filtrados_colunas
                    if ticker not in matriz.columns
                ]
                if ajuste_por_benchmark
                else []
            )

        st.session_state[RESULTADO_CORRELACAO_KEY] = {
            "matriz": matriz,
            "pares": pares,
            "tickers": tickers,
            "ativos_ignorados": ativos_ignorados,
            "ativos_sem_sobreposicao": ativos_sem_sobreposicao,
            "ajuste_por_benchmark": ajuste_por_benchmark,
            "benchmark_nome": benchmark_nome,
        }
        st.session_state.pop(HEATMAP_DESTACADO_KEY, None)

    resultado_correlacao = st.session_state[RESULTADO_CORRELACAO_KEY]
    matriz = resultado_correlacao["matriz"]
    pares = resultado_correlacao["pares"]
    tickers = resultado_correlacao["tickers"]
    ativos_ignorados = resultado_correlacao["ativos_ignorados"]
    ativos_sem_sobreposicao = resultado_correlacao["ativos_sem_sobreposicao"]
    ajuste_por_benchmark_resultado = resultado_correlacao["ajuste_por_benchmark"]
    benchmark_nome_resultado = resultado_correlacao["benchmark_nome"]

    if matriz.empty or pares.empty:
        st.error(
            "Os dados em comum não foram suficientes para calcular a correlação. "
            "Tente aumentar o período ou usar uma frequência mais frequente."
        )
        st.stop()

    if ativos_ignorados:
        st.caption(
            "Ativos ignorados por falta de dados suficientes: "
            + ", ".join(ticker_limpo(ticker) for ticker in ativos_ignorados)
        )

    if ajuste_por_benchmark_resultado:
        if ativos_sem_sobreposicao:
            st.caption(
                "Ativos ignorados por falta de dados em comum com o índice: "
                + ", ".join(ticker_limpo(ticker) for ticker in ativos_sem_sobreposicao)
            )

    titulo_matriz = (
        f"Matriz de correlação ajustada por {benchmark_nome_resultado}"
        if ajuste_por_benchmark_resultado
        else "Matriz de correlação tradicional"
    )
    st.subheader(titulo_matriz)
    matriz_exibicao = renomear_para_tickers_limpos(matriz)
    pares_exibicao = pares_da_matriz(matriz_exibicao)
    ativos_heatmap = list(matriz_exibicao.columns)
    indices_heatmap = list(range(len(ativos_heatmap)))
    textos_heatmap = matriz_exibicao.applymap(formatar_correlacao).to_numpy()
    dados_hover = [
        [
            [
                ativo_y,
                ativo_x,
                formatar_correlacao(matriz_exibicao.loc[ativo_y, ativo_x]),
                (
                    "Mesmo ativo"
                    if ativo_x == ativo_y
                    else classificar_correlacao_visual(
                        matriz_exibicao.loc[ativo_y, ativo_x]
                    )
                ),
            ]
            for ativo_x in ativos_heatmap
        ]
        for ativo_y in ativos_heatmap
    ]

    figura = go.Figure(
        data=go.Heatmap(
            z=matriz_exibicao.to_numpy(),
            x=indices_heatmap,
            y=indices_heatmap,
            text=textos_heatmap,
            customdata=dados_hover,
            colorscale=[
                [0.0, "#2F5FA7"],
                [0.3, "#7296cc"],
                [0.5, "#FFFFFF"],
                [0.8, "#f2cece"],
                [1.0, "#EF6A6A"],
            ],
            zmin=-1,
            zmax=1,
            texttemplate="<b>%{text}</b>",
            textfont={"color": "#111827"},
            hovertemplate=(
                "<b>%{customdata[0]} × %{customdata[1]}</b><br>"
                "Correlação: %{customdata[2]}<br>"
                "Classificação: %{customdata[3]}<extra></extra>"
            ),
            colorbar={
                "title": "Correlação",
                "tickvals": [-1, -0.5, 0, 0.5, 1],
                "ticktext": ["-100%", "-50%", "0%", "50%", "100%"],
            },
        )
    )
    figura.update_xaxes(
        side="top",
        tickmode="array",
        tickvals=indices_heatmap,
        ticktext=ativos_heatmap,
        tickangle=-35 if len(ativos_heatmap) > 8 else 0,
        showgrid=False,
        showspikes=False,
    )
    figura.update_yaxes(
        tickmode="array",
        tickvals=indices_heatmap,
        ticktext=ativos_heatmap,
        autorange="reversed",
        showgrid=False,
        showspikes=False,
    )
    figura.update_layout(
        clickmode="event+select",
        dragmode=False,
        height=max(420, min(760, 56 * len(ativos_heatmap) + 180)),
        margin={"l": 72, "r": 24, "t": 92, "b": 32},
    )

    celula_destacada = st.session_state.get(HEATMAP_DESTACADO_KEY)
    if celula_destacada:
        x_destacado, y_destacado = celula_destacada
        if x_destacado in indices_heatmap and y_destacado in indices_heatmap:
            adicionar_destaque_heatmap(
                figura, len(ativos_heatmap), x_destacado, y_destacado
            )

    try:
        evento_grafico = st.plotly_chart(
            figura,
            use_container_width=True,
            key="heatmap_correlacao",
            on_select="rerun",
            selection_mode="points",
            config=PLOTLY_CONFIG,
        )
    except TypeError:
        evento_grafico = None
        st.plotly_chart(figura, use_container_width=True, config=PLOTLY_CONFIG)

    ponto_selecionado = extrair_ponto_selecionado(evento_grafico)
    if ponto_selecionado and ponto_selecionado != celula_destacada:
        x_selecionado, y_selecionado = ponto_selecionado
        if x_selecionado in indices_heatmap and y_selecionado in indices_heatmap:
            st.session_state[HEATMAP_DESTACADO_KEY] = ponto_selecionado
            st.rerun()

    celula_destacada = st.session_state.get(HEATMAP_DESTACADO_KEY)
    if celula_destacada:
        x_destacado, y_destacado = celula_destacada
        if (
            x_destacado in indices_heatmap
            and y_destacado in indices_heatmap
            and x_destacado != y_destacado
        ):
            ativo_1 = ativos_heatmap[y_destacado]
            ativo_2 = ativos_heatmap[x_destacado]
            correlacao_destacada = float(matriz_exibicao.loc[ativo_1, ativo_2])
            renderizar_resumo_par(
                {
                    "Ativo 1": ativo_1,
                    "Ativo 2": ativo_2,
                    "Correlação": correlacao_destacada,
                    "Classificação": classificar_correlacao_visual(
                        correlacao_destacada
                    ),
                    "Interpretação": interpretar_correlacao(
                        correlacao_destacada
                    ),
                }
            )

    st.subheader("Destaques")
    cards_resumo = obter_cards_resumo(pares_exibicao)
    colunas_cards = st.columns(max(1, len(cards_resumo)))
    for coluna, (titulo_card, par_card) in zip(colunas_cards, cards_resumo):
        with coluna:
            renderizar_card_resumo(titulo_card, par_card)

    st.subheader("Ranking de pares")
    coluna_filtro, coluna_ordem = st.columns([1.2, 1])
    with coluna_filtro:
        filtro_correlacao = st.radio(
            "Filtro",
            options=[
                "Todos",
                "Alta correlação positiva",
                "Correlação moderada",
                "Baixa correlação",
                "Correlação negativa",
            ],
            horizontal=True,
        )
    with coluna_ordem:
        criterio_ordenacao = st.selectbox(
            "Ordenação",
            options=[
                "maior correlação",
                "menor correlação",
                "maior correlação absoluta",
                "mais próximo de zero",
            ],
        )

    pares_ranking = ordenar_pares(
        filtrar_pares(pares_exibicao, filtro_correlacao), criterio_ordenacao
    )
    if pares_ranking:
        renderizar_ranking_pares(pares_ranking)
    else:
        st.info("Nenhum par encontrado para este filtro.")

    with st.expander("Ver dados detalhados"):
        tabela_detalhada = pd.DataFrame(pares_exibicao)
        tabela_detalhada["Correlação"] = tabela_detalhada["Correlação"] * 100
        tabela_detalhada["Correlação"] = tabela_detalhada["Correlação"].map(
            lambda valor: f"{valor:.2f}%"
        )
        st.table(tabela_detalhada)

    st.download_button(
        "Baixar matriz em CSV",
        data=matriz_exibicao.to_csv().encode("utf-8-sig"),
        file_name="matriz_correlacao.csv",
        mime="text/csv",
    )

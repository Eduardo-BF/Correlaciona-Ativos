import inspect
from html import escape

import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
    HIGH_DECORRELATION_THRESHOLD,
    HIGH_CORRELATION_THRESHOLD,
    LOW_CORRELATION_THRESHOLD,
    MODERATE_CORRELATION_THRESHOLD,
    MIN_COMMON_OBSERVATIONS,
    MIN_OBSERVATIONS,
    PERIOD_OPTIONS,
    REFERENCE_INDEXES,
    VERY_HIGH_CORRELATION_THRESHOLD,
)
from data_loader import buscar_precos
from residual_analysis import calcular_correlacao_residual
from utils import filtrar_ativos_com_dados_suficientes, normalizar_lista_tickers


def formatar_correlacao(valor: float) -> str:
    return f"{valor * 100:.2f}%"


def classificar_correlacao_visual(valor: float) -> str:
    if valor >= VERY_HIGH_CORRELATION_THRESHOLD:
        return "Correlação altíssima"
    if valor >= HIGH_CORRELATION_THRESHOLD:
        return "Correlação alta"
    if valor >= MODERATE_CORRELATION_THRESHOLD:
        return "Correlação moderada"
    if valor >= -LOW_CORRELATION_THRESHOLD:
        return "Baixa correlação"
    if valor > HIGH_DECORRELATION_THRESHOLD:
        return "Descorrelação moderada"
    return "Descorrelação alta"


def interpretar_correlacao(valor: float) -> str:
    if valor >= VERY_HIGH_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram movimentos históricos muito semelhantes."
    if valor >= HIGH_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram movimentos históricos semelhantes."
    if valor >= MODERATE_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram relação positiva moderada no período."
    if valor >= -LOW_CORRELATION_THRESHOLD:
        return "Os ativos apresentaram pouca relação linear no período."
    if valor > HIGH_DECORRELATION_THRESHOLD:
        return "Os ativos apresentaram relação negativa moderada no período."
    return "Os ativos apresentaram tendência mais forte de movimentos opostos."


def estilo_classificacao(classificacao: str) -> dict[str, str]:
    estilos = {
        "Correlação altíssima": {
            "background": "rgba(239, 106, 106, 0.16)",
            "color": "#B42318",
        },
        "Correlação alta": {
            "background": "rgba(239, 106, 106, 0.12)",
            "color": "#CF3030",
        },
        "Correlação moderada": {
            "background": "rgba(242, 206, 206, 0.30)",
            "color": "#ECA1A1",
        },
        "Baixa correlação": {
            "background": "rgba(114, 150, 204, 0.18)",
            "color": "#C1CBDB",
        },
        "Descorrelação moderada": {
            "background": "rgba(47, 95, 167, 0.20)",
            "color": "#6B9ED1",
        },
        "Descorrelação alta": {
            "background": "rgba(47, 95, 167, 0.28)",
            "color": "#4B86C6",
        },
    }
    return estilos.get(classificacao, estilos["Baixa correlação"])


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


def formatar_data(data) -> str:
    if pd.isna(data):
        return "-"
    return pd.Timestamp(data).strftime("%d/%m/%Y")


def formatar_lista_tickers(tickers: list[str]) -> str:
    return ", ".join(ticker_limpo(ticker) for ticker in tickers)


def obter_chave_selecao_ativo(selecao: str) -> str:
    tickers = selecoes_para_tickers_yahoo([selecao], catalogo_ativos)
    if tickers:
        return tickers[0]
    return str(selecao).strip().upper()


def adicionar_selecao_ativo(selecao: str) -> None:
    if selecao is None:
        return

    selecao = str(selecao).strip()
    if not selecao:
        return

    selecionados = st.session_state.setdefault(SELECOES_ATIVOS_KEY, [])
    ticker_novo = obter_chave_selecao_ativo(selecao)
    tickers_atuais = {
        obter_chave_selecao_ativo(ativo)
        for ativo in selecionados
        if str(ativo).strip()
    }

    if ticker_novo not in tickers_atuais:
        selecionados.append(selecao)


def adicionar_ativo_do_seletor() -> None:
    adicionar_selecao_ativo(st.session_state.get(ATIVO_ADICIONAR_KEY, ""))
    if selectbox_aceita_novas_opcoes() and selectbox_aceita_placeholder():
        st.session_state[ATIVO_ADICIONAR_KEY] = None
    else:
        st.session_state[ATIVO_ADICIONAR_KEY] = ""


def remover_selecao_ativo(indice: int) -> None:
    selecionados = st.session_state.get(SELECOES_ATIVOS_KEY, [])
    if 0 <= indice < len(selecionados):
        del selecionados[indice]


def deduplicar_selecoes_ativos(selecoes: list[str]) -> list[str]:
    resultado = []
    vistos = set()
    for selecao in selecoes:
        chave = obter_chave_selecao_ativo(selecao)
        if chave and chave not in vistos:
            resultado.append(selecao)
            vistos.add(chave)
    return resultado


def selectbox_aceita_novas_opcoes() -> bool:
    return "accept_new_options" in inspect.signature(st.selectbox).parameters


def selectbox_aceita_placeholder() -> bool:
    return "placeholder" in inspect.signature(st.selectbox).parameters


def renderizar_busca_ativo(opcoes: list[str]) -> None:
    placeholder = "Digite para buscar ticker ou nome"
    if selectbox_aceita_novas_opcoes():
        argumentos_selectbox = {
            "label": "Buscar ativo",
            "options": opcoes,
            "key": ATIVO_ADICIONAR_KEY,
            "on_change": adicionar_ativo_do_seletor,
            "accept_new_options": True,
            "help": (
                "Busque um ativo do catálogo ou digite um ticker manual."
            ),
        }
        if selectbox_aceita_placeholder():
            argumentos_selectbox["index"] = None
            argumentos_selectbox["placeholder"] = placeholder
        else:
            argumentos_selectbox["options"] = ["", *opcoes]
            argumentos_selectbox["format_func"] = (
                lambda opcao: placeholder if not opcao else opcao
            )

        st.selectbox(**argumentos_selectbox)
        return

    st.text_input(
        "Buscar ativo",
        placeholder="Digite um ticker, como PETR4 ou BOVA11",
        key=ATIVO_ADICIONAR_KEY,
        on_change=adicionar_ativo_do_seletor,
        help=(
            "Sua versão do Streamlit não permite sugestões e tickers manuais no "
            "mesmo selectbox; este campo aceita o ticker manual."
        ),
    )


def alinhar_janela_comum(
    retornos_ativos: pd.DataFrame,
    retorno_benchmark: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series | None]:
    if retornos_ativos.empty:
        return pd.DataFrame(), None

    retornos_ativos = retornos_ativos.dropna(axis=1, how="all")
    if retorno_benchmark is None:
        return retornos_ativos.dropna(how="any"), None

    benchmark = retorno_benchmark.rename("__benchmark__")
    dados_alinhados = pd.concat(
        [retornos_ativos, benchmark], axis=1, join="inner"
    ).dropna(how="any")
    if dados_alinhados.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    return (
        dados_alinhados.drop(columns="__benchmark__"),
        dados_alinhados["__benchmark__"],
    )


def identificar_limitadores_janela(
    retornos_ativos: pd.DataFrame,
    retorno_benchmark: pd.Series | None,
    inicio_efetivo,
) -> list[str]:
    inicios = {}
    for ticker in retornos_ativos.columns:
        serie = retornos_ativos[ticker].dropna()
        if not serie.empty:
            inicios[ticker] = serie.index.min()

    if retorno_benchmark is not None:
        benchmark = retorno_benchmark.dropna()
        if not benchmark.empty:
            inicios["benchmark"] = benchmark.index.min()

    if not inicios or pd.isna(inicio_efetivo):
        return []

    inicio_mais_antigo = min(inicios.values())
    if pd.Timestamp(inicio_efetivo) <= pd.Timestamp(inicio_mais_antigo):
        return []

    return [
        ticker
        for ticker, inicio in inicios.items()
        if pd.Timestamp(inicio) == pd.Timestamp(inicio_efetivo)
    ]


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
        indice_ponto = (
            ponto.get("point_number")
            if isinstance(ponto, dict)
            else getattr(ponto, "point_number", None)
        )
        if indice_ponto is None:
            indice_ponto = (
                ponto.get("point_index")
                if isinstance(ponto, dict)
                else getattr(ponto, "point_index", None)
            )
        if isinstance(indice_ponto, (list, tuple)) and len(indice_ponto) == 2:
            return int(indice_ponto[1]), int(indice_ponto[0])
        return None

    return int(x), int(y)


def adicionar_destaque_heatmap(
    figura, tamanho: int, x_selecionado: int, y_selecionado: int
) -> None:
    def adicionar_cobertura(x0: float, x1: float, y0: float, y1: float) -> None:
        if x1 <= x0 or y1 <= y0:
            return

        figura.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            line={"width": 0},
            fillcolor="rgba(17, 24, 39, 0.42)",
            layer="above",
        )

    limite_minimo = -0.5
    limite_maximo = tamanho - 0.5
    linha_superior = y_selecionado - 0.5
    linha_inferior = y_selecionado + 0.5

    adicionar_cobertura(limite_minimo, limite_maximo, limite_minimo, linha_superior)
    adicionar_cobertura(limite_minimo, limite_maximo, linha_inferior, limite_maximo)

    figura.add_shape(
        type="rect",
        x0=limite_minimo,
        x1=limite_maximo,
        y0=linha_superior,
        y1=linha_inferior,
        line={"width": 2, "color": "rgba(17, 24, 39, 0.75)"},
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
    "doubleClick": False,
    "editable": False,
    "edits": {
        "annotationPosition": False,
        "annotationTail": False,
        "annotationText": False,
        "axisTitleText": False,
        "colorbarPosition": False,
        "colorbarTitleText": False,
        "legendPosition": False,
        "legendText": False,
        "shapePosition": False,
        "titleText": False,
    },
    "scrollZoom": False,
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
    "staticPlot": False,
}


def renderizar_heatmap_com_destaque_linha(
    figura: go.Figure, altura: int, tamanho: int
) -> None:
    div_id = "heatmap_correlacao_interativo"
    argumentos_html = {
        "fig": figura,
        "config": PLOTLY_CONFIG,
        "full_html": False,
        "include_plotlyjs": True,
    }
    if "div_id" in inspect.signature(pio.to_html).parameters:
        argumentos_html["div_id"] = div_id

    grafico_html = pio.to_html(**argumentos_html)
    estilos_html = """
    <style>
        html,
        body {
            background: transparent;
            margin: 0;
            padding: 0;
        }
    </style>
    """
    script_hover = f"""
    <script>
    (function() {{
        const tamanho = {tamanho};
        const grafico = document.getElementById("{div_id}") ||
            document.querySelector(".plotly-graph-div");

        if (!grafico || !window.Plotly) {{
            return;
        }}

        const wrapper = grafico.parentElement;
        wrapper.style.position = "relative";

        const tooltip = document.createElement("div");
        tooltip.style.position = "absolute";
        tooltip.style.display = "none";
        tooltip.style.pointerEvents = "none";
        tooltip.style.zIndex = "1000";
        tooltip.style.maxWidth = "260px";
        tooltip.style.padding = "0.55rem 0.65rem";
        tooltip.style.border = "1px solid rgba(17, 24, 39, 0.18)";
        tooltip.style.borderRadius = "6px";
        tooltip.style.background = "rgba(255, 255, 255, 0.96)";
        tooltip.style.boxShadow = "0 8px 24px rgba(17, 24, 39, 0.18)";
        tooltip.style.color = "#111827";
        tooltip.style.fontFamily = "system-ui, -apple-system, BlinkMacSystemFont, sans-serif";
        tooltip.style.fontSize = "0.78rem";
        tooltip.style.lineHeight = "1.25";
        wrapper.appendChild(tooltip);

        const limiteMinimo = -0.5;
        const limiteMaximo = tamanho - 0.5;

        function escaparHtml(valor) {{
            return String(valor)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }}

        function centroCelula(ponto) {{
            const layout = grafico._fullLayout;
            const eixoX = layout.xaxis;
            const eixoY = layout.yaxis;
            const x = Number(ponto.x);
            const y = Number(ponto.y);

            if (
                !eixoX ||
                !eixoY ||
                Number.isNaN(x) ||
                Number.isNaN(y) ||
                typeof eixoX.l2p !== "function" ||
                typeof eixoY.l2p !== "function"
            ) {{
                const wrapperRect = wrapper.getBoundingClientRect();
                return {{
                    x: wrapperRect.width / 2,
                    y: wrapperRect.height / 2
                }};
            }}

            return {{
                x: eixoX._offset + eixoX.l2p(x),
                y: eixoY._offset + eixoY.l2p(y)
            }};
        }}

        function mostrarTooltip(ponto) {{
            const dados = ponto.customdata || [];
            tooltip.innerHTML = `
                <div style="font-weight: 700; margin-bottom: 0.2rem;">
                    ${{escaparHtml(dados[0])}} × ${{escaparHtml(dados[1])}}
                </div>
                <div>Correlação: ${{escaparHtml(dados[2])}}</div>
                <div>Classificação: ${{escaparHtml(dados[3])}}</div>
            `;
            tooltip.style.display = "block";

            const wrapperRect = wrapper.getBoundingClientRect();
            const centro = centroCelula(ponto);
            const margem = 8;

            let left = centro.x - tooltip.offsetWidth / 2;
            left = Math.max(margem, Math.min(left, wrapperRect.width - tooltip.offsetWidth - margem));

            let top = centro.y - tooltip.offsetHeight - 24;
            if (top < margem) {{
                top = centro.y + 18;
            }}
            top = Math.max(margem, Math.min(top, wrapperRect.height - tooltip.offsetHeight - margem));

            tooltip.style.left = `${{left}}px`;
            tooltip.style.top = `${{top}}px`;
        }}

        function esconderTooltip() {{
            tooltip.style.display = "none";
        }}

        function coberturaLinha(y) {{
            const linhaSuperior = y - 0.5;
            const linhaInferior = y + 0.5;
            const cobertura = "rgba(17, 24, 39, 0.42)";
            const borda = "rgba(17, 24, 39, 0.85)";

            return [
                {{
                    type: "rect",
                    xref: "x",
                    yref: "y",
                    x0: limiteMinimo,
                    x1: limiteMaximo,
                    y0: limiteMinimo,
                    y1: linhaSuperior,
                    line: {{width: 0}},
                    fillcolor: cobertura,
                    layer: "above"
                }},
                {{
                    type: "rect",
                    xref: "x",
                    yref: "y",
                    x0: limiteMinimo,
                    x1: limiteMaximo,
                    y0: linhaInferior,
                    y1: limiteMaximo,
                    line: {{width: 0}},
                    fillcolor: cobertura,
                    layer: "above"
                }},
                {{
                    type: "rect",
                    xref: "x",
                    yref: "y",
                    x0: limiteMinimo,
                    x1: limiteMaximo,
                    y0: linhaSuperior,
                    y1: linhaInferior,
                    line: {{width: 2, color: borda}},
                    fillcolor: "rgba(255, 255, 255, 0)",
                    layer: "above"
                }}
            ];
        }}

        grafico.on("plotly_hover", function(evento) {{
            if (!evento || !evento.points || !evento.points.length) {{
                return;
            }}

            const y = Number(evento.points[0].y);
            if (Number.isNaN(y)) {{
                return;
            }}

            window.Plotly.relayout(grafico, {{shapes: coberturaLinha(y)}});
            mostrarTooltip(evento.points[0]);
        }});

        grafico.on("plotly_unhover", function() {{
            window.Plotly.relayout(grafico, {{shapes: []}});
            esconderTooltip();
        }});
    }})();
    </script>
    """

    components.html(
        estilos_html + grafico_html + script_hover,
        height=altura + 32,
        scrolling=False,
    )


RESULTADO_CORRELACAO_KEY = "resultado_correlacao"
HEATMAP_DESTACADO_KEY = "celula_heatmap_destacada"
SELECOES_ATIVOS_KEY = "ativos_selecionados"
ATIVO_ADICIONAR_KEY = "ativo_para_adicionar"
AUTO_CALCULO_INICIAL_KEY = "auto_calculo_inicial_feito"


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
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
        align-items: center;
        gap: 0.25rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"] p {
        font-size: 0.76rem;
        line-height: 1.05;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] [data-testid="stButton"] {
        margin: 0;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] button {
        background: rgba(207, 48, 48, 0.10);
        border-color: rgba(207, 48, 48, 0.55);
        border-radius: 4px;
        color: #cf3030;
        min-height: 1.35rem;
        height: 1.35rem;
        padding: 0 0.45rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] button:hover {
        background: rgba(207, 48, 48, 0.18);
        border-color: rgba(207, 48, 48, 0.85);
        color: #cf3030;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] button p {
        color: #cf3030;
        font-size: 0.76rem;
        line-height: 1;
        margin: 0;
    }
    </style>
    """

st.set_page_config(
    page_title="Correlação de Ativos",
    page_icon="📊",
    layout="wide",
)

st.markdown(RESULTADOS_CSS, unsafe_allow_html=True)

st.title("Calculadora de Correlação de Ativos")
st.write(
    "Compare o comportamento de diferentes ativos e identifique possíveis casos "
    "de falsa diversificação em uma carteira Buy & Hold."
)
st.info(
    "A correlação mostra o quanto dois ativos costumam variar juntos:\n\n"
    "↳ **Perto de 100%:** tendem a subir e cair na mesma direção.\n\n"
    "↳ **Perto de 0%:** baixa relação entre seus movimentos.\n\n"
    "↳ **Perto de -100%:** tendem a variar em direções opostas."
)

catalogo_ativos = carregar_catalogo()
opcoes_catalogo = opcoes_ativos(catalogo_ativos)
ativos_padrao = tickers_para_labels(DEFAULT_TICKERS, catalogo_ativos)
opcoes_seletor = sorted(set(opcoes_catalogo + ativos_padrao))

if SELECOES_ATIVOS_KEY not in st.session_state:
    st.session_state[SELECOES_ATIVOS_KEY] = list(ativos_padrao)
else:
    st.session_state[SELECOES_ATIVOS_KEY] = deduplicar_selecoes_ativos(
        st.session_state[SELECOES_ATIVOS_KEY]
    )

if ATIVO_ADICIONAR_KEY not in st.session_state:
    st.session_state[ATIVO_ADICIONAR_KEY] = (
        None
        if selectbox_aceita_novas_opcoes() and selectbox_aceita_placeholder()
        else ""
    )
elif (
    selectbox_aceita_novas_opcoes()
    and selectbox_aceita_placeholder()
    and st.session_state[ATIVO_ADICIONAR_KEY] == ""
):
    st.session_state[ATIVO_ADICIONAR_KEY] = None

tickers_selecionados = st.session_state[SELECOES_ATIVOS_KEY]
tickers_selecionados_chaves = {
    obter_chave_selecao_ativo(selecao) for selecao in tickers_selecionados
}
opcoes_para_adicionar = [
    opcao
    for opcao in opcoes_seletor
    if obter_chave_selecao_ativo(opcao) not in tickers_selecionados_chaves
]

with st.sidebar:
    st.header("Configuração")
    renderizar_busca_ativo(opcoes_para_adicionar)
    tickers_selecionados = st.session_state[SELECOES_ATIVOS_KEY]
    st.caption(f"{len(tickers_selecionados)} ativos selecionados")
    for indice, selecao in enumerate(tickers_selecionados):
        coluna_nome, coluna_remover = st.columns(
            [6, 1],
            gap="small",
            vertical_alignment="center",
        )
        coluna_nome.markdown(escape(selecao))
        if coluna_remover.button(
            "-",
            key=f"remover_ativo_{indice}_{obter_chave_selecao_ativo(selecao)}",
            help=f"Remover {selecao}",
        ):
            remover_selecao_ativo(indice)
            st.rerun()

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

auto_calcular_inicial = (
    not st.session_state.get(AUTO_CALCULO_INICIAL_KEY, False)
    and RESULTADO_CORRELACAO_KEY not in st.session_state
)
if auto_calcular_inicial:
    st.session_state[AUTO_CALCULO_INICIAL_KEY] = True
    calcular = True

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
                    "Não foi possível obter dados para os ativos selecionados. "
                    "Confira se os tickers manuais são válidos no Yahoo Finance. "
                    f"Tickers testados: {formatar_lista_tickers(tickers)}."
                )
                st.stop()

            ativos_sem_preco = [ticker for ticker in tickers if ticker not in precos.columns]
            precos_filtrados = filtrar_ativos_com_dados_suficientes(
                precos, MIN_OBSERVATIONS
            )
            ativos_insuficientes = [
                ticker
                for ticker in tickers
                if ticker in precos.columns and ticker not in precos_filtrados.columns
            ]

            if precos_filtrados.shape[1] < 2:
                ativos_removidos = ativos_sem_preco + ativos_insuficientes
                detalhes_removidos = (
                    f" Ativos removidos: {formatar_lista_tickers(ativos_removidos)}."
                    if ativos_removidos
                    else ""
                )
                st.error(
                    "Não foi possível obter dados suficientes para pelo menos dois ativos. "
                    "Confira os códigos ou tente novamente mais tarde."
                    + detalhes_removidos
                )
                st.stop()

            retornos = calcular_retornos(
                precos_filtrados, FREQUENCY_OPTIONS[frequencia_nome]
            ).dropna(axis=1, how="all")
            ativos_sem_retorno = [
                ticker for ticker in precos_filtrados.columns if ticker not in retornos.columns
            ]
            if retornos.shape[1] < 2:
                ativos_removidos = (
                    ativos_sem_preco + ativos_insuficientes + ativos_sem_retorno
                )
                detalhes_removidos = (
                    f" Ativos removidos: {formatar_lista_tickers(ativos_removidos)}."
                    if ativos_removidos
                    else ""
                )
                st.error(
                    "Não foi possível calcular retornos suficientes para pelo menos "
                    "dois ativos."
                    + detalhes_removidos
                )
                st.stop()

            retorno_indice = None
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
                retorno_indice = retornos_indice[ticker_indice]

            retornos_alinhados, retorno_indice_alinhado = alinhar_janela_comum(
                retornos,
                retorno_indice,
            )
            if (
                retornos_alinhados.shape[1] < 2
                or len(retornos_alinhados) < MIN_COMMON_OBSERVATIONS
            ):
                st.error(
                    "A janela comum entre os ativos selecionados ficou pequena demais "
                    "para calcular a matriz. Tente reduzir a quantidade de ativos, "
                    "aumentar o período ou usar uma frequência mais frequente."
                )
                st.stop()

            if ajuste_por_benchmark:
                matriz = calcular_correlacao_residual(
                    retornos_alinhados, retorno_indice_alinhado
                )
            else:
                matriz = calcular_correlacao(retornos_alinhados)

            pares = listar_pares_correlacao(matriz)
            ativos_removidos = (
                ativos_sem_preco + ativos_insuficientes + ativos_sem_retorno
            )
            ativos_sem_sobreposicao = (
                [
                    ticker
                    for ticker in retornos_alinhados.columns
                    if ticker not in matriz.columns
                ]
                if ajuste_por_benchmark
                else []
            )
            inicio_efetivo = retornos_alinhados.index.min()
            fim_efetivo = retornos_alinhados.index.max()
            limitadores_janela = identificar_limitadores_janela(
                retornos,
                retorno_indice,
                inicio_efetivo,
            )

        st.session_state[RESULTADO_CORRELACAO_KEY] = {
            "matriz": matriz,
            "pares": pares,
            "tickers": tickers,
            "ativos_ignorados": ativos_removidos,
            "ativos_sem_sobreposicao": ativos_sem_sobreposicao,
            "ajuste_por_benchmark": ajuste_por_benchmark,
            "benchmark_nome": benchmark_nome,
            "periodo_solicitado": periodo_nome,
            "frequencia_nome": frequencia_nome,
            "inicio_efetivo": inicio_efetivo,
            "fim_efetivo": fim_efetivo,
            "observacoes": len(retornos_alinhados),
            "limitadores_janela": limitadores_janela,
        }
        st.session_state.pop(HEATMAP_DESTACADO_KEY, None)

    resultado_correlacao = st.session_state[RESULTADO_CORRELACAO_KEY]
    campos_resultado = {
        "matriz",
        "pares",
        "tickers",
        "ativos_ignorados",
        "ativos_sem_sobreposicao",
        "ajuste_por_benchmark",
        "benchmark_nome",
        "periodo_solicitado",
        "frequencia_nome",
        "inicio_efetivo",
        "fim_efetivo",
        "observacoes",
        "limitadores_janela",
    }
    if not campos_resultado.issubset(resultado_correlacao):
        st.session_state.pop(RESULTADO_CORRELACAO_KEY, None)
        st.info("Clique em Calcular correlação para atualizar a análise.")
        st.stop()

    matriz = resultado_correlacao["matriz"]
    pares = resultado_correlacao["pares"]
    tickers = resultado_correlacao["tickers"]
    ativos_ignorados = resultado_correlacao["ativos_ignorados"]
    ativos_sem_sobreposicao = resultado_correlacao["ativos_sem_sobreposicao"]
    ajuste_por_benchmark_resultado = resultado_correlacao["ajuste_por_benchmark"]
    benchmark_nome_resultado = resultado_correlacao["benchmark_nome"]
    periodo_solicitado = resultado_correlacao["periodo_solicitado"]
    frequencia_resultado = resultado_correlacao["frequencia_nome"]
    inicio_efetivo = resultado_correlacao["inicio_efetivo"]
    fim_efetivo = resultado_correlacao["fim_efetivo"]
    observacoes = resultado_correlacao["observacoes"]
    limitadores_janela = resultado_correlacao["limitadores_janela"]

    if matriz.empty or pares.empty:
        st.error(
            "Os dados em comum não foram suficientes para calcular a correlação. "
            "Tente aumentar o período ou usar uma frequência mais frequente."
        )
        st.stop()

    st.caption(
        "Período solicitado: "
        f"{periodo_solicitado} | Frequência: {frequencia_resultado} | "
        "Período efetivamente usado: "
        f"{formatar_data(inicio_efetivo)} a {formatar_data(fim_efetivo)} | "
        f"Observações: {observacoes}"
    )

    if limitadores_janela:
        st.warning(
            "A janela comum foi limitada pelo histórico mais curto de: "
            + formatar_lista_tickers(limitadores_janela)
            + "."
        )

    if ativos_ignorados:
        st.warning(
            "Ativos removidos por ticker inválido ou falta de dados suficientes: "
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
    rotulos_heatmap = [f"<b>{escape(ativo)}</b>" for ativo in ativos_heatmap]
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
                [0.0, "#1551AB"],
                [0.45, "#FFFFFF"],
                [0.5, "#FFFFFF"],
                [0.55, "#FFFFFF"],
                [1.0, "#EF6A6A"],
            ],
            zmin=-1,
            zmax=1,
            texttemplate="<b>%{text}</b>",
            textfont={"color": "#111827"},
            hoverinfo="none",
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
        ticktext=rotulos_heatmap,
        tickangle=-35 if len(ativos_heatmap) > 8 else 0,
        tickfont={"color": "#F3F4F6", "size": 12},
        fixedrange=True,
        showgrid=False,
        showspikes=False,
    )
    figura.update_yaxes(
        tickmode="array",
        tickvals=indices_heatmap,
        ticktext=rotulos_heatmap,
        autorange="reversed",
        tickfont={"color": "#F3F4F6", "size": 12},
        fixedrange=True,
        showgrid=False,
        showspikes=False,
    )
    altura_heatmap = max(420, min(760, 56 * len(ativos_heatmap) + 180))
    figura.update_layout(
        clickmode="event+select",
        dragmode=False,
        height=altura_heatmap,
        margin={"l": 72, "r": 24, "t": 92, "b": 32},
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
    )

    renderizar_heatmap_com_destaque_linha(
        figura,
        altura_heatmap,
        len(ativos_heatmap),
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
                "Correlação altíssima",
                "Correlação alta",
                "Correlação moderada",
                "Baixa correlação",
                "Descorrelação moderada",
                "Descorrelação alta",
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

"""Dashboard de manutenção preventiva (Streamlit).

    streamlit run dashboard/app.py

Lê a base de dados indicada por MANUTENCAO_DB (a mesma da API e da app de
desktop) através do pipeline em analytics/pipeline.py.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import altair as alt
import polars as pl
import streamlit as st

# Permite `streamlit run dashboard/app.py` a partir da raiz do repositório.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.pipeline import extrair, transformar  # noqa: E402
from repositorio import DB_PADRAO, VARIAVEL_AMBIENTE_DB  # noqa: E402

# Uma só série por gráfico: azul do tema, com o passo próprio para modo escuro.
AZUL = {"light": "#2a78d6", "dark": "#3987e5"}

st.set_page_config(page_title="Manutenção preventiva", layout="wide")


def cor_serie() -> str:
    try:
        tipo = st.context.theme.type or "light"
    except AttributeError:
        tipo = "light"
    return AZUL.get(tipo, AZUL["light"])


@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados(db_path: str) -> pl.DataFrame:
    return extrair(db_path)


def grafico_barras(df: pl.DataFrame, x: str, y: str, titulo_y: str, tooltip: list) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(color=cor_serie(), cornerRadiusEnd=4, size=14)
        .encode(
            x=alt.X(x, title=None, axis=alt.Axis(format="%b %Y", labelAngle=0, grid=False)),
            y=alt.Y(y, title=titulo_y, axis=alt.Axis(tickMinStep=1)),
            tooltip=tooltip,
        )
    )


# ------------------------------------------------------------------ dados
db_path = os.environ.get(VARIAVEL_AMBIENTE_DB, DB_PADRAO)

st.title("Manutenção preventiva")

if not Path(db_path).exists():
    st.info(
        f"Não encontrei a base de dados em `{db_path}`. Defina `MANUTENCAO_DB` "
        "ou gere dados de demonstração com `python -m scripts.gerar_dados_demo --db demo.db`."
    )
    st.stop()

dados = carregar_dados(db_path)

with st.sidebar:
    st.header("Filtros")
    hoje = st.date_input("Data de referência", value=date.today(), format="YYYY-MM-DD")
    maquinas = sorted(dados["nome_maquina"].unique().to_list())
    escolhidas = st.multiselect("Máquinas", maquinas, placeholder="Todas")
    st.caption(f"Base de dados: `{db_path}`")

if escolhidas:
    dados = dados.filter(pl.col("nome_maquina").is_in(escolhidas))

r = transformar(dados, hoje)
k = r.kpis.row(0, named=True)

# ------------------------------------------------------------------ KPIs
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Máquinas", k["maquinas"])
c2.metric("Pendentes", k["pendentes"])
c3.metric("Vencidas", k["vencidas"], help="Por concluir com data limite até à data de referência")
c4.metric(
    "Concluídas no prazo",
    "—" if k["taxa_no_prazo_pct"] is None else f"{k['taxa_no_prazo_pct']:.1f}%",
)
c5.metric(
    "Atraso médio",
    "—" if k["atraso_medio_dias"] is None else f"{k['atraso_medio_dias']:.1f} dias",
    help="Média de dias de atraso nas manutenções concluídas fora do prazo",
)

# ------------------------------------------------------------------ vencidas
st.subheader("Vencidas")
if r.vencidas.is_empty():
    st.success("Nenhuma manutenção vencida à data de referência.")
else:
    st.dataframe(
        r.vencidas.with_columns(
            pl.when(pl.col("dias_atraso") == 0)
            .then(pl.lit("⚠ Vence hoje"))
            .otherwise(pl.format("⛔ {} dias de atraso", pl.col("dias_atraso")))
            .alias("estado")
        ).select("maquina", "estado", "data_limite", "data_manutencao", "id"),
        hide_index=True,
        width="stretch",
        column_config={
            "maquina": "Máquina",
            "estado": "Estado",
            "data_limite": st.column_config.DateColumn("Data limite"),
            "data_manutencao": st.column_config.DateColumn("Última manutenção"),
            "id": st.column_config.NumberColumn("ID", format="%d"),
        },
    )

# ------------------------------------------------------------------ evolução
st.subheader("Evolução mensal")
if r.mensal.is_empty():
    st.info("Ainda não há manutenções concluídas.")
else:
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Manutenções concluídas por mês**")
        st.altair_chart(
            grafico_barras(
                r.mensal, "mes:T", "concluidas:Q", "Concluídas",
                [alt.Tooltip("mes:T", title="Mês", format="%B %Y"),
                 alt.Tooltip("concluidas:Q", title="Concluídas"),
                 alt.Tooltip("no_prazo:Q", title="No prazo")],
            ),
            width="stretch",
        )
    with g2:
        st.markdown("**% concluídas no prazo**")
        linha = (
            alt.Chart(r.mensal)
            .mark_line(color=cor_serie(), strokeWidth=2,
                       point=alt.OverlayMarkDef(color=cor_serie(), size=64))
            .encode(
                x=alt.X("mes:T", title=None,
                        axis=alt.Axis(format="%b %Y", labelAngle=0, grid=False)),
                y=alt.Y("taxa_no_prazo_pct:Q", title="% no prazo",
                        scale=alt.Scale(domain=[0, 100])),
                tooltip=[alt.Tooltip("mes:T", title="Mês", format="%B %Y"),
                         alt.Tooltip("taxa_no_prazo_pct:Q", title="% no prazo"),
                         alt.Tooltip("concluidas:Q", title="Concluídas")],
            )
        )
        st.altair_chart(linha, width="stretch")
        st.caption("Com poucas manutenções por mês, cada uma pesa muito na percentagem.")

# ------------------------------------------------------------------ por máquina
st.subheader("Cumprimento por máquina")
com_taxa = r.por_maquina.filter(pl.col("taxa_no_prazo_pct").is_not_null())
if not com_taxa.is_empty():
    barras = (
        alt.Chart(com_taxa)
        .mark_bar(color=cor_serie(), cornerRadiusEnd=4, size=14)
        .encode(
            y=alt.Y("maquina:N", title=None, sort=alt.EncodingSortField("taxa_no_prazo_pct")),
            x=alt.X("taxa_no_prazo_pct:Q", title="% concluídas no prazo",
                    scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(tickCount=5)),
            tooltip=[alt.Tooltip("maquina:N", title="Máquina"),
                     alt.Tooltip("taxa_no_prazo_pct:Q", title="% no prazo"),
                     alt.Tooltip("concluidas:Q", title="Concluídas"),
                     alt.Tooltip("vencidas:Q", title="Vencidas")],
        )
        .properties(height=alt.Step(26))
    )
    st.altair_chart(barras, width="stretch")

st.dataframe(
    r.por_maquina,
    hide_index=True,
    width="stretch",
    column_config={
        "maquina": "Máquina",
        "intervencoes": "Intervenções",
        "concluidas": "Concluídas",
        "vencidas": "Vencidas",
        "taxa_no_prazo_pct": st.column_config.NumberColumn("% no prazo", format="%.1f%%"),
        "intervalo_medio_dias": "Intervalo (dias)",
        "ultima_manutencao": st.column_config.DateColumn("Última manutenção"),
        "proxima_data_limite": st.column_config.DateColumn("Próxima data limite"),
    },
)
st.download_button(
    "Descarregar CSV por máquina",
    r.por_maquina.write_csv(),
    file_name=f"manutencao_por_maquina_{hoje.isoformat()}.csv",
    mime="text/csv",
)

# ------------------------------------------------------------------ qualidade
with st.expander(f"Qualidade dos dados ({r.qualidade.height} problema(s))"):
    if r.qualidade.is_empty():
        st.write("Todas as regras de qualidade passaram.")
    else:
        st.write("Estes registos foram excluídos das métricas:")
        st.dataframe(r.qualidade, hide_index=True, width="stretch")

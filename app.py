import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Carga variables de entorno desde .env (claves API para futuras secciones)
load_dotenv()

DB_PATH = "data/market.duckdb"

# --- Configuración de página ---
st.set_page_config(
    page_title="Market Intelligence CL",
    page_icon="📊",
    layout="wide",
)

# --- CSS personalizado ---
# Fondo oscuro, tarjetas con borde redondeado y tipografía moderna
st.markdown("""
<style>
  /* Fondo principal */
  .stApp {
    background-color: #0e1117;
  }

  /* Tarjetas métricas */
  [data-testid="stMetric"] {
    background-color: #1c2333;
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid #2d3748;
  }

  /* Valor principal de la métrica */
  [data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    color: #e2e8f0 !important;
  }

  /* Label de la métrica */
  [data-testid="stMetricLabel"] {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: #a0aec0 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Título principal */
  h1 {
    color: #00d4aa !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
  }

  /* Subtítulos de sección */
  h2, h3 {
    color: #e2e8f0 !important;
    font-weight: 700 !important;
  }

  /* Tabla de datos */
  [data-testid="stDataFrame"] {
    background-color: #1c2333;
    border-radius: 10px;
    border: 1px solid #2d3748;
  }

  /* Selectbox */
  [data-testid="stSelectbox"] > div > div {
    background-color: #1c2333 !important;
    border-color: #2d3748 !important;
    color: #e2e8f0 !important;
    border-radius: 8px;
  }

  /* Divisor */
  hr {
    border-color: #2d3748 !important;
    margin: 1.5rem 0 !important;
  }

  /* Caption / subtexto */
  [data-testid="stCaptionContainer"] p {
    color: #718096 !important;
    font-size: 0.85rem !important;
  }

  /* Header/toolbar superior */
  header[data-testid="stHeader"] {
    background-color: #0e1117 !important;
  }

  /* Contenedor principal */
  .block-container {
    background-color: #0e1117;
  }
</style>
""", unsafe_allow_html=True)


# --- Carga de datos ---
# st.cache_data evita re-leer DuckDB en cada interacción del usuario
@st.cache_data
def load_data() -> pd.DataFrame:
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("SELECT * FROM mart_indicators ORDER BY ticker, date").df()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


df = load_data()

# --- Encabezado ---
ultima_fecha = df["date"].max().strftime("%d/%m/%Y")
st.title("📊 Market Intelligence CL")
st.caption(f"Última actualización: {ultima_fecha}  ·  Fuente: Yahoo Finance  ·  Datos: últimos 90 días")

st.divider()

# ── SECCIÓN 1: Tarjetas de resumen por ticker ───────────────────────────────
st.subheader("Resumen del mercado")

# Último registro por ticker para mostrar precio y variación actual
resumen = (
    df.sort_values("date")
    .groupby("ticker")
    .last()
    .reset_index()[["ticker", "close", "daily_change_pct"]]
)

# Una tarjeta por ticker con st.metric — delta positivo → verde, negativo → rojo
cols = st.columns(len(resumen))
for col, (_, row) in zip(cols, resumen.iterrows()):
    variacion = row["daily_change_pct"]
    delta_str = f"{variacion:+.2f}%" if pd.notna(variacion) else "N/A"
    col.metric(
        label=row["ticker"],
        value=f"{row['close']:.2f}",
        delta=delta_str,
    )

st.divider()

# ── SECCIÓN 2: Gráfico de precios y medias móviles ──────────────────────────
st.subheader("Precios y medias móviles")

ticker_sel = st.selectbox("Selecciona un ticker", sorted(df["ticker"].unique()))
df_ticker = df[df["ticker"] == ticker_sel].sort_values("date")

fig = go.Figure()

# Línea de precio de cierre
fig.add_trace(go.Scatter(
    x=df_ticker["date"], y=df_ticker["close"],
    name="Close",
    line=dict(color="#00d4aa", width=2),
))

# Media móvil de 7 días
fig.add_trace(go.Scatter(
    x=df_ticker["date"], y=df_ticker["ma7"],
    name="MA 7",
    line=dict(color="#f6a623", width=1.5, dash="dot"),
))

# Media móvil de 30 días
fig.add_trace(go.Scatter(
    x=df_ticker["date"], y=df_ticker["ma30"],
    name="MA 30",
    line=dict(color="#ff4b6e", width=1.5, dash="dash"),
))

# Rango Y ajustado al mínimo/máximo real de los datos con margen del 3%
y_vals = pd.concat([df_ticker["close"], df_ticker["ma7"].dropna(), df_ticker["ma30"].dropna()])
y_min, y_max = y_vals.min(), y_vals.max()
y_buf = (y_max - y_min) * 0.03

# Tema oscuro con fondo transparente para integrarse al CSS de la app
fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    title=dict(
        text=f"{ticker_sel} — Últimos 90 días",
        font=dict(size=16, color="#e2e8f0"),
    ),
    xaxis=dict(title="Fecha", gridcolor="#2d3748", showline=False),
    yaxis=dict(title="Precio", gridcolor="#2d3748", showline=False, range=[y_min - y_buf, y_max + y_buf]),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right", x=1,
        bgcolor="rgba(0,0,0,0)",
    ),
    hovermode="x unified",
    margin=dict(l=0, r=0, t=50, b=0),
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── SECCIÓN 3: Tabla de últimos 30 registros ────────────────────────────────
st.subheader(f"Detalle — últimos 30 registros de {ticker_sel}")

cols_tabla = ["date", "close", "daily_change_pct", "ma7", "ma30"]
ultimos = df_ticker[cols_tabla].tail(30).sort_values("date", ascending=False).copy()

# Formatear columnas numéricas a 2 decimales para mejor legibilidad
for col in ["close", "daily_change_pct", "ma7", "ma30"]:
    ultimos[col] = ultimos[col].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")

ultimos["date"] = ultimos["date"].dt.strftime("%d/%m/%Y")
ultimos = ultimos.rename(columns={
    "date": "Fecha",
    "close": "Cierre",
    "daily_change_pct": "Var. diaria %",
    "ma7": "MA 7",
    "ma30": "MA 30",
})

ultimos_styled = ultimos.style.set_properties(**{
    "background-color": "#1c2333",
    "color": "#e2e8f0",
    "border-color": "#2d3748",
}).set_table_styles([
    {"selector": "th", "props": [("background-color", "#2d3748"), ("color", "#a0aec0"), ("border", "1px solid #2d3748")]},
    {"selector": "td", "props": [("border", "1px solid #2d3748")]},
])

st.dataframe(ultimos_styled, use_container_width=True, hide_index=True)

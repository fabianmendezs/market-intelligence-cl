import os
from datetime import datetime, timedelta

import duckdb
import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --- Carga de variables de entorno ---
load_dotenv()

DB_PATH = "data/market.duckdb"
HOY = datetime.today().strftime("%d/%m/%Y")
HACE_30_DIAS = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

NOMBRES = {
    "ECH":   "iShares MSCI Chile ETF",
    "SQM":   "Sociedad Química y Minera",
    "BCH":   "Banco de Chile (ADR)",
    "CLP=X": "Tipo de cambio USD/CLP",
    "HG=F":  "Cobre Futures",
}


# ── 1. LECTURA DE DATOS ──────────────────────────────────────────────────────
# Filtra los últimos 30 días desde mart_indicators (ya transformado por dbt)
con = duckdb.connect(DB_PATH, read_only=True)
df = con.execute(f"""
    SELECT *
    FROM mart_indicators
    WHERE date >= '{HACE_30_DIAS}'
    ORDER BY ticker, date
""").df()
con.close()

df["date"] = pd.to_datetime(df["date"])

# Último registro por ticker (datos del día más reciente)
ultimo = (
    df.sort_values("date")
    .groupby("ticker")
    .last()
    .reset_index()
)


# ── 2. CONSTRUCCIÓN DEL RESUMEN PARA GROQ ────────────────────────────────────
# Texto estructurado con métricas clave de cada activo para el prompt
lineas = []
for _, row in ultimo.iterrows():
    ticker = row["ticker"]
    nombre = NOMBRES.get(ticker, ticker)
    var = row["daily_change_pct"]
    tendencia = "por encima" if row["close"] > row["ma30"] else "por debajo"
    var_str = f"{var:+.2f}%" if pd.notna(var) else "N/D"
    lineas.append(
        f"- {nombre} ({ticker}): cierre {row['close']:.2f} | "
        f"var. diaria {var_str} | MA7 {row['ma7']:.2f} | "
        f"MA30 {row['ma30']:.2f} | precio {tendencia} de MA30"
    )

resumen_datos = "\n".join(lineas)
print("=== Datos enviados a Groq ===")
print(resumen_datos)


# ── 3. ANÁLISIS IA CON GROQ ──────────────────────────────────────────────────
# Modelo llama-3.3-70b-versatile con system prompt de analista financiero chileno
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

respuesta_groq = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {
            "role": "system",
            "content": (
                "Eres un analista financiero experto en mercados chilenos. "
                "Tu tarea es generar un resumen ejecutivo diario en español, "
                "claro y conciso, de máximo 200 palabras, explicando el comportamiento "
                "del mercado basándote en los datos entregados. Menciona los activos "
                "más relevantes, las tendencias detectadas y un punto de atención para el día."
            ),
        },
        {
            "role": "user",
            "content": f"Datos del mercado al {HOY}:\n\n{resumen_datos}",
        },
    ],
    max_tokens=400,
    temperature=0.5,
)

analisis_ia = respuesta_groq.choices[0].message.content
print("\n=== Análisis IA ===")
print(analisis_ia)


# ── 4. CONSTRUCCIÓN DEL EMAIL HTML ───────────────────────────────────────────
# Tarjetas por activo + sección de análisis IA con borde verde #00d4aa

def tarjeta_activo(row: pd.Series) -> str:
    ticker = row["ticker"]
    nombre = NOMBRES.get(ticker, ticker)
    var = row["daily_change_pct"]
    var_str = f"{var:+.2f}%" if pd.notna(var) else "N/D"
    color_var = "#00d4aa" if pd.notna(var) and var >= 0 else "#ff4b6e"
    tendencia = "▲ sobre MA30" if row["close"] > row["ma30"] else "▼ bajo MA30"
    color_tend = "#00d4aa" if row["close"] > row["ma30"] else "#ff4b6e"

    return f"""
    <div style="background:#1c2333;border-radius:12px;padding:20px;margin-bottom:12px;border:1px solid #2d3748;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div>
          <span style="font-size:0.75rem;color:#a0aec0;text-transform:uppercase;letter-spacing:0.05em;">{nombre}</span><br>
          <span style="font-size:1.1rem;font-weight:700;color:#e2e8f0;">{ticker}</span>
        </div>
        <div style="text-align:right;">
          <span style="font-size:1.4rem;font-weight:800;color:#e2e8f0;">{row['close']:.2f}</span><br>
          <span style="font-size:0.9rem;font-weight:600;color:{color_var};">{var_str}</span>
        </div>
      </div>
      <div style="display:flex;gap:16px;font-size:0.8rem;color:#718096;margin-top:8px;">
        <span>MA7: <strong style="color:#e2e8f0;">{row['ma7']:.2f}</strong></span>
        <span>MA30: <strong style="color:#e2e8f0;">{row['ma30']:.2f}</strong></span>
        <span style="color:{color_tend};font-weight:600;">{tendencia}</span>
      </div>
    </div>
    """

tarjetas_html = "".join(tarjeta_activo(row) for _, row in ultimo.iterrows())

# Párrafos del análisis IA formateados como bloques de texto
parrafos_ia = "".join(
    f'<p style="margin:0 0 10px 0;line-height:1.6;">{p.strip()}</p>'
    for p in analisis_ia.strip().split("\n")
    if p.strip()
)

html_body = f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0e1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:32px 16px;">

    <!-- Encabezado -->
    <div style="margin-bottom:28px;">
      <h1 style="margin:0 0 4px 0;font-size:1.6rem;font-weight:800;color:#00d4aa;letter-spacing:-0.02em;">
        📊 Market Intelligence CL
      </h1>
      <p style="margin:0;font-size:0.85rem;color:#718096;">
        Reporte diario · {HOY} · Fuente: Yahoo Finance
      </p>
      <p style="margin:6px 0 0 0;font-size:0.8rem;color:#718096;">
        Datos correspondientes al cierre del mercado del {HOY}.
      </p>
    </div>

    <!-- Análisis IA -->
    <div style="margin-bottom:28px;background:#1c2333;border-radius:12px;padding:24px;
                border-left:4px solid #00d4aa;border-top:1px solid #2d3748;
                border-right:1px solid #2d3748;border-bottom:1px solid #2d3748;">
      <h2 style="margin:0 0 16px 0;font-size:1rem;font-weight:700;color:#00d4aa;text-transform:uppercase;letter-spacing:0.05em;">
        🤖 Análisis IA — Llama 3.3 70B
      </h2>
      <div style="font-size:0.9rem;color:#cbd5e0;">
        {parrafos_ia}
      </div>
    </div>

    <!-- Tarjetas por activo -->
    <h2 style="margin:0 0 16px 0;font-size:1rem;font-weight:700;color:#a0aec0;text-transform:uppercase;letter-spacing:0.05em;">
      Resumen del mercado
    </h2>
    {tarjetas_html}

    <!-- Pie de página -->
    <p style="margin-top:28px;font-size:0.75rem;color:#4a5568;text-align:center;">
      Generado automáticamente · Market Intelligence CL · Los datos son referenciales y no constituyen asesoría financiera.
    </p>
  </div>
</body>
</html>
"""


# ── 5. ENVÍO POR SENDGRID ─────────────────────────────────────────────────────
# try/except para registrar el error sin abortar si falla el envío
mensaje = Mail(
    from_email=os.getenv("SMTP_USER"),
    to_emails=os.getenv("DESTINATARIO"),
    subject=f"📊 Market Intelligence CL — Cierre {HOY}",
    html_content=html_body,
)

try:
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    response = sg.send(mensaje)
    print(f"\n[OK] Email enviado correctamente (status {response.status_code})")
except Exception as e:
    print(f"\n[ERROR] Fallo al enviar el email: {e}")

import os
from datetime import datetime, timedelta

import duckdb
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# Carga variables de entorno desde .env (GROQ_API_KEY, SENDGRID_API_KEY, etc.)
load_dotenv()

# --- Configuración ---
DB_PATH = "data/market.duckdb"
TICKERS = ["ECH", "SQM", "BCH", "CLP=X", "HG=F"]
DAYS = 90

# --- Conexión a DuckDB ---
# Crea el archivo .duckdb si no existe; si existe, lo abre
con = duckdb.connect(DB_PATH)

# --- Creación de tabla ---
# UNIQUE(ticker, date) permite usar INSERT OR IGNORE para evitar duplicados
con.execute("""
    CREATE TABLE IF NOT EXISTS raw_prices (
        ticker  VARCHAR,
        date    DATE,
        open    DOUBLE,
        high    DOUBLE,
        low     DOUBLE,
        close   DOUBLE,
        volume  DOUBLE,
        UNIQUE (ticker, date)
    )
""")

# --- Descarga e inserción por ticker ---
end_date = datetime.today()
start_date = end_date - timedelta(days=DAYS)

for ticker in TICKERS:
    print(f"Descargando {ticker}...")

    df = yf.download(ticker, start=start_date, end=end_date, progress=False)

    if df.empty:
        print(f"  Sin datos para {ticker}, saltando.")
        continue

    # Aplanar columnas multi-nivel que yfinance genera cuando descarga un solo ticker
    # (ej: ("Close", "^IPSA") → "Close")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # Renombrar columnas a minúsculas para coincidir con el esquema de la tabla
    df.columns = [c.lower() for c in df.columns]

    # Eliminar filas sin precio de cierre (días sin cotización o feriados)
    df = df.dropna(subset=["close"])

    # Agregar columna ticker y convertir el índice de fecha a columna
    df["ticker"] = ticker
    df = df.reset_index().rename(columns={"Date": "date", "Datetime": "date"})

    # Insertar registros ignorando duplicados ya existentes en la tabla
    inserted = 0
    for _, row in df.iterrows():
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO raw_prices (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["ticker"],
                    row["date"],
                    row.get("open"),
                    row.get("high"),
                    row.get("low"),
                    row.get("close"),
                    row.get("volume"),
                ],
            )
            inserted += 1
        except Exception as e:
            print(f"  Error insertando fila: {e}")

    print(f"  {inserted} registros procesados para {ticker}.")

# --- Resumen final ---
total = con.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]
print(f"\nTotal de registros en raw_prices: {total}")

con.close()

# 📊 Market Intelligence CL

Pipeline automatizado de datos financieros chilenos: descarga precios diarios, los transforma con dbt y los presenta en un dashboard web con análisis de inteligencia artificial enviado por email cada día hábil.

[![Dashboard en vivo](https://img.shields.io/badge/Dashboard-markets.frmendez.com-00d4aa?style=flat-square)](https://markets.frmendez.com)

## Demo

🔗 **Dashboard en vivo:** https://markets.frmendez.com

---

## Stack

| Capa | Tecnología |
|---|---|
| Descarga de datos | yfinance |
| Base de datos | DuckDB |
| Transformaciones SQL | dbt (dbt-duckdb) |
| Dashboard web | Streamlit + Plotly |
| Análisis IA | Groq API — Llama 3.3 70B |
| Envío de email | SendGrid |
| Variables de entorno | python-dotenv |

---

## Arquitectura

```
ingest.py
    └── Descarga últimos 90 días desde Yahoo Finance (yfinance)
    └── Inserta en DuckDB → tabla raw_prices (INSERT OR IGNORE)

dbt (dbt_project/)
    └── staging/stg_prices.sql     → vista limpia sobre raw_prices
    └── marts/mart_indicators.sql  → tabla con daily_change_pct, MA7, MA30

Streamlit (app.py)
    └── Lee mart_indicators desde DuckDB
    └── Muestra tarjetas por activo, gráfico de precios y medias móviles

email_report.py
    └── Lee mart_indicators → construye resumen estructurado
    └── Envía datos a Groq (Llama 3.3 70B) → análisis en lenguaje natural
    └── Construye email HTML y lo envía vía SendGrid
```

**Flujo diario (lunes a viernes):**
```
cron → ingest.py → dbt run → email_report.py
```

---

## Activos monitoreados

| Ticker | Nombre | Tipo |
|---|---|---|
| ECH | iShares MSCI Chile ETF | ETF índice chileno |
| SQM | Sociedad Química y Minera | Acción NYSE |
| BCH | Banco de Chile ADR | Acción NYSE |
| CLP=X | Tipo de cambio USD/CLP | Forex |
| HG=F | Cobre Futures | Commodity |

---

## Deploy

La app corre en el servidor DigitalOcean (`frmendez.com`) con la siguiente configuración:

- **Streamlit** — servicio `markets.service` gestionado por **systemd** (arranque automático, reinicio ante fallos), accesible en `https://markets.frmendez.com` vía Nginx + HTTPS (Let's Encrypt)
- **Pipeline de datos** — tarea **cron** de lunes a viernes a las 12:00 UTC (08:00 Chile invierno) que ejecuta secuencialmente `ingest.py` → `dbt run` → `email_report.py`

### Instalación local

```bash
git clone https://github.com/fabianmendezs/market-intelligence-cl.git
cd market-intelligence-cl

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Completar GROQ_API_KEY, SENDGRID_API_KEY, SMTP_USER, DESTINATARIO

# Descargar datos y transformar
python ingest.py
cd dbt_project && dbt run --profiles-dir . && cd ..

# Ejecutar dashboard
streamlit run app.py

# Enviar reporte por email
python email_report.py
```

---

## Autor

**Fabián Méndez** — Analista de datos  
[LinkedIn](https://linkedin.com/in/fabianmendezs) · [GitHub](https://github.com/fabianmendezs)

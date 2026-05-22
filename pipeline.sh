#!/bin/bash
cd /var/www/market-intelligence-cl
source venv/bin/activate

echo "=== $(date) — Iniciando pipeline ===" >> logs/cron.log

python ingest.py >> logs/cron.log 2>&1
cd dbt_project && rm -rf target/ && dbt run --profiles-dir . >> ../logs/cron.log 2>&1 && cd ..
python email_report.py >> logs/cron.log 2>&1

echo "=== $(date) — Pipeline finalizado ===" >> logs/cron.log

select
    ticker,
    date,
    open,
    high,
    low,
    close,
    volume,

    -- Variación porcentual del close respecto al día anterior
    round(
        (close - lag(close) over (partition by ticker order by date))
        / lag(close) over (partition by ticker order by date) * 100,
        4
    ) as daily_change_pct,

    -- Promedio móvil de 7 días
    avg(close) over (
        partition by ticker
        order by date
        rows between 6 preceding and current row
    ) as ma7,

    -- Promedio móvil de 30 días
    avg(close) over (
        partition by ticker
        order by date
        rows between 29 preceding and current row
    ) as ma30

from {{ ref('stg_prices') }}

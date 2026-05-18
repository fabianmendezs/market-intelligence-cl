
  
  create view "market"."main"."stg_prices__dbt_tmp" as (
    select *
from raw_prices
order by ticker, date
  );

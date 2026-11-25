# Column-Level Lineage from SQL (sqlglot)

Parses a folder of warehouse SQL models and works out, **for every output column, which raw source columns it comes from**, through CTEs, joins, aliases, `SELECT *`, CASE expressions and window functions. Then it answers the question that matters before changing anything upstream: **what breaks if this column changes?**

## How it works

1. Find which tables each model reads, and order the models so each one is analyzed after its inputs (a topological sort that reports cycles and unknown tables).
2. Qualify each model's SQL against the known schemas, so `SELECT i.*` expands to real columns, and register its output columns for the models downstream.
3. Use **sqlglot's lineage walker** to trace each output column back to the input columns it's computed from.
4. Stitch the models together into one graph from `raw.*` columns to mart columns.
5. Separately record the columns each model uses in **WHERE / JOIN / GROUP BY / HAVING** as row-level dependencies (explained below).

## Sample warehouse

`raw.orders`, `raw.order_items`, `raw.customers`, `raw.products` → 3 staging models → 2 marts (customer lifetime value and margin; daily revenue by category with a window function).

```
$ python -m lineage trace mart_customer_value.lifetime_margin
mart_customer_value.lifetime_margin is computed from:
  raw.order_items.qty
  raw.order_items.unit_price
  raw.products.cost
```

That's through a CTE that aggregates `line_revenue - line_cost`, where those come from a staging model that joins items to products.

```
$ python -m lineage impact raw.orders.discount
if raw.orders.discount changes:
  values change in (3):
    mart_customer_value.lifetime_value
    mart_customer_value.value_tier
    stg_orders.net_amount
```

`python -m lineage mermaid --focus raw.products.cost` prints a Mermaid diagram of just that column's paths.

## Value lineage isn't the whole story

`raw.orders.status` only flows *as a value* into `stg_orders.status`. But the mart CTE filters on `status = 'completed'`, so a change to status values (say, `"completed"` renamed to `"complete"`) silently changes **every** column in `mart_customer_value`.

Standard column lineage, sqlglot's included, only follows values. This project also records the columns used to **filter, join or group** each model, and `impact` reports both:
- **values change in**: the column's data feeds these columns
- **which rows are counted changes in**: these columns can change because rows are filtered, joined or grouped differently

```python
g.downstream("raw.orders.status")                        # {'stg_orders.status'}
g.downstream("raw.orders.status", include_filters=True)  # 16 columns, both marts
```

## Bug fixed along the way (see the commit history)

sqlglot quotes every identifier during qualification (`"qty"`), so the first version produced names like `raw.order_items."qty"`. Those didn't match the model columns, so models never linked up and `impact raw.orders.discount` returned nothing. Normalizing the names fixed the end-to-end chain, and there are tests for it now.

## Limits
- Join keys used through a CTE alias (e.g. `o.customer_id` where `o` is a CTE) aren't traced back to their physical table in the row-level view yet.
- Models are plain SQL files. dbt's Jinja (`ref()`, macros) would need to be compiled first, for example with `dbt compile`.

## How to run

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m lineage trace mart_daily_category_revenue.share_of_day
PYTHONPATH=src python -m lineage impact raw.orders.status
pytest
```

## Next steps
- Read compiled dbt models from `target/compiled` and `manifest.json`
- Export to OpenLineage column-lineage facets

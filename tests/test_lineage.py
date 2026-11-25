import pytest

from lineage.graph import _toposort, build


@pytest.fixture(scope="module")
def g():
    return build("models", "models/sources.json")


@pytest.mark.parametrize("col,expected", [
    ("stg_orders.net_amount", {"raw.orders.amount", "raw.orders.discount"}),
    ("stg_order_items.sku", {"raw.order_items.sku"}),                       # through SELECT i.*
    ("mart_customer_value.lifetime_margin", {"raw.order_items.qty", "raw.order_items.unit_price", "raw.products.cost"}),
    ("mart_customer_value.value_tier", {"raw.orders.amount", "raw.orders.discount"}),  # through CASE + CTE
    ("mart_daily_category_revenue.share_of_day",
     {"raw.order_items.qty", "raw.order_items.unit_price", "raw.orders.ordered_at"}),  # window PARTITION BY
])
def test_trace_to_raw_columns(g, col, expected):
    assert g.upstream(col) == expected


def test_star_expands_to_all_source_columns(g):
    assert g.models["stg_order_items"][:5] == ["order_id", "line_no", "sku", "qty", "unit_price"]


def test_impact_of_a_raw_column(g):
    assert g.downstream("raw.products.cost") == {"stg_order_items.line_cost", "mart_customer_value.lifetime_margin"}


def test_filter_columns_affect_rows_not_values(g):
    assert g.downstream("raw.orders.status") == {"stg_orders.status"}
    with_rows = g.downstream("raw.orders.status", include_filters=True)
    assert "mart_customer_value.lifetime_value" in with_rows


def test_unknown_table_and_cycles_are_reported():
    with pytest.raises(ValueError, match="unknown tables"):
        _toposort({"a": "SELECT x FROM nowhere"}, set())
    with pytest.raises(ValueError, match="cycle"):
        _toposort({"a": "SELECT x FROM b", "b": "SELECT x FROM a"}, set())

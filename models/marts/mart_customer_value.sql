-- lifetime value and margin per customer
WITH orders AS (
    SELECT customer_id, order_id, order_date, net_amount
    FROM stg_orders
    WHERE status = 'completed'
),
margins AS (
    SELECT order_id, SUM(line_revenue - line_cost) AS gross_margin
    FROM stg_order_items
    GROUP BY order_id
)
SELECT
    c.customer_id,
    c.state,
    MIN(o.order_date)                       AS first_order_date,
    COUNT(o.order_id)                       AS orders,
    SUM(o.net_amount)                       AS lifetime_value,
    SUM(m.gross_margin)                     AS lifetime_margin,
    CASE WHEN SUM(o.net_amount) > 1000 THEN 'high' ELSE 'standard' END AS value_tier
FROM stg_customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.customer_id
LEFT JOIN margins AS m ON m.order_id = o.order_id
GROUP BY c.customer_id, c.state

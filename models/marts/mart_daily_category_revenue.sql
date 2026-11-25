SELECT
    o.order_date,
    i.category,
    SUM(i.line_revenue)                                                    AS revenue,
    SUM(i.line_revenue) / SUM(SUM(i.line_revenue)) OVER (PARTITION BY o.order_date) AS share_of_day
FROM stg_order_items AS i
JOIN stg_orders AS o ON o.order_id = i.order_id
GROUP BY o.order_date, i.category

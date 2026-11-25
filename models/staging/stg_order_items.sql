SELECT
    i.*,
    i.qty * i.unit_price      AS line_revenue,
    i.qty * p.cost            AS line_cost,
    p.category
FROM raw.order_items AS i
JOIN raw.products AS p ON p.sku = i.sku

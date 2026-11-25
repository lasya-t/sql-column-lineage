-- one row per order, cleaned
SELECT
    order_id,
    customer_id,
    CAST(ordered_at AS DATE)           AS order_date,
    LOWER(status)                      AS status,
    amount - COALESCE(discount, 0)     AS net_amount
FROM raw.orders
WHERE status IS NOT NULL

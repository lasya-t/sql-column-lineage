SELECT
    customer_id,
    LOWER(TRIM(email)) AS email,
    UPPER(state)       AS state,
    created_at
FROM raw.customers

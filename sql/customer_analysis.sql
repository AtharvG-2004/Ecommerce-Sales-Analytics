-- ============================================================
-- Olist E-Commerce Analytics
-- Level 4 — SQL Business Analysis
-- File: customer_analysis.sql
-- Database: DuckDB
--
-- Purpose:
-- Measure customer count, repeat purchase behavior, revenue value,
-- geography, and segmentation using the cleaned processed data.
-- ============================================================

-- Revenue definition used in this file:
-- We aggregate order payments at the order level before joining to
-- customers. This ensures each order contributes once to customer revenue
-- and avoids double-counting when an order has multiple payment rows or
-- multiple item rows.

-- ============================================================
-- Q1. How many unique customers are in the cleaned dataset?
-- ============================================================
--
-- Explanation:
-- This is the starting point for customer analysis. It tells the business
-- how large the active customer base is and gives a reliable baseline for
-- repeat purchase, retention, and revenue-per-customer metrics.
--
SELECT
    COUNT(DISTINCT customer_unique_id) AS unique_customers
FROM customers;

-- ============================================================
-- Q2. How many customers are one-time buyers vs repeat buyers?
-- ============================================================
--
-- Explanation:
-- This separates customers into one-time and repeat-purchase segments.
-- Businesses care about this because repeat buyers usually indicate stronger
-- retention and better long-term customer lifetime value.
--
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS orders_per_customer
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*) AS total_customers,
    SUM(CASE WHEN orders_per_customer = 1 THEN 1 ELSE 0 END) AS one_time_customers,
    SUM(CASE WHEN orders_per_customer > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(AVG(orders_per_customer), 2) AS avg_orders_per_customer
FROM customer_order_counts;

-- ============================================================
-- Q3. What is the customer purchase frequency distribution?
-- ============================================================
--
-- Explanation:
-- This query shows how often customers are buying across the portfolio.
-- It helps identify whether most customers buy once, a small minority buy
-- repeatedly, or the business is seeing broad repeat purchase behavior.
--
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS orders_per_customer
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
),
customer_purchase_bands AS (
    SELECT
        CASE
            WHEN orders_per_customer = 1 THEN '1 order'
            WHEN orders_per_customer BETWEEN 2 AND 3 THEN '2-3 orders'
            WHEN orders_per_customer BETWEEN 4 AND 5 THEN '4-5 orders'
            WHEN orders_per_customer BETWEEN 6 AND 10 THEN '6-10 orders'
            ELSE '11+ orders'
        END AS purchase_frequency_band,
        CASE
            WHEN orders_per_customer = 1 THEN 1
            WHEN orders_per_customer BETWEEN 2 AND 3 THEN 2
            WHEN orders_per_customer BETWEEN 4 AND 5 THEN 3
            WHEN orders_per_customer BETWEEN 6 AND 10 THEN 4
            ELSE 5
        END AS sorting_order
    FROM customer_order_counts
)
SELECT
    purchase_frequency_band,
    COUNT(*) AS customer_count
FROM customer_purchase_bands
GROUP BY purchase_frequency_band, sorting_order
ORDER BY sorting_order;

-- ============================================================
-- Q4. Which customers placed the most orders?
-- ============================================================
--
-- Explanation:
-- This identifies the most frequent buyers. It helps the business recognize
-- its most engaged customers and supports loyalty, retention, and customer
-- success efforts.
--
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id, c.customer_state
)
SELECT
    customer_unique_id,
    customer_state,
    order_count,
    ROW_NUMBER() OVER (ORDER BY order_count DESC, customer_unique_id) AS customer_rank
FROM customer_order_counts
ORDER BY order_count DESC, customer_unique_id
LIMIT 10;

-- ============================================================
-- Q5. Which customers generated the most revenue?
-- ============================================================
--
-- Explanation:
-- This is the customer value view. It answers which customers contribute the
-- most to total revenue, which is important for prioritizing loyalty offers,
-- premium support, and retention strategy.
--
WITH order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        COUNT(DISTINCT o.order_id) AS order_count,
        ROUND(SUM(opt.order_total_payment), 2) AS total_customer_revenue
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    GROUP BY c.customer_unique_id, c.customer_state
)
SELECT
    customer_unique_id,
    customer_state,
    order_count,
    total_customer_revenue,
    RANK() OVER (ORDER BY total_customer_revenue DESC) AS revenue_rank
FROM customer_revenue
ORDER BY total_customer_revenue DESC
LIMIT 10;

-- ============================================================
-- Q6. What share of total customer revenue is captured by the top customers?
-- ============================================================
--
-- Explanation:
-- This query shows whether revenue is concentrated in a small group of
-- customers. It is useful for understanding dependency risk and for deciding
-- how much effort should be placed on high-value customer retention.
--
WITH order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        ROUND(SUM(opt.order_total_payment), 2) AS total_customer_revenue
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    GROUP BY c.customer_unique_id
),
customer_ranked AS (
    SELECT
        customer_unique_id,
        total_customer_revenue,
        SUM(total_customer_revenue) OVER () AS total_revenue,
        RANK() OVER (ORDER BY total_customer_revenue DESC) AS revenue_rank
    FROM customer_revenue
)
SELECT
    customer_unique_id,
    total_customer_revenue,
    revenue_rank,
    ROUND((total_customer_revenue / total_revenue) * 100, 2) AS revenue_share_pct
FROM customer_ranked
ORDER BY revenue_rank
LIMIT 20;

-- ============================================================
-- Q7. Which customer states have the most customers and the highest revenue?
-- ============================================================
--
-- Explanation:
-- This identifies where the customer base is strongest geographically. It helps
-- the business focus marketing, warehousing, and regional support efforts on
-- the most valuable states.
--
WITH order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
state_customer_summary AS (
    SELECT
        c.customer_state,
        COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
        COUNT(DISTINCT o.order_id) AS total_orders,
        ROUND(SUM(opt.order_total_payment), 2) AS total_revenue,
        ROUND(AVG(opt.order_total_payment), 2) AS avg_order_value
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    LEFT JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    GROUP BY c.customer_state
)
SELECT
    customer_state,
    unique_customers,
    total_orders,
    total_revenue,
    avg_order_value
FROM state_customer_summary
ORDER BY total_revenue DESC;

-- ============================================================
-- Q8. Are repeat customers driving a disproportionate share of revenue?
-- ============================================================
--
-- Explanation:
-- This compares the value of one-time buyers versus repeat buyers. It helps
-- the business see whether loyalty behavior is driving most revenue or if a
-- large share of sales still comes from occasional customers.
--
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS orders_per_customer
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
),
order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        CASE
            WHEN coc.orders_per_customer = 1 THEN 'one_time'
            ELSE 'repeat'
        END AS customer_type,
        ROUND(SUM(opt.order_total_payment), 2) AS customer_revenue
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    INNER JOIN customer_order_counts AS coc
        ON c.customer_unique_id = coc.customer_unique_id
    GROUP BY c.customer_unique_id, coc.orders_per_customer
)
SELECT
    customer_type,
    COUNT(DISTINCT customer_unique_id) AS customer_count,
    ROUND(SUM(customer_revenue), 2) AS total_revenue,
    ROUND(AVG(customer_revenue), 2) AS avg_revenue_per_customer
FROM customer_revenue
GROUP BY customer_type
ORDER BY total_revenue DESC;

-- ============================================================
-- Q9. How do customer segments behave by value tier?
-- ============================================================
--
-- Explanation:
-- This creates a simple value segmentation model for the customer base. It is
-- useful for marketing teams because it highlights which customers should get
-- loyalty offers, VIP support, or reactivation campaigns.
--
WITH order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        ROUND(SUM(opt.order_total_payment), 2) AS customer_revenue
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    GROUP BY c.customer_unique_id, c.customer_state
),
segmented_customers AS (
    SELECT
        customer_unique_id,
        customer_state,
        customer_revenue,
        CASE
            WHEN NTILE(4) OVER (ORDER BY customer_revenue DESC) = 1 THEN 'Top quartile'
            WHEN NTILE(4) OVER (ORDER BY customer_revenue DESC) = 2 THEN 'Second quartile'
            WHEN NTILE(4) OVER (ORDER BY customer_revenue DESC) = 3 THEN 'Third quartile'
            ELSE 'Lowest quartile'
        END AS customer_segment,
        NTILE(4) OVER (ORDER BY customer_revenue DESC) AS value_quartile
    FROM customer_revenue
)
SELECT
    customer_segment,
    COUNT(*) AS customer_count,
    ROUND(AVG(customer_revenue), 2) AS avg_revenue_per_customer,
    ROUND(SUM(customer_revenue), 2) AS segment_revenue
FROM segmented_customers
GROUP BY customer_segment, value_quartile
ORDER BY value_quartile;

-- ============================================================
-- Q10. Which months had the highest number of active customers?
-- ============================================================
--
-- Explanation:
-- This tracks customer activity over time and helps the business understand
-- whether growth is driven by broader customer acquisition or by higher repeat
-- buying among existing customers.
--
WITH customer_orders AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
        c.customer_unique_id
    FROM orders AS o
    INNER JOIN customers AS c
        ON o.customer_id = c.customer_id
)
SELECT
    order_month,
    COUNT(DISTINCT customer_unique_id) AS active_customers,
    LAG(COUNT(DISTINCT customer_unique_id)) OVER (ORDER BY order_month) AS previous_month_active_customers
FROM customer_orders
GROUP BY order_month
ORDER BY order_month;

-- ============================================================
-- Q11. How much of customer revenue comes from repeat buyers versus first-time buyers?
-- ============================================================
--
-- Explanation:
-- This is a business-important retention metric. It tells whether repeat buyers
-- are adding meaningful incremental value or whether the business is still too
-- dependent on one-time purchases.
--
WITH customer_order_counts AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS orders_per_customer
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
),
order_payment_totals AS (
    SELECT
        order_id,
        SUM(payment_value) AS order_total_payment
    FROM order_payments
    GROUP BY order_id
),
customer_revenue AS (
    SELECT
        c.customer_unique_id,
        CASE
            WHEN coc.orders_per_customer = 1 THEN 'first_time'
            ELSE 'repeat'
        END AS customer_type,
        ROUND(SUM(opt.order_total_payment), 2) AS customer_revenue
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id
    INNER JOIN order_payment_totals AS opt
        ON o.order_id = opt.order_id
    INNER JOIN customer_order_counts AS coc
        ON c.customer_unique_id = coc.customer_unique_id
    GROUP BY c.customer_unique_id, coc.orders_per_customer
)
SELECT
    customer_type,
    ROUND(SUM(customer_revenue), 2) AS total_revenue,
    ROUND((SUM(customer_revenue) / SUM(SUM(customer_revenue)) OVER ()) * 100, 2) AS revenue_share_pct
FROM customer_revenue
GROUP BY customer_type
ORDER BY total_revenue DESC;

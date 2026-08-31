-- ============================================================
-- Olist E-Commerce Analytics
-- Level 4 — SQL Business Analysis
-- File: sales_analysis.sql
-- Database: DuckDB
--
-- Purpose:
-- Measure revenue performance, order trends, category mix,
-- geography, and sales quality using the cleaned processed data.
-- ============================================================

-- Revenue definition used in this file:
-- We use order-level payment revenue from order_payments, aggregated
-- per order, before joining to customer or category data. This avoids
-- double counting when an order has multiple payment rows or when a
-- single order contains multiple items. Category analysis uses item
-- revenue (price) to understand product mix, not to replace the core
-- order-based revenue KPI.

-- ============================================================
-- Q1. What was the total gross revenue from delivered orders?
-- ============================================================
--
-- Explanation:
-- This query answers the core business question: how much revenue the
-- company actually earned from delivered orders. We aggregate payment
-- records at the order level to avoid multiplying one order by multiple
-- order-item rows or payment records.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id
)
SELECT
    ROUND(SUM(order_total_payment), 2) AS total_revenue
FROM delivered_order_totals;

-- ============================================================
-- Q2. How many orders were delivered and what was the average order value?
-- ============================================================
--
-- Explanation:
-- This query helps the business understand sales volume and average spend
-- per completed order. It combines order count and revenue efficiency in
-- one view, which is useful for comparing performance across time periods.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id
)
SELECT
    COUNT(*) AS delivered_orders,
    ROUND(AVG(order_total_payment), 2) AS average_order_value,
    ROUND(SUM(order_total_payment), 2) AS total_revenue
FROM delivered_order_totals;

-- ============================================================
-- Q3. How did monthly revenue trend over time?
-- ============================================================
--
-- Explanation:
-- This query shows whether sales are rising, falling, or seasonal. Monthly
-- revenue tracking is a common executive KPI because it reveals demand
-- cycles, campaign impact, and promotional performance.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, DATE_TRUNC('month', o.order_purchase_timestamp)
)
SELECT
    order_month,
    ROUND(SUM(order_total_payment), 2) AS monthly_revenue
FROM delivered_order_totals
GROUP BY order_month
ORDER BY order_month;

-- ============================================================
-- Q4. Which months had revenue above the average monthly revenue level?
-- ============================================================
--
-- Explanation:
-- This identifies months that outperformed the normal sales baseline. It is
-- especially useful for spotting seasonality, promotions, or unusually high
-- customer demand.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, DATE_TRUNC('month', o.order_purchase_timestamp)
),
monthly_revenue AS (
    SELECT
        order_month,
        ROUND(SUM(order_total_payment), 2) AS monthly_revenue
    FROM delivered_order_totals
    GROUP BY order_month
)
SELECT
    order_month,
    monthly_revenue
FROM monthly_revenue
GROUP BY order_month, monthly_revenue
HAVING monthly_revenue > AVG(monthly_revenue)
ORDER BY monthly_revenue DESC;

-- ============================================================
-- Q5. Which product categories generated the most revenue?
-- ============================================================
--
-- Explanation:
-- This query reveals which product categories are driving the business.
-- A retailer can use this to focus marketing spend, inventory planning, and
-- supplier strategy on the highest-performing categories.
--
WITH delivered_orders AS (
    SELECT DISTINCT o.order_id
    FROM orders AS o
    WHERE o.order_status = 'delivered'
),
category_revenue AS (
    SELECT
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM delivered_orders AS d
    INNER JOIN order_items AS oi
        ON d.order_id = oi.order_id
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
)
SELECT
    category_name,
    category_revenue
FROM category_revenue
ORDER BY category_revenue DESC
LIMIT 10;

-- ============================================================
-- Q6. Which customer states generated the most revenue?
-- ============================================================
--
-- Explanation:
-- This helps the business understand where sales are concentrated
-- geographically. It supports regional marketing decisions, sales
-- allocation, and fulfillment planning.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        c.customer_state,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    INNER JOIN customers AS c
        ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, c.customer_state
)
SELECT
    customer_state,
    ROUND(SUM(order_total_payment), 2) AS revenue,
    COUNT(DISTINCT order_id) AS delivered_orders
FROM delivered_order_totals
GROUP BY customer_state
ORDER BY revenue DESC;

-- ============================================================
-- Q7. What share of total delivered revenue does each state contribute?
-- ============================================================
--
-- Explanation:
-- This query shows the revenue concentration across states. It helps the
-- business see whether performance is concentrated in a few regions or
-- spread across the country.
--
WITH delivered_order_totals AS (
    SELECT
        o.order_id,
        c.customer_state,
        SUM(op.payment_value) AS order_total_payment
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    INNER JOIN customers AS c
        ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, c.customer_state
),
state_revenue AS (
    SELECT
        customer_state,
        ROUND(SUM(order_total_payment), 2) AS state_revenue
    FROM delivered_order_totals
    GROUP BY customer_state
),
revenue_summary AS (
    SELECT
        customer_state,
        state_revenue,
        SUM(state_revenue) OVER () AS total_revenue,
        RANK() OVER (ORDER BY state_revenue DESC) AS revenue_rank
    FROM state_revenue
)
SELECT
    customer_state,
    state_revenue,
    ROUND((state_revenue / total_revenue) * 100, 2) AS revenue_share_pct,
    revenue_rank
FROM revenue_summary
ORDER BY revenue_rank;

-- ============================================================
-- Q8. How did monthly revenue change compared with the previous month?
-- ============================================================
--
-- Explanation:
-- This compares each month against the prior month to highlight momentum.
-- A business can use this to understand growth or decline trends before
-- making marketing or inventory decisions.
--
WITH delivered_order_totals AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
        SUM(op.payment_value) AS monthly_revenue
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
)
SELECT
    order_month,
    ROUND(monthly_revenue, 2) AS monthly_revenue,
    LAG(monthly_revenue) OVER (ORDER BY order_month) AS previous_month_revenue,
    ROUND(monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY order_month), 2) AS revenue_change_vs_prev_month,
    ROUND(
        ((monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY order_month))
        / NULLIF(LAG(monthly_revenue) OVER (ORDER BY order_month), 0)) * 100,
        2
    ) AS pct_change_vs_prev_month
FROM delivered_order_totals
ORDER BY order_month;

-- ============================================================
-- Q9. Which payment methods drive the most revenue?
-- ============================================================
--
-- Explanation:
-- This query helps the business understand which payment methods customers
-- prefer most and which channels are most valuable. It is useful for
-- operational planning, partner management, and customer experience work.
--
WITH order_payments_summary AS (
    SELECT
        o.order_id,
        o.order_status,
        op.payment_type,
        op.payment_value
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
)
SELECT
    payment_type,
    ROUND(SUM(payment_value), 2) AS total_revenue,
    ROUND(AVG(payment_value), 2) AS avg_payment_value,
    COUNT(DISTINCT order_id) AS completed_orders
FROM order_payments_summary
GROUP BY payment_type
ORDER BY total_revenue DESC;

-- ============================================================
-- Q10. Which product categories rank highest by revenue, and how much of total category revenue do they represent?
-- ============================================================
--
-- Explanation:
-- This query ranks categories by revenue and shows their share of the total
-- category mix. It is valuable for prioritizing portfolio decisions and
-- identifying where the business is most dependent on a few categories.
--
WITH delivered_orders AS (
    SELECT DISTINCT o.order_id
    FROM orders AS o
    WHERE o.order_status = 'delivered'
),
category_revenue AS (
    SELECT
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM delivered_orders AS d
    INNER JOIN order_items AS oi
        ON d.order_id = oi.order_id
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
),
category_ranked AS (
    SELECT
        category_name,
        category_revenue,
        SUM(category_revenue) OVER () AS total_category_revenue,
        RANK() OVER (ORDER BY category_revenue DESC) AS revenue_rank
    FROM category_revenue
)
SELECT
    category_name,
    category_revenue,
    revenue_rank,
    ROUND((category_revenue / total_category_revenue) * 100, 2) AS category_share_pct
FROM category_ranked
ORDER BY revenue_rank
LIMIT 10;
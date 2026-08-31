-- ============================================================
-- Olist E-Commerce Analytics
-- Level 4 — SQL Business Analysis
-- File: delivery_analysis.sql
-- Database: DuckDB
--
-- Purpose:
-- Measure delivery speed, completeness, late-delivery risk, and the
-- relationship between delivery performance and customer experience.
-- ============================================================

-- Delivery logic used in this file:
-- - Purchase-to-delivery time is calculated as the difference between
--   order_purchase_timestamp and order_delivered_customer_date.
-- - Purchase-to-estimated time is calculated as the difference between
--   order_purchase_timestamp and order_estimated_delivery_date.
-- - Late delivery is defined as actual delivery date greater than the
--   estimated delivery date.
-- - Orders without required timestamps are excluded from the delivery-time
--   calculations, because a missing date would make the calculation invalid.
-- - Cancelled or unavailable orders are not treated as on-time deliveries;
--   they are excluded from the main delivery performance analysis because
--   the business question is about completed delivery experience.

-- ============================================================
-- Q1. What is the average delivery time for delivered orders?
-- ============================================================
--
-- Explanation:
-- This is the core delivery-speed metric. It helps the business understand how
-- quickly orders move from purchase to final delivery and whether the carrier
-- network is meeting customer expectations.
--
SELECT
    ROUND(AVG(DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date)), 2) AS avg_delivery_days
FROM orders
WHERE order_status = 'delivered'
    AND order_purchase_timestamp IS NOT NULL
    AND order_delivered_customer_date IS NOT NULL;

-- ============================================================
-- Q2. How is delivery time distributed across orders?
-- ============================================================
--
-- Explanation:
-- This shows whether delivery performance is clustered around a typical lead
-- time or whether the business has a wide range of delivery experiences. It is
-- useful for spotting operational outliers or seasonal instability.
--
WITH delivery_days AS (
    SELECT
        DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date) AS delivery_days
    FROM orders
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp IS NOT NULL
      AND order_delivered_customer_date IS NOT NULL
)
SELECT
    MIN(delivery_days) AS min_delivery_days,
    ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days) AS median_delivery_days,
    MAX(delivery_days) AS max_delivery_days
FROM delivery_days;

-- ============================================================
-- Q3. What is the average delivery time by customer state?
-- ============================================================
--
-- Explanation:
-- This identifies which states experience the fastest or slowest fulfillment.
-- A business can use this to target regional logistics improvements and
-- evaluate operational consistency across geographies.
--
WITH delivered_orders AS (
    SELECT
        o.customer_id,
        c.customer_state,
        DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_days
    FROM orders AS o
    INNER JOIN customers AS c
        ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT
    customer_state,
    ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
    COUNT(*) AS delivered_orders
FROM delivered_orders
GROUP BY customer_state
ORDER BY avg_delivery_days DESC;

-- ============================================================
-- Q4. How does actual delivery time compare with the estimated delivery date?
-- ============================================================
--
-- Explanation:
-- This answers whether the business is delivering faster or slower than its
-- promised delivery window. It is a critical operational metric because it
-- connects service quality to customer expectation.
--
WITH delivery_window AS (
    SELECT
        order_id,
        order_purchase_timestamp,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date) AS actual_days,
        DATE_DIFF('day', order_purchase_timestamp, order_estimated_delivery_date) AS estimated_days
    FROM orders
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp IS NOT NULL
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
)
SELECT
    ROUND(AVG(actual_days - estimated_days), 2) AS avg_gap_vs_estimate,
    MIN(actual_days - estimated_days) AS best_gap_days,
    MAX(actual_days - estimated_days) AS worst_gap_days
FROM delivery_window;

-- ============================================================
-- Q5. What percentage of delivered orders were late?
-- ============================================================
--
-- Explanation:
-- This is a direct measure of service reliability. Late deliveries are a
-- customer-experience risk and often correlate with lower satisfaction and
-- higher support cost.
--
WITH late_delivery_check AS (
    SELECT
        order_id,
        CASE
            WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1
            ELSE 0
        END AS is_late
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
)
SELECT
    ROUND(AVG(is_late) * 100, 2) AS late_delivery_pct,
    SUM(is_late) AS late_orders,
    COUNT(*) AS delivered_orders
FROM late_delivery_check;

-- ============================================================
-- Q6. Which customer states have the highest late-delivery rate?
-- ============================================================
--
-- Explanation:
-- This identifies whether some regions experience materially worse delivery
-- performance. It supports targeted operations, carrier management, and
-- customer communication strategies.
--
WITH late_delivery_by_state AS (
    SELECT
        c.customer_state,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
            ELSE 0
        END AS is_late
    FROM orders AS o
    INNER JOIN customers AS c
        ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT
    customer_state,
    ROUND(AVG(is_late) * 100, 2) AS late_delivery_pct,
    SUM(is_late) AS late_orders,
    COUNT(*) AS delivered_orders
FROM late_delivery_by_state
GROUP BY customer_state
ORDER BY late_delivery_pct DESC;

-- ============================================================
-- Q7. Which product categories have the highest late-delivery rate?
-- ============================================================
--
-- Explanation:
-- This connects product mix with fulfillment risk. To avoid distortions from
-- multiple item rows per order, the late flag is first established at the order
-- level and then assigned to each category associated with that order. This
-- preserves the correct order + category grain before the late-delivery rate is
-- calculated.
--
WITH order_category_late AS (
    SELECT
        o.order_id,
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        MAX(CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
            ELSE 0
        END) AS is_late
    FROM orders AS o
    INNER JOIN order_items AS oi
        ON o.order_id = oi.order_id
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY o.order_id, COALESCE(ct.product_category_name_english, p.product_category_name)
)
SELECT
    category_name,
    ROUND(AVG(is_late) * 100, 2) AS late_delivery_pct,
    SUM(is_late) AS late_orders,
    COUNT(*) AS delivered_orders
FROM order_category_late
GROUP BY category_name
ORDER BY late_delivery_pct DESC
LIMIT 10;

-- ============================================================
-- Q8. How has delivery performance changed over time?
-- ============================================================
--
-- Explanation:
-- This tracks whether delivery reliability is improving or worsening across
-- time. It helps with operational planning and highlights whether service
-- quality is stable across the business lifecycle.
--
WITH monthly_delivery AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
        COUNT(*) AS total_orders,
        ROUND(AVG(DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date)), 2) AS avg_delivery_days,
        ROUND(AVG(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) * 100, 2) AS late_delivery_pct
    FROM orders AS o
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
)
SELECT
    order_month,
    total_orders,
    avg_delivery_days,
    late_delivery_pct,
    LAG(avg_delivery_days) OVER (ORDER BY order_month) AS previous_month_avg_delivery_days
FROM monthly_delivery
ORDER BY order_month;

-- ============================================================
-- Q9. Do late deliveries have lower review scores?
-- ============================================================
--
-- Explanation:
-- This explores whether delivery delays are associated with poorer customer
-- satisfaction. It is an insight query, not proof of causation, but it helps
-- identify whether operational delays may be affecting customer sentiment.
--
WITH delivery_reviews AS (
    SELECT
        o.order_id,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'late'
            ELSE 'on_time'
        END AS delivery_status,
        AVG(r.review_score) AS avg_review_score,
        COUNT(r.review_score) AS review_count
    FROM orders AS o
    LEFT JOIN order_reviews AS r
        ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY o.order_id, o.order_delivered_customer_date, o.order_estimated_delivery_date
)
SELECT
    delivery_status,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    SUM(review_count) AS total_reviews
FROM delivery_reviews
GROUP BY delivery_status
ORDER BY avg_review_score ASC;

-- ============================================================
-- Q9A. What is the correlation between delivery delay and review score?
-- ============================================================
--
-- Explanation:
-- This measures the statistical association between delivery delay and review
-- score using an order-level dataset. It helps determine whether faster delivery
-- is associated with stronger customer feedback, without implying causation.
--
WITH order_delay_review AS (
    SELECT
        o.order_id,
        DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_days,
        AVG(r.review_score) AS avg_review_score
    FROM orders AS o
    INNER JOIN order_reviews AS r
        ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
      AND r.review_score IS NOT NULL
    GROUP BY o.order_id, o.order_purchase_timestamp, o.order_delivered_customer_date
),
order_delay_review_with_means AS (
    SELECT
        delivery_days,
        avg_review_score,
        AVG(delivery_days) OVER () AS avg_delivery_days,
        AVG(avg_review_score) OVER () AS avg_review_score_global
    FROM order_delay_review
)
SELECT
    ROUND(
        SUM((delivery_days - avg_delivery_days) * (avg_review_score - avg_review_score_global)) /
        SQRT(
            SUM(POWER(delivery_days - avg_delivery_days, 2)) *
            SUM(POWER(avg_review_score - avg_review_score_global, 2))
        ),
        4
    ) AS pearson_correlation_delivery_days_vs_review_score,
    COUNT(*) AS orders_with_reviews
FROM order_delay_review_with_means;

-- ============================================================
-- Q10. How do review scores vary by delivery-time bands?
-- ============================================================
--
-- Explanation:
-- This groups delivery performance into time bands to understand whether longer
-- waits are associated with lower review sentiment. This is useful for setting
-- service standards and identifying where delays become customer-visible.
--
WITH delivery_review_bands AS (
    SELECT
        o.order_id,
        CASE
            WHEN DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) <= 7 THEN '0-7 days'
            WHEN DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) <= 14 THEN '8-14 days'
            WHEN DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) <= 21 THEN '15-21 days'
            ELSE '22+ days'
        END AS delivery_band,
        AVG(r.review_score) AS avg_review_score
    FROM orders AS o
    LEFT JOIN order_reviews AS r
        ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
    GROUP BY o.order_id, DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
)
SELECT
    delivery_band,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    COUNT(*) AS orders_with_reviews
FROM delivery_review_bands
GROUP BY delivery_band
ORDER BY
    CASE
        WHEN delivery_band = '0-7 days' THEN 1
        WHEN delivery_band = '8-14 days' THEN 2
        WHEN delivery_band = '15-21 days' THEN 3
        ELSE 4
    END;

-- ============================================================
-- Q11. Which payment methods are used most often for delivered orders, and how do they compare on late-delivery rate?
-- ============================================================
--
-- Explanation:
-- This helps the business understand whether payment type is associated with
-- delivery reliability. It is useful for operational and customer experience
-- analysis, but it is not interpreted as proof that payment type causes delay.
--
WITH payment_delivery AS (
    SELECT
        o.order_id,
        o.order_status,
        op.payment_type,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
            ELSE 0
        END AS is_late
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT
    payment_type,
    COUNT(DISTINCT order_id) AS delivered_orders,
    ROUND(AVG(is_late) * 100, 2) AS late_delivery_pct,
    ROUND(SUM(is_late) / COUNT(DISTINCT order_id) * 100, 2) AS late_delivery_rate
FROM payment_delivery
GROUP BY payment_type
ORDER BY delivered_orders DESC;

-- ============================================================
-- Q12. How do installment patterns relate to delivery performance?
-- ============================================================
--
-- Explanation:
-- This query checks whether orders with more payment installments behave
-- differently in terms of delivery performance. Installments are a behavioral
-- signal, not a causal explanation, but they can help identify customer or
-- product segments associated with different delivery experience.
--
WITH payment_delivery AS (
    SELECT
        o.order_id,
        MAX(op.payment_installments) AS max_installments,
        CASE
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1
            ELSE 0
        END AS is_late
    FROM orders AS o
    INNER JOIN order_payments AS op
        ON o.order_id = op.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY o.order_id, o.order_delivered_customer_date, o.order_estimated_delivery_date
),
installment_bands AS (
    SELECT
        order_id,
        CASE
            WHEN max_installments <= 1 THEN '1 installment'
            WHEN max_installments BETWEEN 2 AND 4 THEN '2-4 installments'
            WHEN max_installments BETWEEN 5 AND 8 THEN '5-8 installments'
            ELSE '9+ installments'
        END AS installment_band,
        is_late
    FROM payment_delivery
)
SELECT
    installment_band,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(is_late) * 100, 2) AS late_delivery_pct
FROM installment_bands
GROUP BY installment_band
ORDER BY
    CASE
        WHEN installment_band = '1 installment' THEN 1
        WHEN installment_band = '2-4 installments' THEN 2
        WHEN installment_band = '5-8 installments' THEN 3
        ELSE 4
    END;

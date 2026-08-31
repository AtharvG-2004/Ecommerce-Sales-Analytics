-- ============================================================
-- Olist E-Commerce Analytics
-- Level 4 — SQL Business Analysis
-- File: product_analysis.sql
-- Database: DuckDB
--
-- Purpose:
-- Evaluate product performance, category concentration, and seller
-- contribution using the cleaned processed data.
-- ============================================================

-- Revenue definition used in this file:
-- We use item-level revenue from order_items.price, because product and
-- seller analysis is naturally evaluated at the order-item grain. We do
-- not join payment rows into this logic, because that would overstate
-- revenue by multiplying a single order by multiple item rows. The
-- business question here is product/category/seller contribution, not
-- order-level payment value.

-- ============================================================
-- Q1. Which products generate the most revenue?
-- ============================================================
--
-- Explanation:
-- This identifies the products contributing the most sales revenue. It helps
-- the business focus assortment decisions, marketing spend, and inventory on
-- the products driving the largest share of revenue.
--
WITH item_revenue AS (
    SELECT
        oi.product_id,
        ROUND(SUM(oi.price), 2) AS revenue
    FROM order_items AS oi
    GROUP BY oi.product_id
)
SELECT
    p.product_id,
    COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
    ROUND(ir.revenue, 2) AS total_revenue
FROM item_revenue AS ir
INNER JOIN products AS p
    ON ir.product_id = p.product_id
LEFT JOIN category_translation AS ct
    ON p.product_category_name = ct.product_category_name
ORDER BY ir.revenue DESC
LIMIT 10;

-- ============================================================
-- Q2. Which products generate the least revenue?
-- ============================================================
--
-- Explanation:
-- This surfaces products with the lowest revenue contribution. It helps the
-- business spot underperforming inventory, low-demand SKUs, or pricing issues.
--
WITH item_revenue AS (
    SELECT
        oi.product_id,
        ROUND(SUM(oi.price), 2) AS revenue
    FROM order_items AS oi
    GROUP BY oi.product_id
)
SELECT
    p.product_id,
    COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
    ROUND(ir.revenue, 2) AS total_revenue
FROM item_revenue AS ir
INNER JOIN products AS p
    ON ir.product_id = p.product_id
LEFT JOIN category_translation AS ct
    ON p.product_category_name = ct.product_category_name
ORDER BY ir.revenue ASC
LIMIT 10;

-- ============================================================
-- Q3. Which products were sold most often by quantity?
-- ============================================================
--
-- Explanation:
-- This query answers which products sold the most items in total. It is a
-- strong operational metric for understanding demand volume, stock turnover,
-- and the products that move the greatest number of units.
--
WITH product_quantity AS (
    SELECT
        oi.product_id,
        COUNT(*) AS items_sold
    FROM order_items AS oi
    GROUP BY oi.product_id
)
SELECT
    pq.product_id,
    COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
    pq.items_sold AS units_sold,
    ROW_NUMBER() OVER (ORDER BY pq.items_sold DESC) AS quantity_rank
FROM product_quantity AS pq
INNER JOIN products AS p
    ON pq.product_id = p.product_id
LEFT JOIN category_translation AS ct
    ON p.product_category_name = ct.product_category_name
ORDER BY pq.items_sold DESC
LIMIT 10;

-- ============================================================
-- Q4. Which product categories generate the most revenue?
-- ============================================================
--
-- Explanation:
-- This identifies the categories contributing the most sales revenue. It helps
-- the business understand which product families are most valuable and where
-- strategic investment should be focused.
--
WITH category_revenue AS (
    SELECT
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
)
SELECT
    category_name,
    category_revenue,
    RANK() OVER (ORDER BY category_revenue DESC) AS revenue_rank
FROM category_revenue
ORDER BY category_revenue DESC
LIMIT 10;

-- ============================================================
-- Q5. Which product categories generate the least revenue?
-- ============================================================
--
-- Explanation:
-- This highlights categories with weak revenue contribution. It is useful for
-- understanding underperforming product lines and deciding whether to invest,
-- optimize, or discontinue them.
--
WITH category_revenue AS (
    SELECT
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
)
SELECT
    category_name,
    category_revenue,
    RANK() OVER (ORDER BY category_revenue ASC) AS revenue_rank_lowest
FROM category_revenue
ORDER BY category_revenue ASC
LIMIT 10;

-- ============================================================
-- Q6. What share of total product revenue comes from each product category?
-- ============================================================
--
-- Explanation:
-- This shows the category mix of the business. It helps the company see how
-- concentrated revenue is across categories and whether a few categories drive
-- most of the sales.
--
WITH category_revenue AS (
    SELECT
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM order_items AS oi
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
        SUM(category_revenue) OVER () AS total_revenue,
        RANK() OVER (ORDER BY category_revenue DESC) AS revenue_rank
    FROM category_revenue
)
SELECT
    category_name,
    category_revenue,
    ROUND((category_revenue / total_revenue) * 100, 2) AS category_share_pct,
    revenue_rank
FROM category_ranked
ORDER BY revenue_rank;

-- ============================================================
-- Q7. Which sellers generate the most revenue?
-- ============================================================
--
-- Explanation:
-- This identifies the top sellers by revenue contribution. It helps the
-- business understand which sellers drive the most value and where partner
-- relationships deserve attention.
--
WITH seller_revenue AS (
    SELECT
        oi.seller_id,
        ROUND(SUM(oi.price), 2) AS seller_revenue,
        COUNT(*) AS item_count
    FROM order_items AS oi
    GROUP BY oi.seller_id
)
SELECT
    sr.seller_id,
    s.seller_city,
    s.seller_state,
    sr.seller_revenue,
    sr.item_count,
    RANK() OVER (ORDER BY sr.seller_revenue DESC) AS revenue_rank
FROM seller_revenue AS sr
LEFT JOIN sellers AS s
    ON sr.seller_id = s.seller_id
ORDER BY sr.seller_revenue DESC
LIMIT 10;

-- ============================================================
-- Q8. Which sellers perform best by order and item volume?
-- ============================================================
--
-- Explanation:
-- This query combines seller revenue with operational activity. It helps the
-- company see whether a seller is successful because of high value per order,
-- high sales volume, or both.
--
WITH seller_metrics AS (
    SELECT
        oi.seller_id,
        COUNT(DISTINCT oi.order_id) AS unique_orders,
        COUNT(*) AS items_sold,
        ROUND(SUM(oi.price), 2) AS revenue
    FROM order_items AS oi
    GROUP BY oi.seller_id
)
SELECT
    sm.seller_id,
    s.seller_city,
    s.seller_state,
    sm.unique_orders,
    sm.items_sold,
    sm.revenue,
    DENSE_RANK() OVER (ORDER BY sm.revenue DESC) AS revenue_rank
FROM seller_metrics AS sm
LEFT JOIN sellers AS s
    ON sm.seller_id = s.seller_id
ORDER BY sm.revenue DESC
LIMIT 10;

-- ============================================================
-- Q9. Which sellers perform best within each category?
-- ============================================================
--
-- Explanation:
-- This shows how sellers perform across categories, which helps the business
-- identify category specialists and evaluate whether a seller is dominant in a
-- particular product family.
--
WITH seller_category_revenue AS (
    SELECT
        oi.seller_id,
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue,
        COUNT(*) AS items_sold
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY oi.seller_id, COALESCE(ct.product_category_name_english, p.product_category_name)
),
ranked_sellers AS (
    SELECT
        seller_id,
        category_name,
        category_revenue,
        items_sold,
        ROW_NUMBER() OVER (PARTITION BY category_name ORDER BY category_revenue DESC) AS seller_rank_in_category
    FROM seller_category_revenue
)
SELECT
    category_name,
    seller_id,
    category_revenue,
    items_sold,
    seller_rank_in_category
FROM ranked_sellers
WHERE seller_rank_in_category <= 5
ORDER BY category_name, seller_rank_in_category;

-- ============================================================
-- Q10. What is the price distribution for products in the catalog?
-- ============================================================
--
-- Explanation:
-- This highlights how expensive the catalog is and whether the business is
-- driven by premium or low-price products. Price distribution matters because
-- it affects margin, basket size, and customer acquisition strategy.
--
WITH product_price_summary AS (
    SELECT
        p.product_id,
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(AVG(oi.price), 2) AS avg_sold_price,
        ROUND(MIN(oi.price), 2) AS min_price,
        ROUND(MAX(oi.price), 2) AS max_price,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY oi.price), 2) AS median_price
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY p.product_id, COALESCE(ct.product_category_name_english, p.product_category_name)
)
SELECT
    category_name,
    ROUND(AVG(avg_sold_price), 2) AS avg_price_by_category,
    ROUND(MIN(min_price), 2) AS lowest_price_in_category,
    ROUND(MAX(max_price), 2) AS highest_price_in_category,
    ROUND(AVG(median_price), 2) AS avg_median_price
FROM product_price_summary
GROUP BY category_name
ORDER BY avg_price_by_category DESC
LIMIT 10;

-- ============================================================
-- Q11. Which categories are most concentrated in the top seller mix?
-- ============================================================
--
-- Explanation:
-- This helps the business understand whether the strongest sellers are heavily
-- concentrated in a few categories or spread across the catalog. It supports
-- merchandising and supplier diversification decisions.
--
WITH seller_category_revenue AS (
    SELECT
        oi.seller_id,
        COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
        ROUND(SUM(oi.price), 2) AS category_revenue
    FROM order_items AS oi
    INNER JOIN products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN category_translation AS ct
        ON p.product_category_name = ct.product_category_name
    GROUP BY oi.seller_id, COALESCE(ct.product_category_name_english, p.product_category_name)
),
category_share_by_seller AS (
    SELECT
        seller_id,
        category_name,
        category_revenue,
        SUM(category_revenue) OVER (PARTITION BY seller_id) AS seller_total_revenue,
        NTILE(4) OVER (PARTITION BY seller_id ORDER BY category_revenue DESC) AS category_quartile
    FROM seller_category_revenue
)
SELECT
    seller_id,
    category_name,
    category_revenue,
    ROUND((category_revenue / seller_total_revenue) * 100, 2) AS category_share_of_seller_revenue,
    category_quartile
FROM category_share_by_seller
ORDER BY seller_id, category_quartile, category_revenue DESC
LIMIT 20;
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "olist.duckdb"

st.set_page_config(
    page_title="Olist E-Commerce Analytics",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_db() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    return duckdb.connect(database=str(DB_PATH), read_only=True)


@st.cache_data
def get_date_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    con = get_db()
    result = con.execute(
        """
        SELECT MIN(order_purchase_timestamp)::DATE AS min_date,
               MAX(order_purchase_timestamp)::DATE AS max_date
        FROM orders
        WHERE order_purchase_timestamp IS NOT NULL
        """
    ).fetchone()
    if not result or result[0] is None or result[1] is None:
        today = pd.Timestamp.today().normalize()
        return today, today
    return pd.Timestamp(result[0]), pd.Timestamp(result[1])


@st.cache_data
def get_category_options() -> list[str]:
    con = get_db()
    df = con.execute(
        """
        SELECT DISTINCT COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
        WHERE COALESCE(ct.product_category_name_english, p.product_category_name) IS NOT NULL
        ORDER BY category_name
        """
    ).fetchdf()
    return df["category_name"].astype(str).tolist()


@st.cache_data
def get_state_options() -> list[str]:
    con = get_db()
    df = con.execute(
        "SELECT DISTINCT customer_state FROM customers WHERE customer_state IS NOT NULL ORDER BY customer_state"
    ).fetchdf()
    return df["customer_state"].astype(str).tolist()


def build_category_filter(
    values: list[str],
    expr: str = "COALESCE(ct.product_category_name_english, p.product_category_name)",
    order_alias: str = "o",
) -> tuple[str, list[str]]:
    if not values:
        return "", []
    placeholders = ", ".join(["?"] * len(values))
    return f"""
        AND EXISTS (
            SELECT 1
            FROM order_items oi
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE oi.order_id = {order_alias}.order_id
              AND {expr} IN ({placeholders})
        )
    """, list(values)


def build_state_filter(values: list[str], expr: str = "c.customer_state") -> tuple[str, list[str]]:
    if not values:
        return "", []
    placeholders = ", ".join(["?"] * len(values))
    return f" AND {expr} IN ({placeholders})", list(values)


@st.cache_data
def get_customer_value_thresholds() -> tuple[float, float]:
    con = get_db()
    df = con.execute(
        """
        WITH customer_revenue AS (
            SELECT c.customer_unique_id,
                   SUM(op.payment_value) AS revenue
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id
            JOIN order_payments op ON op.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        )
        SELECT PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue) AS q1,
               PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue) AS q3
        FROM customer_revenue
        """
    ).fetchdf()
    q1 = float(df["q1"].iloc[0]) if not df.empty else 0.0
    q3 = float(df["q3"].iloc[0]) if not df.empty else 0.0
    return q1, q3


@st.cache_data
def get_orders_base(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH filtered_orders AS (
            SELECT o.order_id,
                   o.customer_id,
                   c.customer_state,
                   c.customer_unique_id,
                   o.order_status,
                   o.order_purchase_timestamp,
                   o.order_delivered_customer_date,
                   o.order_estimated_delivery_date
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
        )
        SELECT DISTINCT * FROM filtered_orders
    """
    params = [date_start, date_end, *params]
    df = con.execute(query, params).fetchdf()
    if df.empty:
        return pd.DataFrame(columns=[
            "order_id","customer_id","customer_state","customer_unique_id",
            "order_status","order_purchase_timestamp","order_delivered_customer_date",
            "order_estimated_delivery_date"
        ])
    return df


@st.cache_data
def get_order_items_base(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH filtered_item_orders AS (
            SELECT o.order_id,
                   o.customer_id,
                   c.customer_state,
                   oi.product_id,
                   p.product_category_name,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   oi.price,
                   oi.freight_value,
                   oi.seller_id,
                   o.order_purchase_timestamp,
                   o.order_status
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
        )
        SELECT * FROM filtered_item_orders
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_review_base(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH filtered_review_orders AS (
            SELECT o.order_id,
                   o.order_status,
                   o.order_purchase_timestamp,
                   o.order_delivered_customer_date,
                   o.order_estimated_delivery_date,
                   c.customer_state,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   r.review_score
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_reviews r ON r.order_id = o.order_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              {category_filter}
              {state_filter}
        )
        SELECT * FROM filtered_review_orders
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_kpi_cards(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH base AS (
            SELECT o.order_id,
                   o.order_status,
                   o.order_purchase_timestamp,
                   o.customer_id,
                   c.customer_state,
                   c.customer_unique_id,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   op.payment_value,
                   r.review_score
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            LEFT JOIN order_reviews r ON r.order_id = o.order_id
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
        )
        SELECT
            ROUND(SUM(CASE WHEN order_status = 'delivered' THEN payment_value ELSE 0 END), 2) AS total_revenue,
            COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END) AS total_orders,
            ROUND(AVG(CASE WHEN order_status = 'delivered' THEN payment_value END), 2) AS aov,
            ROUND(AVG(review_score), 2) AS avg_review_score,
            COUNT(DISTINCT customer_unique_id) AS total_customers
        FROM base
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_revenue_trend(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH revenue_by_month AS (
            SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
                   ROUND(SUM(op.payment_value), 2) AS revenue
            FROM orders o
            JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              {category_filter}
              {state_filter}
            GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
        )
        SELECT * FROM revenue_by_month ORDER BY month
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_orders_trend(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH orders_by_month AS (
            SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
                   COUNT(DISTINCT o.order_id) AS orders
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
        )
        SELECT * FROM orders_by_month ORDER BY month
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_top_category_revenue(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH category_revenue AS (
            SELECT COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   ROUND(SUM(oi.price), 2) AS revenue
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
        )
        SELECT * FROM category_revenue ORDER BY revenue DESC LIMIT 10
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_state_revenue(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH state_revenue AS (
            SELECT c.customer_state,
                   ROUND(SUM(op.payment_value), 2) AS revenue
            FROM orders o
            JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              {category_filter}
              {state_filter}
            GROUP BY c.customer_state
        )
        SELECT * FROM state_revenue ORDER BY revenue DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_order_status_breakdown(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH status_count AS (
            SELECT o.order_status,
                   COUNT(DISTINCT o.order_id) AS orders
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY o.order_status
        )
        SELECT * FROM status_count ORDER BY orders DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_top_bottom_products(date_start: str, date_end: str, category: list[str], state: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    filter_params = [*category_params, *state_params]
    query_params = [date_start, date_end, *filter_params]

    query = f"""
        WITH product_revenue AS (
            SELECT p.product_id,
                   COALESCE(p.product_category_name, 'Unknown') AS product_name,
                   ROUND(SUM(oi.price), 2) AS revenue,
                   COUNT(DISTINCT oi.order_id) AS orders
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY p.product_id, COALESCE(p.product_category_name, 'Unknown')
        )
        SELECT * FROM product_revenue ORDER BY revenue DESC LIMIT 10
    """
    top = con.execute(query, query_params).fetchdf()

    bottom_query = f"""
        WITH product_revenue AS (
            SELECT p.product_id,
                   COALESCE(p.product_category_name, 'Unknown') AS product_name,
                   ROUND(SUM(oi.price), 2) AS revenue,
                   COUNT(DISTINCT oi.order_id) AS orders
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY p.product_id, COALESCE(p.product_category_name, 'Unknown')
        )
        SELECT * FROM product_revenue WHERE revenue IS NOT NULL ORDER BY revenue ASC LIMIT 10
    """
    bottom = con.execute(bottom_query, query_params).fetchdf()
    return top, bottom


@st.cache_data
def get_category_order_count(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH category_metrics AS (
            SELECT COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   ROUND(SUM(oi.price), 2) AS revenue,
                   COUNT(DISTINCT o.order_id) AS order_count
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY COALESCE(ct.product_category_name_english, p.product_category_name)
        )
        SELECT * FROM category_metrics ORDER BY revenue DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_seller_leaderboard(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH seller_metrics AS (
            SELECT s.seller_id,
                   COALESCE(s.seller_city, 'Unknown') AS seller_city,
                   COALESCE(s.seller_state, 'Unknown') AS seller_state,
                   ROUND(SUM(oi.price), 2) AS seller_revenue,
                   COUNT(DISTINCT oi.order_id) AS orders,
                   COUNT(*) AS items_sold,
                   ROUND(AVG(r.review_score), 2) AS avg_review_score
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN sellers s ON s.seller_id = oi.seller_id
            LEFT JOIN order_reviews r ON r.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY s.seller_id, s.seller_city, s.seller_state
        )
        SELECT * FROM seller_metrics ORDER BY seller_revenue DESC LIMIT 15
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_sales_vs_freight(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH order_metrics AS (
            SELECT o.order_id,
                   ROUND(SUM(oi.price), 2) AS revenue,
                   ROUND(SUM(oi.freight_value), 2) AS freight_cost,
                   COALESCE(c.customer_state, 'Unknown') AS customer_state
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY o.order_id, c.customer_state
        )
        SELECT * FROM order_metrics
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_category_review_scores(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH order_review_score AS (
            SELECT o.order_id,
                   AVG(r.review_score) AS avg_review_score
            FROM orders o
            JOIN order_reviews r ON r.order_id = o.order_id
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
            GROUP BY o.order_id
        ), order_category_review AS (
            SELECT DISTINCT oi.order_id,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name,
                   c.customer_state,
                   ors.avg_review_score
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            JOIN order_review_score ors ON ors.order_id = o.order_id
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
        )
        SELECT category_name,
               ROUND(AVG(avg_review_score), 2) AS avg_review_score,
               COUNT(DISTINCT order_id) AS review_orders
        FROM order_category_review
        GROUP BY category_name
        ORDER BY avg_review_score DESC
    """
    params = [date_start, date_end, date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_repeat_customers(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH customer_orders AS (
            SELECT c.customer_unique_id,
                   COUNT(DISTINCT o.order_id) AS order_count
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY c.customer_unique_id
        )
        SELECT
            SUM(CASE WHEN order_count = 1 THEN 1 ELSE 0 END) AS one_time_customers,
            SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers
        FROM customer_orders
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_top_customers(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH customer_revenue AS (
            SELECT c.customer_unique_id,
                   c.customer_state,
                   ROUND(SUM(op.payment_value), 2) AS revenue,
                   COUNT(DISTINCT o.order_id) AS order_count
            FROM orders o
            JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              {category_filter}
              {state_filter}
            GROUP BY c.customer_unique_id, c.customer_state
        )
        SELECT * FROM customer_revenue ORDER BY revenue DESC LIMIT 10
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_customers_by_state(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH customer_counts AS (
            SELECT c.customer_state,
                   COUNT(DISTINCT c.customer_unique_id) AS customers
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY c.customer_state
        )
        SELECT * FROM customer_counts ORDER BY customers DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_customer_segments(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    q1, q3 = get_customer_value_thresholds()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH eligible_orders AS (
            SELECT DISTINCT o.order_id,
                            o.customer_id,
                            c.customer_unique_id
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              {category_filter}
              {state_filter}
        ), customer_revenue AS (
            SELECT e.customer_unique_id,
                   ROUND(SUM(op.payment_value), 2) AS revenue
            FROM eligible_orders e
            JOIN order_payments op ON op.order_id = e.order_id
            GROUP BY e.customer_unique_id
        )
        SELECT
            SUM(CASE WHEN revenue <= ? THEN 1 ELSE 0 END) AS low,
            SUM(CASE WHEN revenue > ? AND revenue < ? THEN 1 ELSE 0 END) AS medium,
            SUM(CASE WHEN revenue >= ? THEN 1 ELSE 0 END) AS high
        FROM customer_revenue
    """
    params = [date_start, date_end, *category_params, *state_params, q1, q1, q3, q3]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_delivery_by_state(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH delivery_state AS (
            SELECT c.customer_state,
                   ROUND(AVG(DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date)), 2) AS avg_delivery_days
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              AND o.order_purchase_timestamp IS NOT NULL
              AND o.order_delivered_customer_date IS NOT NULL
              {category_filter}
              {state_filter}
            GROUP BY c.customer_state
        )
        SELECT * FROM delivery_state ORDER BY avg_delivery_days DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_late_delivery_kpi(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH late_delivery AS (
            SELECT
                ROUND(AVG(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) * 100, 2) AS late_delivery_pct,
                SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders,
                COUNT(*) AS delivered_orders
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              AND o.order_delivered_customer_date IS NOT NULL
              AND o.order_estimated_delivery_date IS NOT NULL
              {category_filter}
              {state_filter}
        )
        SELECT * FROM late_delivery
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_late_delivery_trend(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH late_by_month AS (
            SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
                   ROUND(AVG(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) * 100, 2) AS late_delivery_pct,
                   COUNT(*) AS delivered_orders
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              AND o.order_delivered_customer_date IS NOT NULL
              AND o.order_estimated_delivery_date IS NOT NULL
              {category_filter}
              {state_filter}
            GROUP BY DATE_TRUNC('month', o.order_purchase_timestamp)
        )
        SELECT * FROM late_by_month ORDER BY month
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_review_vs_delivery(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH order_review_metrics AS (
            SELECT o.order_id,
                   DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_days,
                   AVG(r.review_score) AS avg_review_score,
                   c.customer_state,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category_name
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_reviews r ON r.order_id = o.order_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              AND o.order_status = 'delivered'
              AND o.order_purchase_timestamp IS NOT NULL
              AND o.order_delivered_customer_date IS NOT NULL
              {category_filter}
              {state_filter}
            GROUP BY o.order_id, o.order_purchase_timestamp, o.order_delivered_customer_date, c.customer_state, COALESCE(ct.product_category_name_english, p.product_category_name)
        )
        SELECT * FROM order_review_metrics
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_payment_method_breakdown(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH payment_summary AS (
            SELECT op.payment_type,
                   COUNT(DISTINCT o.order_id) AS orders
            FROM orders o
            JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY op.payment_type
        )
        SELECT * FROM payment_summary ORDER BY orders DESC
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


@st.cache_data
def get_installment_distribution(date_start: str, date_end: str, category: list[str], state: list[str]) -> pd.DataFrame:
    con = get_db()
    category_filter, category_params = build_category_filter(
        category,
        "COALESCE(ct.product_category_name_english, p.product_category_name)",
        "o",
    )
    state_filter, state_params = build_state_filter(state, "c.customer_state")
    params = [*category_params, *state_params]

    query = f"""
        WITH installment_summary AS (
            SELECT MAX(op.payment_installments) AS installment_count,
                   o.order_id
            FROM orders o
            JOIN order_payments op ON op.order_id = o.order_id
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN category_translation ct ON ct.product_category_name = p.product_category_name
            WHERE o.order_purchase_timestamp >= ?
              AND o.order_purchase_timestamp < ?
              {category_filter}
              {state_filter}
            GROUP BY o.order_id
        )
        SELECT installment_count, COUNT(*) AS orders
        FROM installment_summary
        GROUP BY installment_count
        ORDER BY installment_count
    """
    params = [date_start, date_end, *params]
    return con.execute(query, params).fetchdf()


def format_currency(value):
    if pd.isna(value):
        return "R$0.00"
    return f"R${float(value):,.2f}"


def format_percent(value):
    if pd.isna(value):
        return "0.00%"
    return f"{float(value):.2f}%"


def filter_controls() -> tuple[str, str, list[str], list[str]]:
    min_date, max_date = get_date_range()
    date_start, date_end = st.sidebar.date_input(
        "Purchase date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
        key="date_range",
    )

    if isinstance(date_start, tuple):
        date_start, date_end = date_start

    categories = get_category_options()
    selected_categories = st.sidebar.multiselect("Category", categories, default=categories)

    states = get_state_options()
    selected_states = st.sidebar.multiselect("State", states, default=states)

    start_str = pd.Timestamp(date_start).strftime("%Y-%m-%d")
    end_str = (pd.Timestamp(date_end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return start_str, end_str, selected_categories, selected_states


def show_empty_state(message: str):
    st.info(message)


def show_kpi_card(label: str, value: str, help_text: str):
    st.markdown(
        f"""
        <div style="padding: 0.75rem 1rem; border-radius: 0.75rem; background: #F5F7FF; border: 1px solid #D6DDF7; margin-bottom: 0.5rem;">
            <div style="font-size: 0.8rem; color: #4B5563;">{label}</div>
            <div style="font-size: 1.6rem; font-weight: 700; color: #111827;">{value}</div>
            <div style="font-size: 0.7rem; color: #6B7280;">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(date_start: str, date_end: str, category: list[str], state: list[str]):
    st.title("Executive Overview")
    st.caption("Validated Olist revenue, customer, and delivery patterns using the project’s business definitions.")

    kpis = get_kpi_cards(date_start, date_end, category, state).iloc[0]
    total_revenue = float(kpis["total_revenue"]) if pd.notna(kpis["total_revenue"]) else 0.0
    total_orders = int(kpis["total_orders"]) if pd.notna(kpis["total_orders"]) else 0
    aov = float(kpis["aov"]) if pd.notna(kpis["aov"]) else 0.0
    avg_review_score = float(kpis["avg_review_score"]) if pd.notna(kpis["avg_review_score"]) else 0.0
    total_customers = int(kpis["total_customers"]) if pd.notna(kpis["total_customers"]) else 0

    cols = st.columns(5)
    metrics = [
        ("Total Revenue", format_currency(total_revenue), "Delivered-order payment revenue"),
        ("Total Orders", f"{total_orders:,}", "Matching order count for the selected period"),
        ("AOV", format_currency(aov), "Revenue divided by delivered orders"),
        ("Avg Review Score", f"{avg_review_score:.2f}", "Average review score for delivered orders"),
        ("Total Customers", f"{total_customers:,}", "Unique customers in the selected filter"),
    ]
    for col, (label, value, help_text) in zip(cols, metrics):
        with col:
            show_kpi_card(label, value, help_text)

    revenue_df = get_revenue_trend(date_start, date_end, category, state)
    orders_df = get_orders_trend(date_start, date_end, category, state)
    if revenue_df.empty or orders_df.empty:
        show_empty_state("No data available for the selected filters.")
        return

    st.subheader("Revenue trend")
    fig = px.line(
        revenue_df,
        x="month",
        y="revenue",
        title="Revenue over time",
        markers=True,
        line_shape="spline",
        template="plotly_white",
    )
    fig.update_layout(height=350, xaxis_title="Month", yaxis_title="Revenue", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Orders trend")
    fig_orders = px.line(
        orders_df,
        x="month",
        y="orders",
        title="Orders over time",
        markers=True,
        line_shape="spline",
        template="plotly_white",
    )
    fig_orders.update_layout(height=350, xaxis_title="Month", yaxis_title="Orders", template="plotly_white")
    st.plotly_chart(fig_orders, use_container_width=True)

    top_cat = get_top_category_revenue(date_start, date_end, category, state)
    if not top_cat.empty:
        st.subheader("Top 10 categories by revenue")
        fig_cat = px.bar(
            top_cat.sort_values("revenue", ascending=True),
            x="revenue",
            y="category_name",
            orientation="h",
            title="Top 10 category revenue",
            color="revenue",
            color_continuous_scale="Blues",
        )
        fig_cat.update_layout(height=420, template="plotly_white", xaxis_title="Revenue", yaxis_title="Category")
        st.plotly_chart(fig_cat, use_container_width=True)

    state_rev = get_state_revenue(date_start, date_end, category, state)
    if not state_rev.empty:
        st.subheader("Revenue by state")
        fig_state = px.bar(
            state_rev,
            x="customer_state",
            y="revenue",
            title="Revenue by state",
            color="revenue",
            color_continuous_scale="Viridis",
            template="plotly_white",
        )
        fig_state.update_layout(height=350, xaxis_title="State", yaxis_title="Revenue")
        st.plotly_chart(fig_state, use_container_width=True)

    status_df = get_order_status_breakdown(date_start, date_end, category, state)
    if not status_df.empty:
        st.subheader("Order status breakdown")
        fig_status = px.pie(
            status_df,
            names="order_status",
            values="orders",
            title="Order status distribution",
            hole=0.45,
        )
        fig_status.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_status, use_container_width=True)

    with st.expander("Methodology"):
        st.markdown(
            """
            - Revenue uses delivered-order payment value from `order_payments.payment_value`.
            - Orders are counted at the order grain.
            - Category revenue uses item-level `order_items.price` grouped by product category.
            - Filters apply to the relevant data granularity without creating duplicate revenue rows.
            """
        )


def render_product_seller(date_start: str, date_end: str, category: list[str], state: list[str]):
    st.title("Product & Seller Analysis")
    st.caption("Product ambition, assortment concentration, and seller performance from the item-level revenue logic.")

    top_products, bottom_products = get_top_bottom_products(date_start, date_end, category, state)
    if top_products.empty and bottom_products.empty:
        show_empty_state("No product-level revenue available for the selected filter set.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if not top_products.empty:
            st.subheader("Top 10 products by revenue")
            fig_top = px.bar(
                top_products.sort_values("revenue", ascending=True),
                x="revenue",
                y="product_name",
                orientation="h",
                color="revenue",
                color_continuous_scale="Blues",
                template="plotly_white",
            )
            fig_top.update_layout(height=420, xaxis_title="Revenue", yaxis_title="Product")
            st.plotly_chart(fig_top, use_container_width=True)

    with col2:
        if not bottom_products.empty:
            st.subheader("Bottom 10 products by revenue")
            fig_bottom = px.bar(
                bottom_products.sort_values("revenue", ascending=False),
                x="revenue",
                y="product_name",
                orientation="h",
                color="revenue",
                color_continuous_scale="Reds",
                template="plotly_white",
            )
            fig_bottom.update_layout(height=420, xaxis_title="Revenue", yaxis_title="Product")
            st.plotly_chart(fig_bottom, use_container_width=True)

    cat_metrics = get_category_order_count(date_start, date_end, category, state)
    if not cat_metrics.empty:
        st.subheader("Category revenue vs order count")
        fig_cat = px.scatter(
            cat_metrics,
            x="order_count",
            y="revenue",
            size="revenue",
            color="category_name",
            hover_name="category_name",
            template="plotly_white",
        )
        fig_cat.update_layout(height=420, xaxis_title="Distinct orders", yaxis_title="Revenue")
        st.plotly_chart(fig_cat, use_container_width=True)

    sellers = get_seller_leaderboard(date_start, date_end, category, state)
    if not sellers.empty:
        st.subheader("Seller performance leaderboard")
        st.dataframe(
            sellers[["seller_id", "seller_city", "seller_state", "seller_revenue", "orders", "items_sold", "avg_review_score"]].sort_values("seller_revenue", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    sales_vs_freight = get_sales_vs_freight(date_start, date_end, category, state)
    if not sales_vs_freight.empty:
        st.subheader("Sales vs freight cost")
        fig_freight = px.scatter(
            sales_vs_freight,
            x="freight_cost",
            y="revenue",
            color="customer_state",
            hover_name="order_id",
            template="plotly_white",
        )
        fig_freight.update_layout(height=420, xaxis_title="Freight cost", yaxis_title="Revenue")
        st.plotly_chart(fig_freight, use_container_width=True)

    review_scores = get_category_review_scores(date_start, date_end, category, state)
    if not review_scores.empty:
        st.subheader("Review score by category")
        fig_reviews = px.bar(
            review_scores.sort_values("avg_review_score", ascending=False),
            x="category_name",
            y="avg_review_score",
            color="avg_review_score",
            color_continuous_scale="Viridis",
            template="plotly_white",
        )
        fig_reviews.update_layout(height=420, xaxis_title="Category", yaxis_title="Average review score")
        st.plotly_chart(fig_reviews, use_container_width=True)

    with st.expander("Metric definitions"):
        st.markdown(
            """
            - Product and seller revenue uses `order_items.price` at the item level.
            - Category revenue is aggregated by category after resolving product category names.
            - Seller leaderboard is ordered by total seller revenue, not by operating margin or profit.
            - Sales vs freight is plotted at the order grain to avoid duplicate revenue/freight rows.
            """
        )


def render_customer(date_start: str, date_end: str, category: list[str], state: list[str]):
    st.title("Customer Analysis")
    st.caption("Customer mix, repeat behavior, and value distribution based on validated customer grain.")

    repeat_df = get_repeat_customers(date_start, date_end, category, state).iloc[0]
    one_time = int(repeat_df["one_time_customers"]) if pd.notna(repeat_df["one_time_customers"]) else 0
    repeat = int(repeat_df["repeat_customers"]) if pd.notna(repeat_df["repeat_customers"]) else 0
    if one_time + repeat > 0:
        repeat_pie = pd.DataFrame({"segment": ["One-time", "Repeat"], "customers": [one_time, repeat]})
        st.subheader("Repeat vs one-time customers")
        fig_repeat = px.pie(repeat_pie, names="segment", values="customers", hole=0.45)
        fig_repeat.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_repeat, use_container_width=True)

    top_customers = get_top_customers(date_start, date_end, category, state)
    if not top_customers.empty:
        st.subheader("Top 10 customers by revenue")
        top_customers = top_customers.copy()
        top_customers["customer_display"] = top_customers["customer_unique_id"].astype(str).str[:8] + "…"
        fig_cust = px.bar(
            top_customers.sort_values("revenue", ascending=True),
            x="revenue",
            y="customer_display",
            orientation="h",
            color="revenue",
            color_continuous_scale="Blues",
            template="plotly_white",
        )
        fig_cust.update_layout(height=420, xaxis_title="Revenue", yaxis_title="Customer")
        st.plotly_chart(fig_cust, use_container_width=True)

    state_counts = get_customers_by_state(date_start, date_end, category, state)
    if not state_counts.empty:
        st.subheader("Customers by state")
        fig_state = px.bar(
            state_counts,
            x="customer_state",
            y="customers",
            color="customers",
            color_continuous_scale="Viridis",
            template="plotly_white",
        )
        fig_state.update_layout(height=380, xaxis_title="State", yaxis_title="Customers")
        st.plotly_chart(fig_state, use_container_width=True)

    seg_df = get_customer_segments(date_start, date_end, category, state).iloc[0]
    low = int(seg_df["low"]) if pd.notna(seg_df["low"]) else 0
    medium = int(seg_df["medium"]) if pd.notna(seg_df["medium"]) else 0
    high = int(seg_df["high"]) if pd.notna(seg_df["high"]) else 0
    seg_df_plot = pd.DataFrame({"segment": ["Low", "Medium", "High"], "customers": [low, medium, high]})
    st.subheader("Customer value segments")
    st.caption("Segment logic: low = revenue <= 25th percentile, medium = between 25th and 75th percentile, high = >= 75th percentile.")
    fig_seg = px.bar(seg_df_plot, x="segment", y="customers", color="segment", color_discrete_sequence=["#7F8CFF", "#A9C3FF", "#1E3A8A"])
    st.plotly_chart(fig_seg, use_container_width=True)

    with st.expander("Metric definitions"):
        st.markdown(
            """
            - Customer count is based on distinct `customer_unique_id` values.
            - Repeat customer means more than one order in the filtered time range.
            - Customer value segments are based on revenue distribution across delivered orders.
            """
        )


def render_delivery(date_start: str, date_end: str, category: list[str], state: list[str]):
    st.title("Delivery & Customer Experience")
    st.caption("Order-level delivery quality, lateness, and the relationship between delivery speed and review sentiment.")

    late_df = get_late_delivery_kpi(date_start, date_end, category, state).iloc[0]
    late_pct = float(late_df["late_delivery_pct"]) if pd.notna(late_df["late_delivery_pct"]) else 0.0
    late_orders = int(late_df["late_orders"]) if pd.notna(late_df["late_orders"]) else 0
    delivered_orders = int(late_df["delivered_orders"]) if pd.notna(late_df["delivered_orders"]) else 0
    col1, col2, col3 = st.columns(3)
    with col1:
        show_kpi_card("Late Delivery %", format_percent(late_pct), "Late orders divided by delivered orders")
    with col2:
        show_kpi_card("Late Orders", f"{late_orders:,}", "Orders delivered after the estimate")
    with col3:
        show_kpi_card("Delivered Orders", f"{delivered_orders:,}", "Orders in the filtered delivery base")

    delivery_state = get_delivery_by_state(date_start, date_end, category, state)
    if not delivery_state.empty:
        st.subheader("Average delivery time by state")
        fig_state_delivery = px.bar(
            delivery_state,
            x="customer_state",
            y="avg_delivery_days",
            color="avg_delivery_days",
            color_continuous_scale="Viridis",
            template="plotly_white",
        )
        fig_state_delivery.update_layout(height=400, xaxis_title="State", yaxis_title="Average delivery days")
        st.plotly_chart(fig_state_delivery, use_container_width=True)

    late_trend = get_late_delivery_trend(date_start, date_end, category, state)
    if not late_trend.empty:
        st.subheader("Late delivery trend")
        fig_late = px.line(
            late_trend,
            x="month",
            y="late_delivery_pct",
            markers=True,
            template="plotly_white",
        )
        fig_late.update_layout(height=350, xaxis_title="Month", yaxis_title="Late delivery %")
        st.plotly_chart(fig_late, use_container_width=True)

    review_vs_delivery = get_review_vs_delivery(date_start, date_end, category, state)
    if not review_vs_delivery.empty:
        st.subheader("Review score vs delivery time")
        fig_review = px.scatter(
            review_vs_delivery,
            x="delivery_days",
            y="avg_review_score",
            color="customer_state",
            hover_name="order_id",
            trendline="ols",
            template="plotly_white",
        )
        fig_review.update_layout(height=420, xaxis_title="Delivery days", yaxis_title="Average review score")
        st.plotly_chart(fig_review, use_container_width=True)

    payment_df = get_payment_method_breakdown(date_start, date_end, category, state)
    if not payment_df.empty:
        st.subheader("Payment method breakdown")
        fig_payment = px.bar(
            payment_df,
            x="payment_type",
            y="orders",
            color="payment_type",
            template="plotly_white",
        )
        fig_payment.update_layout(height=350, xaxis_title="Payment method", yaxis_title="Orders")
        st.plotly_chart(fig_payment, use_container_width=True)

    installments = get_installment_distribution(date_start, date_end, category, state)
    if not installments.empty:
        st.subheader("Installment count distribution")
        fig_install = px.bar(
            installments,
            x="installment_count",
            y="orders",
            color="installment_count",
            color_continuous_scale="Cividis",
            template="plotly_white",
        )
        fig_install.update_layout(height=350, xaxis_title="Installment count", yaxis_title="Orders")
        st.plotly_chart(fig_install, use_container_width=True)

    with st.expander("Metric definitions"):
        st.markdown(
            """
            - Delivery time is calculated as `order_delivered_customer_date - order_purchase_timestamp` in days.
            - Late delivery is defined as `order_delivered_customer_date > order_estimated_delivery_date` for delivered orders.
            - Review vs delivery is evaluated at the order grain to avoid duplicate review rows when multiple item rows or review rows exist.
            - Correlation is interpreted as association only, not proof of causation.
            """
        )


def main():
    st.sidebar.title("Olist Dashboard")
    st.sidebar.caption("Portfolio analytics dashboard")
    start, end, categories, states = filter_controls()

    page = st.sidebar.radio(
        "Navigate",
        [
            "Executive Overview",
            "Product & Seller Analysis",
            "Customer Analysis",
            "Delivery & Customer Experience",
        ],
    )

    if page == "Executive Overview":
        render_overview(start, end, categories, states)
    elif page == "Product & Seller Analysis":
        render_product_seller(start, end, categories, states)
    elif page == "Customer Analysis":
        render_customer(start, end, categories, states)
    else:
        render_delivery(start, end, categories, states)


if __name__ == "__main__":
    main()

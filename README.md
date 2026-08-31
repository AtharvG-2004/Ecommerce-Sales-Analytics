# Olist E-Commerce Analytics

This project contains a validated Olist sales, customer, product, and delivery analysis built around the DuckDB database and SQL layer.

## Dashboard

Launch the Streamlit dashboard from the project root:

streamlit run streamlit_app/app.py

## Pages

- Executive Overview
- Product & Seller Analysis
- Customer Analysis
- Delivery & Customer Experience

## Filters

The dashboard includes shared filters for:

- purchase date range
- category
- state

## Metric definitions

- Revenue: delivered-order payment value from `order_payments.payment_value`
- AOV: total delivered revenue divided by delivered order count
- Customer count: distinct `customer_unique_id`
- Product and seller revenue: item-level `order_items.price`
- Late delivery: actual delivery date later than the estimated delivery date

## Requirements

Install dependencies with:

pip install -r requirements.txt

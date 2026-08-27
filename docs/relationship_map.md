# Olist E-Commerce Dataset — Relationship Map

## 1. Overview

The Olist Brazilian E-Commerce dataset contains 9 CSV tables covering customers, orders, order items, payments, reviews, products, sellers, geolocation, and product category translation.

The relationships below were identified and verified during the Level 1 Dataset Audit.

---

## 2. Main Relationship Structure

```text
Customers
    │
    │ customer_id
    ▼
Orders
    │
    ├──────────────► Order Items
    │                  │
    │                  ├──────────► Products
    │                  │
    │                  └──────────► Sellers
    │
    ├──────────────► Payments
    │
    └──────────────► Reviews

Products
    │
    └──────────────► Category Translation

Customers / Sellers
    │
    └──────────────► Geolocation
```
## 3. Relationship Summary

| Relationship                    | Join Column                | Expected Relationship                                    |
| ------------------------------- | -------------------------- | -------------------------------------------------------- |
| Customers → Orders              | `customer_id`              | 1 customer → many orders                                 |
| Orders → Order Items            | `order_id`                 | 1 order → many order items                               |
| Products → Order Items          | `product_id`               | 1 product → many order items                             |
| Sellers → Order Items           | `seller_id`                | 1 seller → many order items                              |
| Orders → Payments               | `order_id`                 | 1 order → many payment records                           |
| Orders → Reviews                | `order_id`                 | 1 order → potentially many review records                |
| Products → Category Translation | `product_category_name`    | 1 category → 1 translated category name                  |
| Customers → Geolocation         | `customer_zip_code_prefix` | 1 ZIP-code prefix → potentially many geolocation records |
| Sellers → Geolocation           | `seller_zip_code_prefix`   | 1 ZIP-code prefix → potentially many geolocation records |
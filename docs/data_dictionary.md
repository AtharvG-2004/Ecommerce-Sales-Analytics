# Olist E-Commerce Dataset — Data Dictionary

## 1. Customers

**File:** `olist_customers_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `customer_id` | Identifier for a customer record | String | Key candidate; 6 duplicate/malformed values found |
| `customer_unique_id` | Unique identifier representing the customer | String | Not unique in the table; 96,100 unique values |
| `customer_zip_code_prefix` | Customer ZIP-code prefix | String | 6 missing values |
| `customer_city` | Customer city | String | 6 missing values |
| `customer_state` | Customer state | String | 6 missing values |

---

## 2. Geolocation

**File:** `olist_geolocation_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `geolocation_zip_code_prefix` | ZIP-code prefix | Integer | Multiple records per ZIP prefix |
| `geolocation_lat` | Latitude | Float | — |
| `geolocation_lng` | Longitude | Float | — |
| `geolocation_city` | City | String | — |
| `geolocation_state` | State | String | — |

---

## 3. Order Items

**File:** `olist_order_items_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `order_id` | Order identifier | String | Part of composite key |
| `order_item_id` | Item sequence within an order | Integer | Part of composite key |
| `product_id` | Product identifier | String | Foreign-key candidate to products |
| `seller_id` | Seller identifier | String | Foreign-key candidate to sellers |
| `shipping_limit_date` | Seller shipping deadline | String | Will be converted to datetime during cleaning |
| `price` | Price of the item | Float | No zero/negative values found |
| `freight_value` | Freight/shipping value | Float | 383 values <= 0 found |

---

## 4. Order Payments

**File:** `olist_order_payments_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `order_id` | Order identifier | String | Foreign-key candidate to orders |
| `payment_sequential` | Payment sequence number for an order | Integer | Part of composite key |
| `payment_type` | Payment method | String | 5 categories identified |
| `payment_installments` | Number of installments | Integer | — |
| `payment_value` | Payment amount | Float | 9 values <= 0 found |

---

## 5. Order Reviews

**File:** `olist_order_reviews_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `review_id` | Review identifier | String | 98,410 unique values |
| `order_id` | Order identifier | String | Foreign-key candidate to orders |
| `review_score` | Customer review score | Integer | Valid range 1–5 |
| `review_comment_title` | Review title | String | Missing values present |
| `review_comment_message` | Review message | String | Missing values present |
| `review_creation_date` | Review creation date | String | Will be converted during cleaning |
| `review_answer_timestamp` | Review response timestamp | String | Will be converted during cleaning |

---

## 6. Orders

**File:** `olist_orders_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `order_id` | Order identifier | String | Key candidate; 3 malformed rows found |
| `customer_id` | Customer record identifier | String | Foreign-key candidate to customers |
| `order_status` | Current order status | String | 8 non-null status categories |
| `order_purchase_timestamp` | Order purchase timestamp | String | Main date for sales analysis |
| `order_approved_at` | Order approval timestamp | String | Missing values present |
| `order_delivered_carrier_date` | Date order was handed to carrier | String | Missing values present |
| `order_delivered_customer_date` | Date order was delivered to customer | String | Missing values present |
| `order_estimated_delivery_date` | Estimated delivery date | String | Missing values present |

---

## 7. Products

**File:** `olist_products_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `product_id` | Product identifier | String | Unique across product table |
| `product_category_name` | Product category in Portuguese | String | 610 missing values |
| `product_name_lenght` | Product-name character count | Integer | Original dataset column name |
| `product_description_lenght` | Product-description character count | Integer | Original dataset column name |
| `product_photos_qty` | Number of product photos | Integer | — |
| `product_weight_g` | Product weight in grams | Float | 4 values <= 0 found |
| `product_length_cm` | Product length in centimeters | Float | No values <= 0 found |
| `product_height_cm` | Product height in centimeters | Float | No values <= 0 found |
| `product_width_cm` | Product width in centimeters | Float | No values <= 0 found |

---

## 8. Sellers

**File:** `olist_sellers_dataset.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `seller_id` | Seller identifier | String | Unique across seller table |
| `seller_zip_code_prefix` | Seller ZIP-code prefix | String | — |
| `seller_city` | Seller city | String | — |
| `seller_state` | Seller state | String | — |

---

## 9. Product Category Translation

**File:** `product_category_name_translation.csv`

| Column | Description | Data Type | Notes |
|---|---|---|---|
| `product_category_name` | Original Portuguese category name | String | Used to join with products |
| `product_category_name_english` | English category name | String | Used for analysis/dashboard |

---

## Dataset Summary

| Table | Rows | Columns |
|---|---:|---:|
| Customers | 99,447 | 5 |
| Geolocation | 1,000,163 | 5 |
| Order Items | 112,650 | 7 |
| Order Payments | 103,886 | 5 |
| Order Reviews | 99,224 | 7 |
| Orders | 99,444 | 8 |
| Products | 32,951 | 9 |
| Sellers | 3,095 | 4 |
| Category Translation | 71 | 2 |
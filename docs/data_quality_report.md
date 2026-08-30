# Data Quality Report

## 1. Purpose

This report documents the data quality assessment and cleaning performed on the Olist Brazilian E-Commerce dataset.

The objective of Level 2 was to prepare the raw datasets for reliable exploratory data analysis, SQL analysis, business insights, and dashboard development.

The cleaning process focused on:

* Duplicate records
* Missing values
* Invalid or inconsistent identifiers
* Orphan records and referential integrity
* Datetime standardization
* Data type validation
* Final quality checks

---

## 2. Cleaning Summary

The following datasets were cleaned and validated:

| Dataset              | Original Rows | Final Rows | Rows Removed |
| -------------------- | ------------: | ---------: | -----------: |
| customers            |        99,447 |     99,441 |            6 |
| geolocation          |     1,000,163 |    738,332 |      261,831 |
| order_items          |       112,650 |    112,647 |            3 |
| order_payments       |       103,886 |    103,881 |            5 |
| order_reviews        |        99,224 |     99,222 |            2 |
| orders               |        99,444 |     99,441 |            3 |
| products             |        32,951 |     32,951 |            0 |
| sellers              |         3,095 |      3,095 |            0 |
| category_translation |            71 |         71 |            0 |

### Important note

The large reduction in the `geolocation` dataset was caused by duplicate records. These duplicates were removed because they did not provide additional unique information.

---

## 3. Duplicate Handling

Duplicate rows were identified and removed from all datasets.

### Initial duplicate findings

| Dataset              | Duplicate Rows |
| -------------------- | -------------: |
| customers            |              2 |
| geolocation          |        261,831 |
| order_items          |              0 |
| order_payments       |              0 |
| order_reviews        |              0 |
| orders               |              1 |
| products             |              0 |
| sellers              |              0 |
| category_translation |              0 |

After cleaning, the final duplicate check returned:

| Dataset              | Remaining Duplicates |
| -------------------- | -------------------: |
| customers            |                    0 |
| geolocation          |                    0 |
| order_items          |                    0 |
| order_payments       |                    0 |
| order_reviews        |                    0 |
| orders               |                    0 |
| products             |                    0 |
| sellers              |                    0 |
| category_translation |                    0 |

**Result: 0 duplicate rows remain across all datasets.**

---

## 4. Identifier Standardization

Several identifiers contained unnecessary quotation marks, which could cause matching and join problems.

The affected identifiers included:

* Customer IDs
* Seller IDs
* Order IDs in review records

Quotation marks were removed and identifiers were standardized as strings.

### Customer IDs

* Customers with quoted IDs: 1
* Orders with quoted customer IDs: 3
* After standardization, orders with missing customer references: **0**

### Seller IDs

Seller IDs containing quotation marks were standardized.

After cleaning:

* Order items with missing seller reference: **0**

### Review Order IDs

Review `order_id` values were standardized by removing unnecessary quotation marks.

After cleaning:

* Orphan reviews remaining: **0**

---

## 5. Referential Integrity

Relationships between parent and child datasets were checked to identify records referencing IDs that do not exist in the corresponding parent dataset.

### Initial orphan/reference issues

| Relationship           | Invalid References |
| ---------------------- | -----------------: |
| Orders → Customers     |                  4 |
| Order Items → Orders   |                  3 |
| Order Items → Products |                  0 |
| Order Items → Sellers  |                  6 |
| Payments → Orders      |                  5 |
| Reviews → Orders       |                  8 |

Invalid child records were removed where necessary.

### Final validation

| Relationship           | Remaining Invalid References |
| ---------------------- | ---------------------------: |
| Orders → Customers     |                            0 |
| Order Items → Orders   |                            0 |
| Order Items → Products |                            0 |
| Order Items → Sellers  |                            0 |
| Payments → Orders      |                            0 |
| Reviews → Orders       |                            0 |

**Result: Referential integrity checks passed with 0 orphan references.**

---

## 6. Order Items Cleaning

Three order-item records referenced orders that were not present in the cleaned orders dataset.

These records were removed.

* Before cleaning: **112,650**
* After cleaning: **112,647**
* Rows removed: **3**

Final validation:

**Orphan order items remaining: 0**

---

## 7. Payment Data Cleaning

Five payment records referenced orders that were not present in the orders dataset.

These records were removed.

* Before cleaning: **103,886**
* After cleaning: **103,881**
* Rows removed: **5**

Final validation:

**Orphan payments remaining: 0**

---

## 8. Review Data Cleaning

Two review records referenced orders that were not present in the cleaned orders dataset.

Review order IDs were also standardized to remove unnecessary quotation marks.

* Before cleaning: **99,224**
* After cleaning: **99,222**
* Rows removed: **2**

Final validation:

**Orphan reviews remaining: 0**

---

## 9. Missing Value Analysis

Missing values were investigated before deciding whether they should be removed, retained, or handled during analysis.

### Customers

After cleaning:

**No missing values remain.**

### Geolocation

After duplicate removal and cleaning:

**No missing values remain.**

### Order Items

**No missing values remain.**

### Payments

**No missing values remain.**

### Sellers

**No missing values remain.**

### Category Translation

**No missing values remain.**

---

## 10. Review Missing Values

Review text fields contain a large number of missing values.

| Column                 | Missing Values |
| ---------------------- | -------------: |
| review_comment_title   |         87,654 |
| review_comment_message |         58,245 |

These values were **not removed** because a customer not providing a written comment is a valid business scenario.

The `review_score` remains available even when written comments are missing.

Therefore, these missing values are considered **legitimate missing data rather than data-quality errors**.

---

## 11. Order Date Missing Values

Several order timestamp fields contain missing values.

| Column                        | Missing Values |
| ----------------------------- | -------------: |
| order_purchase_timestamp      |              0 |
| order_approved_at             |            160 |
| order_delivered_carrier_date  |          1,783 |
| order_delivered_customer_date |          2,965 |
| order_estimated_delivery_date |              0 |

These missing values were investigated against `order_status`.

Missing delivery timestamps are expected for orders that were:

* Created
* Approved
* Processing
* Invoiced
* Shipped
* Canceled
* Unavailable

Therefore, these values were **not blindly filled or deleted**.

The missingness represents the actual lifecycle state of an order.

---

## 12. Product Missing Values

The product dataset contains 610 products with missing category and related descriptive attributes.

| Column                     | Missing Values |
| -------------------------- | -------------: |
| product_category_name      |            610 |
| product_name_lenght        |            610 |
| product_description_lenght |            610 |
| product_photos_qty         |            610 |

These products were retained because they are valid product records and some are used by order items.

### Business relevance

* Products with missing category: **610**
* Order items using these products: **1,603**
* Unique missing-category products used: **610**

Removing these products would result in the loss of valid sales transactions.

Therefore, the records were retained and the missing category information will be handled appropriately during EDA and business analysis.

---

## 13. Product Physical Attribute Missing Values

A very small number of products have missing physical dimensions.

| Column            | Missing Values |
| ----------------- | -------------: |
| product_weight_g  |              2 |
| product_length_cm |              2 |
| product_height_cm |              2 |
| product_width_cm  |              2 |

These records were retained because the missing values affect only a very small number of products and removing the products would unnecessarily discard valid product information.

---

## 14. Datetime Standardization

Datetime columns were converted from string/object values to proper datetime types where applicable.

Examples include:

* `order_purchase_timestamp`
* `order_approved_at`
* `order_delivered_carrier_date`
* `order_delivered_customer_date`
* `order_estimated_delivery_date`
* `shipping_limit_date`
* Review date fields

The resulting datetime columns can now be used reliably for:

* Delivery-time calculations
* Monthly and yearly trends
* Time-based sales analysis
* Order lifecycle analysis
* Delivery performance analysis

---

## 15. Data Type Validation

Data types were reviewed after cleaning.

Examples:

* IDs → string
* Prices → float
* Freight values → float
* Payment values → float
* Payment installments → integer
* Review scores → integer
* Geographic latitude/longitude → float
* Datetime fields → datetime

This ensures that numerical calculations, joins, filtering, and time-based analysis can be performed reliably.

---

## 16. Final Dataset Validation

### Final Row Counts

| Dataset              | Final Rows |
| -------------------- | ---------: |
| customers            |     99,441 |
| geolocation          |    738,332 |
| order_items          |    112,647 |
| order_payments       |    103,881 |
| order_reviews        |     99,222 |
| orders               |     99,441 |
| products             |     32,951 |
| sellers              |      3,095 |
| category_translation |         71 |

### Final Duplicate Check

All nine datasets returned:

**0 duplicate rows**

### Final Referential Integrity Check

All tested relationships returned:

**0 orphan/invalid references**

### Final Missing Value Check

Remaining missing values are limited to legitimate cases such as:

* Optional review comments
* Order lifecycle timestamps that do not apply to certain statuses
* Missing product category/descriptive information
* A very small number of missing product dimensions

---

## 17. Cleaning Decisions

The cleaning process followed these principles:

1. **Do not delete valid business records simply because they contain NULL values.**
2. **Remove true duplicate records.**
3. **Standardize identifiers before performing relationship checks.**
4. **Remove orphan child records when the referenced parent record does not exist.**
5. **Preserve legitimate missing values when they represent real business conditions.**
6. **Convert dates and numerical fields into appropriate data types.**
7. **Validate the dataset again after cleaning.**

---

## 18. Data Quality Conclusion

The Olist dataset has successfully passed the Level 2 cleaning and validation process.

The cleaned datasets now have:

* **0 duplicate rows**
* **0 orphan references across tested relationships**
* Standardized identifiers
* Standardized datetime fields
* Validated data types
* Documented legitimate missing values
* Verified final row counts

The cleaned dataset is now ready for:

**Level 3 — Exploratory Data Analysis (EDA).**

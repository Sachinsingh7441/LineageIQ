# 📊 Data Module — Synthetic Data Warehouse

## Overview

This module contains the **synthetic dataset** that powers the entire LineageIQ system. It represents a fictional e-commerce company called **"ShopStream"** with a realistic data warehouse structure.

> **Why synthetic data?** We don't need (and shouldn't use) real company data. This dataset mirrors a real data warehouse closely enough to demonstrate the lineage system. Having a reproducible generator in the repo shows engineering care.

---

## Data Warehouse Layers

Real data warehouses are organized in **layers** (also called zones or tiers). Each layer serves a specific purpose in the data pipeline:

```
Source Systems → [RAW] → [STAGING] → [CURATED] → [REPORTING] → Dashboards
```

### 1. Raw Layer (`raw_*`) — 7 Tables
**Purpose**: Landing zone where data arrives directly from source systems with zero transformation.

| Table | Source | Description |
|---|---|---|
| `raw_orders` | Transactional DB | Every order placed on the platform |
| `raw_customers` | CRM System | Customer profiles and contact details |
| `raw_payments` | Stripe API | Payment transactions (success/failure) |
| `raw_products` | Inventory System | Product catalog including discontinued items |
| `raw_order_items` | Transactional DB | Line items within each order |
| `raw_shipping_events` | Logistics APIs | Shipping tracking events |
| `raw_suppliers` | Vendor Portal | Supplier/vendor master data |

**Key characteristics**: No cleaning, no validation, may contain duplicates. Each table has an `ingested_at` timestamp.

### 2. Staging Layer (`stg_*`) — 7 Tables
**Purpose**: Cleaned, validated, and deduplicated data. Ready for business logic.

| Table | Source | Transformations Applied |
|---|---|---|
| `stg_orders` | `raw_orders` | Remove test orders, standardize timestamps to UTC, dedup |
| `stg_customers` | `raw_customers` | Validate emails, normalize country codes, combine names |
| `stg_payments` | `raw_payments` | Convert currencies to USD, dedup by idempotency key |
| `stg_products` | `raw_products` | Standardize categories, validate prices |
| `stg_order_items` | `raw_order_items` | Validate quantities, remove orphaned records |
| `stg_shipping` | `raw_shipping_events` | Dedup events, normalize carrier names |

### 3. Curated Layer (`curated_*`) — 4 Tables
**Purpose**: Conformed dimensions and fact tables with business logic applied. These are the "source of truth" tables.

| Table | Inputs | Business Logic |
|---|---|---|
| `curated_orders` | stg_orders + stg_payments + stg_shipping | Joins orders with payment and shipping status, classifies refunds |
| `curated_customers` | stg_customers + curated_orders | Enriches customers with lifetime value, order count |
| `curated_products` | stg_products + stg_order_items | Adds sales metrics, margin calculations |
| `curated_order_items` | stg_order_items + stg_products | Computes line totals with discounts |

### 4. Reporting Layer (`rpt_*`) — 4 Tables
**Purpose**: Aggregated, dashboard-ready tables for business users.

| Table | Purpose | Used By |
|---|---|---|
| `rpt_daily_sales` | Daily revenue, order count, AOV, refund rate | Executive dashboard |
| `rpt_customer_segments` | Segment-level metrics (LTV, churn rate) | Marketing team |
| `rpt_product_performance` | Product rankings by revenue and margin | Merchandising team |
| `rpt_shipping_sla` | Carrier delivery performance vs SLA | Operations team |
| `rpt_revenue_by_country` | Geographic revenue breakdown | Regional sales dashboard |

---

## Data Files

| File | Records | Description |
|---|---|---|
| `tables.json` | 22 | Table definitions with layer and description |
| `columns.json` | 170 | Column definitions with data type and description |
| `jobs.json` | 21 | ETL job definitions with schedule and owner |
| `lineage_edges.json` | 46 | Which jobs read/write which tables |
| `job_runs.json` | 190 | 7 days of job execution history (~10% failures) |

---

## Concepts Used

### ETL (Extract, Transform, Load)
The traditional pattern for moving data:
1. **Extract** from source systems
2. **Transform** (clean, validate, enrich)
3. **Load** into the destination

Each "job" in our dataset represents one ETL step.

### Data Lineage
The tracking of data flow: *where did this data come from, what happened to it, and where did it go?* Our dataset defines lineage through the `reads` and `writes` fields on each job.

### Star Schema
The curated layer follows a simplified **star schema** pattern:
- **Fact tables** contain measurable events (orders, order items)
- **Dimension tables** contain descriptive attributes (customers, products)

---

## Regenerating the Data

To regenerate all synthetic data from scratch:
```bash
python scripts/data_generator.py
```

The generator uses a fixed random seed (`random.seed(42)`) for reproducibility — running it twice produces identical output.

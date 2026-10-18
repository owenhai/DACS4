# Olist Star Schema

The fact table grain is one row per order item. Measures are stored in `fact_orders`, while descriptive attributes are stored in dimension tables.

```mermaid
erDiagram
    DIM_CUSTOMERS ||--o{ FACT_ORDERS : customer_key
    DIM_PRODUCTS ||--o{ FACT_ORDERS : product_key
    DIM_SELLERS ||--o{ FACT_ORDERS : seller_key
    DIM_DATE ||--o{ FACT_ORDERS : date_key

    DIM_CUSTOMERS {
        int customer_key PK
        string customer_id
        string customer_unique_id
        string customer_city
        string customer_state
    }

    DIM_PRODUCTS {
        int product_key PK
        string product_id
        string product_category_name_english
        double product_weight_g
        double product_length_cm
        double product_height_cm
        double product_width_cm
    }

    DIM_SELLERS {
        int seller_key PK
        string seller_id
        string seller_city
        string seller_state
        int seller_zip_code_prefix
    }

    DIM_DATE {
        int date_key PK
        date full_date
        int year
        int quarter
        int month
        string month_name
        boolean is_weekend
    }

    FACT_ORDERS {
        string order_id
        int customer_key FK
        int product_key FK
        int seller_key FK
        int date_key FK
        string order_status
        double price
        double freight_value
        double payment_value
        string payment_type
        double review_score
        double delivery_days
    }
```

## Database validation

- `fact_orders`: 112,650 rows
- `dim_customers`: 99,441 rows
- `dim_products`: 32,951 rows
- `dim_sellers`: 3,095 rows
- `dim_date`: 1,461 rows
- `dim_geolocation`: 19,015 rows

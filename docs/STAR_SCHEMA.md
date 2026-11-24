# ⭐ Lược đồ Star Schema — Olist Analytics (`olist_analytics.duckdb`)

Lược đồ Star Schema thiết kế cho bài toán phân tích dữ liệu thương mại điện tử Olist trong DuckDB. Bảng sự kiện `fact_orders` có độ chi tiết (**grain**) ở mức **một dòng trên mỗi mặt hàng trong đơn hàng** (`order_item`), lưu các đại lượng đo lường và liên kết tới các bảng chiều (`dim_*`).

---

## Sơ đồ Thực thể – Quan hệ (ERD)

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
        int product_name_length
        int product_description_length
        int product_photos_qty
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
        int day
        int day_of_week
        string day_name
        boolean is_weekend
    }

    DIM_GEOLOCATION {
        int geolocation_zip_code_prefix
        double geolocation_lat
        double geolocation_lng
        string geolocation_city
        string geolocation_state
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

> **Ghi chú:** `dim_geolocation` có thể kết nối bổ sung qua mã vùng bưu chính (`geolocation_zip_code_prefix` ↔ `seller_zip_code_prefix`) khi phân tích bản đồ tọa độ địa lý (`lat` / `lng`).

---

## Kiểm chứng dữ liệu thực tế trong DuckDB

| Bảng | Loại | Số dòng | Vai trò chính |
|---|---|---:|---|
| `fact_orders` | **FACT** | `112,650` | Giao dịch đơn hàng/sản phẩm, giá, cước vận chuyển, thanh toán, điểm đánh giá, số ngày giao |
| `dim_customers` | **DIMENSION** | `99,441` | Thông tin định danh và vị trí (thành phố, bang) của khách hàng |
| `dim_products` | **DIMENSION** | `32,951` | Danh mục sản phẩm (đã dịch tiếng Anh) và kích thước/khối lượng |
| `dim_sellers` | **DIMENSION** | `3,095` | Thông tin định danh và vị trí (thành phố, bang, mã vùng) của người bán |
| `dim_date` | **DIMENSION** | `1,461` | Chuỗi lịch ngày (`2016-01-01` → `2019-12-31`), năm, quý, tháng, thứ, cuối tuần |
| `dim_geolocation` | **DIMENSION** | `19,015` | Tọa độ vĩ độ/kinh độ theo mã vùng bưu chính Brazil |

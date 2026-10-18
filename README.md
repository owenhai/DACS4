# DACS4 - Automated Data Insights Engine

## Week 1: Olist ETL and Star Schema

This project downloads the Olist Brazilian E-Commerce dataset, cleans the source CSV files, and loads a Star Schema into DuckDB.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run the Olist pipeline

Run these commands from the project root:

```powershell
python -m src.data.download_dataset
python -m src.data.clean_data
python -m src.data.star_schema
```

The pipeline creates:

- Raw CSV files in `data/raw/`
- Clean Parquet files in `data/processed/`
- DuckDB database at `data/database/olist_analytics.duckdb`

Kaggle access is required for the download step.

## Validate Week 1 outputs

```powershell
python -m unittest discover -s tests -v
python -m src.data.schema_metadata
```

The database contains `fact_orders` and the dimensions `dim_customers`, `dim_products`, `dim_sellers`, `dim_date`, and `dim_geolocation`.

See [docs/STAR_SCHEMA.md](docs/STAR_SCHEMA.md) for the ERD and table relationships.

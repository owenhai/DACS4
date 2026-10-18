"""Exploratory summary for the raw Olist CSV files."""

from pathlib import Path

import pandas as pd

from src.data.clean_data import CSV_FILE_MAP


def build_eda_report(raw_dir: str = "data/raw") -> pd.DataFrame:
    """Return one summary row per raw CSV table."""
    raw_path = Path(raw_dir)
    rows: list[dict[str, object]] = []

    for table_name, filename in CSV_FILE_MAP.items():
        filepath = raw_path / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Missing raw file: {filepath}")

        dataframe = pd.read_csv(filepath)
        rows.append(
            {
                "table": table_name,
                "file": filename,
                "rows": len(dataframe),
                "columns": len(dataframe.columns),
                "null_cells": int(dataframe.isna().sum().sum()),
                "duplicate_rows": int(dataframe.duplicated().sum()),
                "dtypes": "; ".join(
                    f"{column}:{dtype}" for column, dtype in dataframe.dtypes.items()
                ),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    """Print the raw-data EDA summary."""
    report = build_eda_report()
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

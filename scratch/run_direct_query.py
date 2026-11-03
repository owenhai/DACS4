import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))  # add project root to PYTHONPATH
import duckdb
import pandas as pd

# Đường dẫn tới file DuckDB (the same logic as pipeline)
project_root = pathlib.Path(__file__).resolve().parents[2]
db_path = project_root / 'data' / 'database' / 'olist_analytics.duckdb'
if not db_path.exists():
    # nếu không tìm, thử alt path
    alt = project_root / 'data' / 'olist.duckdb'
    db_path = alt if alt.exists() else db_path

# Câu SQL trực tiếp (không qua LLM)
sql = """
SELECT COUNT(*) AS total_orders
FROM fact_orders
WHERE EXTRACT(year FROM order_date) = 2018;
"""

# Thực thi
conn = duckdb.connect(str(db_path), read_only=True)
try:
    df = conn.execute(sql).fetchdf()
    print('✅ SUCCESS')
    print('🛠️ GENERATED SQL:', sql.strip())
    print('🔢 ROW COUNT:', df.iloc[0,0])
    print('📊 SAMPLE (first rows):')
    print(df.head())
except Exception as e:
    print('❌ ERROR executing SQL:', e)
finally:
    conn.close()


import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # add project root
from src.models.text_to_sql import TextToSQLPipeline

pipeline = TextToSQLPipeline()
result = pipeline.ask("Có bao nhiêu đơn hàng trong năm 2018?")
print('SUCCESS:', result.success)
print('SQL:', result.generated_sql)
if result.dataframe is not None:
    print('Rows:', len(result.dataframe))
    print(result.dataframe.head())
else:
    print('No dataframe, error:', result.error_message)


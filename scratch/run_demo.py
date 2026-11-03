import sys, os
sys.path.append(r'd:\Project _Lab_Doc\DA\DACS4')
from src.models.text_to_sql import create_pipeline
pipeline = create_pipeline()
question = "Có bao nhiêu đơn hàng trong năm 2018?"
result = pipeline.ask(question)
print('SQL:', result.sql)
print('Rows:', len(result.df) if hasattr(result, 'df') else 'No df')

# -*- coding: utf-8 -*-
import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
from src.models.text_to_sql import TextToSQLPipeline

assert os.getenv("GEMINI_API_KEY"), "API key chưa được đặt trong biến môi trường GEMINI_API_KEY"

pipeline = TextToSQLPipeline(max_corrections=2)
question = "Liệt kê tổng doanh thu của bảng không tồn tại"
result = pipeline.ask(question)

print(" SUCCESS :", result.success)
print(" GENERATED SQL :", result.generated_sql)
print(" CORRECTION ATTEMPTS :", result.correction_attempts)
print(" HISTORY :", result.correction_history)

if not result.success:
    print(" FINAL ERROR :", result.error_message)

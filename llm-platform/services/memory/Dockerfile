FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8088
# --no-access-log: نُطفئ سجل uvicorn النصّي ونعتمد middleware يُصدر JSON بـ request_id (R-ERR-14/15)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8088", "--no-access-log"]

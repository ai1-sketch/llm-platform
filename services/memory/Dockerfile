# python:3.12-slim مُثبَّت بـ digest (إعادة الإنتاج — 2026-06-25)
FROM python@sha256:6c4dd321d176d61ea848dc8c73a4f7dbae8f70e0ee48bb411ea2f045b599fa8e

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8088
# --no-access-log: نُطفئ سجل uvicorn النصّي ونعتمد middleware يُصدر JSON بـ request_id (R-ERR-14/15)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8088", "--no-access-log"]

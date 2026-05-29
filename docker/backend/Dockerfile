FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt

RUN apt-get update && apt-get install -y gcc build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --default-timeout=100 -r /app/backend/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY backend/src /app/backend/src

ENV PYTHONPATH=/app/backend/src

RUN mkdir -p /app/backend/src/logs

WORKDIR /app/backend/src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

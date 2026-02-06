FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/monitoring
COPY ../../webbapp /app/webbapp

CMD ["python3", "/app/monitoring/db_monitor.py"]

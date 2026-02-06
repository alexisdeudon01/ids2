FROM python:3.12-slim

WORKDIR /app

COPY AWS/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY AWS/monitoring /app/monitoring

CMD ["python3", "/app/monitoring/db_monitor.py"]

FROM python:3.11-slim

WORKDIR /dbmanager
COPY storage ./storage

RUN pip install --no-cache-dir sqlalchemy asyncpg

CMD ["python", "-c", "print('DB manager image ready')"]

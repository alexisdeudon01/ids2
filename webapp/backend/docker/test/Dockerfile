FROM ids2-python-base:latest
RUN pip install --no-cache-dir pytest pytest-asyncio pytest-cov pytest-mock
COPY src/ ./src/
COPY tests/ ./tests/
COPY config.yaml ./
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "--cov=src/ids", "--cov-report=term-missing"]
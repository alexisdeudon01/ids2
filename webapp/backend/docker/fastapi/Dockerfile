FROM ids2-python-base:latest
COPY ../src/ ./src/
EXPOSE 8080
CMD ["uvicorn", "ids.app.api_status:app", "--host", "0.0.0.0", "--port", "8080"]

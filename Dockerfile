FROM python:3.9-slim
RUN pip install matrix-nio[e2e] watchdog
COPY src /app/
WORKDIR /app
CMD ["python", "uploader.py"]
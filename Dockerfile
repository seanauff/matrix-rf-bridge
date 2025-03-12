FROM python:3.9-slim
RUN pip install matrix-nio[e2e] watchdog
COPY uploader.py /app/uploader.py
WORKDIR /app
CMD ["python", "uploader.py"]
FROM python:3.9-slim
RUN pip install matrix-nio watchdog mutagen
COPY src /app/
WORKDIR /app
CMD ["python", "uploader.py"]
FROM python:3
LABEL org.opencontainers.image.source=https://github.com/seanauff/matrix-rf-bridge
LABEL org.opencontainers.image.description="The Matrix RF Bridge is a Python-based tool that uploads recordings from an RTLSDR-Airband instance (running in multichannel mode) to a Matrix server (e.g., Synapse)."
LABEL org.opencontainers.image.licenses=MIT
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src .
CMD ["python", "uploader.py"]
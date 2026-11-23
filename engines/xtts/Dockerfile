FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TTS_HOME=/root/.local/share/tts

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3.10-venv \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    git \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3.10 -m pip install --upgrade pip setuptools wheel && \
    python3.10 -m pip install -r requirements.txt

COPY app.py .
EXPOSE 8100

CMD ["python3.10", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]

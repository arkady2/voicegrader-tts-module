FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf \
    OMNIVOICE_MODEL_ID=k2-fsa/OmniVoice \
    OMNIVOICE_DEVICE=cuda:0 \
    OMNIVOICE_SPEAKER_WAV=/voices/Arek.wav \
    ENGINE_NAME=omnivoice \
    ENGINE_DISPLAY_NAME=OmniVoice

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        ffmpeg \
        libsndfile1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip setuptools wheel

RUN python3 -m pip install \
        torch==2.8.0+cu128 \
        torchaudio==2.8.0+cu128 \
        --extra-index-url https://download.pytorch.org/whl/cu128

RUN python3 -m pip install \
        omnivoice==0.2.0 \
        fastapi \
        "uvicorn[standard]" \
        boto3 \
        soundfile \
        numpy

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

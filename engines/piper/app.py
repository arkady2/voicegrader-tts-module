"""TASK Piper direct-WAV HTTP provider.

Real CPU inference.
Voice: pl_PL-gosia-medium.
Native sample rate: 22050 Hz.
Model mounted read-only.
No S3 or reference-speaker cloning.
"""

import hashlib
import io
import logging
import resource
import threading
import time
import wave

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from piper import PiperVoice
from piper.config import SynthesisConfig

MODEL_NAME = "pl_PL-gosia-medium"
MODEL_DIR = Path("/models/piper")

MODEL_FILE = MODEL_DIR / (MODEL_NAME + ".onnx")
CONFIG_FILE = MODEL_DIR / (MODEL_NAME + ".onnx.json")

EXPECTED_SHA = (
    "38f66464240ed74f186e6b7dc13c6e3b22e"
    "023426299f25c2b3cc9dfa9373fbc"
)

SAMPLE_RATE = 22050
MAX_WAV_BYTES = 30 * 1024 * 1024

app = FastAPI(
    title="TASK Piper PL direct WAV",
    version="0.1.0"
)

logger = logging.getLogger("piper-http")
lock = threading.Lock()

voice_model = None
load_seconds = None


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=280)
    language_id: str = "pl"
    voice_id: str = MODEL_NAME


def ensure_model():
    global voice_model, load_seconds

    if voice_model is not None:
        return

    if not MODEL_FILE.is_file():
        raise RuntimeError("Missing Piper ONNX model")

    if not CONFIG_FILE.is_file():
        raise RuntimeError("Missing Piper configuration")

    with MODEL_FILE.open("rb") as stream:
        digest = hashlib.file_digest(
            stream, "sha256"
        ).hexdigest()

    if digest != EXPECTED_SHA:
        raise RuntimeError("Piper model SHA256 mismatch")

    start = time.perf_counter()

    loaded = PiperVoice.load(
        MODEL_FILE,
        config_path=CONFIG_FILE,
        use_cuda=False
    )

    elapsed = time.perf_counter() - start

    voice_model = loaded
    load_seconds = elapsed

    logger.info(
        "Piper model loaded in %.6f seconds",
        elapsed
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "piper",
        "model": MODEL_NAME,
        "mode": "REAL_CPU",
        "model_loaded": voice_model is not None,
        "model_exists": MODEL_FILE.is_file(),
        "config_exists": CONFIG_FILE.is_file(),
        "model_sha256": EXPECTED_SHA,
        "language": "pl",
        "voice_id": MODEL_NAME,
        "sample_rate": SAMPLE_RATE,
        "speaker_wav_used": False,
        "gpu_used": False,
    }


@app.post("/generate")
def generate(req: GenerateRequest):

    if req.language_id != "pl":
        raise HTTPException(
            422, detail="Only Polish is supported"
        )

    if req.voice_id != MODEL_NAME:
        raise HTTPException(
            422, detail="Unsupported Piper voice"
        )

    with lock:
        try:
            ensure_model()

            config = SynthesisConfig(
                noise_scale=0.667,
                length_scale=1.0,
                noise_w_scale=0.8
            )

            output = io.BytesIO()

            start = time.perf_counter()
            cpu_start = time.process_time()

            with wave.open(output, "wb") as wav:
                voice_model.synthesize_wav(
                    req.text,
                    wav,
                    syn_config=config
                )

            generation_seconds = (
                time.perf_counter() - start
            )

            cpu_seconds = (
                time.process_time() - cpu_start
            )

            wav_bytes = output.getvalue()

            if len(wav_bytes) > MAX_WAV_BYTES:
                raise ValueError("Generated WAV too large")

            with wave.open(
                io.BytesIO(wav_bytes), "rb"
            ) as wav:

                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frames = wav.getnframes()
                pcm = wav.readframes(frames)

            if sample_rate != SAMPLE_RATE:
                raise ValueError("Unexpected sample rate")

            if channels != 1 or sample_width != 2:
                raise ValueError("Unexpected WAV format")

            if frames <= 0 or not any(pcm):
                raise ValueError("Empty or silent audio")

            duration_seconds = (
                frames / sample_rate
            )

            sha = hashlib.sha256(
                wav_bytes
            ).hexdigest()

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Engine": "piper",
                    "X-Model": MODEL_NAME,
                    "X-Model-SHA256": EXPECTED_SHA,
                    "X-Language": "pl",
                    "X-Voice": MODEL_NAME,
                    "X-Sample-Rate": str(sample_rate),
                    "X-Speaker-Wav-Used": "false",
                    "X-GPU-Used": "false",
                    "X-Audio-Duration-Sec": (
                        f"{duration_seconds:.6f}"
                    ),
                    "X-Generation-Time-Sec": (
                        f"{generation_seconds:.6f}"
                    ),
                    "X-CPU-Time-Sec": (
                        f"{cpu_seconds:.6f}"
                    ),
                    "X-Model-Load-Sec": (
                        f"{load_seconds:.6f}"
                    ),
                    "X-Process-Peak-RSS-MiB": (
                        f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.2f}"
                    ),
                    "X-Wav-SHA256": sha,
                }
            )

        except HTTPException:
            raise

        except Exception as exc:
            logger.exception("Piper synthesis failed")
            raise HTTPException(
                500,
                detail=(
                    "Piper synthesis failed: "
                    + type(exc).__name__
                )
            ) from exc

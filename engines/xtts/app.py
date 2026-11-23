"""Isolated TASK XTTS v2 HTTP provider. Direct WAV, no S3."""

import io
import threading
import time
import wave
from pathlib import Path

import numpy as np
import torch

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

ROOT = Path("/models/xtts_v2")
VOICE = "/voices/Arek.wav"

app = FastAPI(
    title="TASK XTTS direct WAV laboratory",
    version="0.1.0"
)

lock = threading.Lock()
model = None
conditioning = None
load_sec = None


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=280)
    language_id: str = "pl"
    voice_id: str = "Arek"


def ensure_model():
    global model, conditioning, load_sec

    if model is not None:
        return

    if not (ROOT / "model.pth").is_file():
        raise RuntimeError("Model missing")

    if not Path(VOICE).is_file():
        raise RuntimeError("Speaker recording missing")

    t0 = time.perf_counter()

    torch.set_num_threads(4)

    config = XttsConfig()
    config.load_json(str(ROOT / "config.json"))

    instance = Xtts.init_from_config(config)

    instance.load_checkpoint(
        config,
        checkpoint_dir=str(ROOT),
        use_deepspeed=False
    )

    instance.cuda()
    instance.eval()

    with torch.inference_mode():
        cond = instance.get_conditioning_latents(
            audio_path=[VOICE]
        )

    model = instance
    conditioning = cond
    load_sec = time.perf_counter() - t0


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "xtts",
        "mode": "REAL_GPU",
        "model": "xtts_v2",
        "model_loaded": model is not None,
        "voice_id": "Arek",
        "language": "pl"
    }


@app.post("/generate")
def generate(req: GenerateRequest):

    if req.language_id != "pl" or req.voice_id != "Arek":
        raise HTTPException(
            422,
            detail="Only pl / Arek supported"
        )

    if not torch.cuda.is_available():
        raise HTTPException(
            503,
            detail="CUDA unavailable"
        )

    with lock:

        try:
            ensure_model()

            torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()

            with torch.inference_mode():
                result = model.inference(
                    req.text,
                    "pl",
                    *conditioning
                )

            torch.cuda.synchronize()

            generation_sec = time.perf_counter() - start

            audio = np.asarray(
                result["wav"],
                dtype=np.float32
            ).reshape(-1)

            if (
                not audio.size
                or not np.isfinite(audio).all()
                or float(np.max(np.abs(audio))) == 0
            ):
                raise ValueError("Invalid or silent audio")

            pcm = (
                np.clip(audio, -1, 1) * 32767
            ).astype("<i2").tobytes()

            buffer = io.BytesIO()

            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(pcm)

            duration = len(audio) / 24000

            return Response(
                content=buffer.getvalue(),
                media_type="audio/wav",
                headers={
                    "X-Engine": "xtts",
                    "X-Model": "xtts_v2",
                    "X-Sample-Rate": "24000",
                    "X-Audio-Duration-Sec": f"{duration:.6f}",
                    "X-Generation-Time-Sec": f"{generation_sec:.6f}",
                    "X-Model-Load-Sec": f"{load_sec:.6f}",
                    "X-Peak-Cuda-Allocated-MiB": (
                        f"{torch.cuda.max_memory_allocated()/1048576:.2f}"
                    )
                }
            )

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                500,
                detail=(
                    "XTTS inference failed: "
                    + type(exc).__name__
                )
            ) from exc

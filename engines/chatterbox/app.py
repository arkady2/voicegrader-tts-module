"""TASK isolated Chatterbox Multilingual HTTP provider.

Language: Polish only
Speaker: Arek
Watermark: disabled
Chinese segmenter: skipped for PL only
Model files: read-only
"""

import hashlib
import inspect
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

from chatterbox.mtl_tts import ChatterboxMultilingualTTS

MODEL_DIR = Path(
    "/hf/hub/models--ResembleAI--chatterbox/snapshots/"
    "05e904af2b5c7f8e482687a9d7336c5c824467d9"
)

VOICE = "/voices/Arek.wav"

app = FastAPI(
    title="TASK Chatterbox Multilingual PL",
    version="0.1.0"
)

lock = threading.Lock()
model = None
model_load_seconds = None


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=280)
    language_id: str = "pl"
    voice_id: str = "Arek"


class NoOpWatermarker:
    """Return generated audio unchanged."""

    def apply_watermark(self, wav, sample_rate=None):
        return wav


def configure_polish_only():
    from chatterbox.models.tokenizers.tokenizer import (
        ChineseCangjieConverter
    )
    import chatterbox.mtl_tts as chatterbox_module

    initializer = ChineseCangjieConverter._init_segmenter
    source = inspect.getsource(initializer)

    if (
        "pkuseg" not in source
        or "self.segmenter" not in source
    ):
        raise RuntimeError(
            "Unexpected Chinese tokenizer implementation"
        )

    def skip_chinese_segmenter(self):
        self.segmenter = None

    ChineseCangjieConverter._init_segmenter = (
        skip_chinese_segmenter
    )

    chatterbox_module.perth.PerthImplicitWatermarker = (
        NoOpWatermarker
    )


def ensure_model():
    global model, model_load_seconds

    if model is not None:
        return

    if not Path(VOICE).is_file():
        raise RuntimeError("Missing reference speaker WAV")

    required = (
        "ve.pt",
        "s3gen.pt",
        "t3_mtl23ls_v2.safetensors",
        "grapheme_mtl_merged_expanded_v1.json",
    )

    if not all(
        (MODEL_DIR / name).is_file()
        for name in required
    ):
        raise RuntimeError("Incomplete local checkpoint")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")

    if "pl" not in (
        ChatterboxMultilingualTTS.get_supported_languages()
    ):
        raise RuntimeError("Polish unavailable")

    configure_polish_only()
    torch.set_num_threads(4)

    start = time.perf_counter()

    instance = ChatterboxMultilingualTTS.from_local(
        MODEL_DIR,
        "cuda"
    )

    model_load_seconds = (
        time.perf_counter() - start
    )

    model = instance


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "chatterbox",
        "variant": "multilingual",
        "version": "0.1.7",
        "mode": "REAL_GPU",
        "model_loaded": model is not None,
        "language": "pl",
        "voice_id": "Arek",
        "watermark_enabled": False,
        "chinese_segmenter": "skipped_pl_only",
    }


@app.post("/generate")
def generate(req: GenerateRequest):
    if req.language_id != "pl":
        raise HTTPException(
            422,
            detail="Only Polish supported by this service"
        )

    if req.voice_id != "Arek":
        raise HTTPException(
            422,
            detail="Only Arek supported"
        )

    with lock:
        try:
            ensure_model()

            torch.cuda.reset_peak_memory_stats()

            start = time.perf_counter()

            with torch.inference_mode():
                result = model.generate(
                    req.text,
                    language_id="pl",
                    audio_prompt_path=VOICE
                )

            torch.cuda.synchronize()

            generation_seconds = (
                time.perf_counter() - start
            )

            if isinstance(result, torch.Tensor):
                audio = (
                    result.detach()
                    .float()
                    .cpu()
                    .numpy()
                )
            else:
                audio = np.asarray(
                    result,
                    dtype=np.float32
                )

            audio = audio.reshape(-1)

            if not audio.size:
                raise ValueError("Empty waveform")

            if not np.isfinite(audio).all():
                raise ValueError("Nonfinite waveform")

            peak = float(np.max(np.abs(audio)))

            if peak <= 0:
                raise ValueError("Silent waveform")

            sample_rate = int(model.sr)

            if sample_rate <= 0:
                raise ValueError("Invalid sample rate")

            pcm = (
                np.clip(audio, -1.0, 1.0) * 32767
            ).astype("<i2").tobytes()

            if len(pcm) > 30 * 1024 * 1024:
                raise ValueError("Audio exceeds size limit")

            buffer = io.BytesIO()

            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm)

            duration_seconds = (
                len(audio) / sample_rate
            )

            wav_bytes = buffer.getvalue()

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Engine": "chatterbox",
                    "X-Model": "chatterbox-multilingual-v2",
                    "X-Language": "pl",
                    "X-Voice": "Arek",
                    "X-Watermark-Enabled": "false",
                    "X-Model-Snapshot": MODEL_DIR.name,
                    "X-Sample-Rate": str(sample_rate),
                    "X-Audio-Duration-Sec": (
                        f"{duration_seconds:.6f}"
                    ),
                    "X-Generation-Time-Sec": (
                        f"{generation_seconds:.6f}"
                    ),
                    "X-Model-Load-Sec": (
                        f"{model_load_seconds:.6f}"
                    ),
                    "X-Peak-Cuda-Allocated-MiB": (
                        f"{torch.cuda.max_memory_allocated()/1048576:.2f}"
                    ),
                    "X-Wav-SHA256": hashlib.sha256(
                        wav_bytes
                    ).hexdigest()
                }
            )

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Chatterbox inference failed: "
                    + type(exc).__name__
                )
            ) from exc

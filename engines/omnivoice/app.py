from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

import boto3
import numpy as np
import soundfile as sf
import torch
from botocore.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

ENGINE_NAME = os.getenv("ENGINE_NAME", "omnivoice")
ENGINE_DISPLAY_NAME = os.getenv("ENGINE_DISPLAY_NAME", "OmniVoice")
OMNIVOICE_MODEL_ID = os.getenv("OMNIVOICE_MODEL_ID", "k2-fsa/OmniVoice")
OMNIVOICE_DEVICE = os.getenv("OMNIVOICE_DEVICE", "cuda:0")
OMNIVOICE_SPEAKER_WAV = os.getenv("OMNIVOICE_SPEAKER_WAV", "/voices/Arek.wav")
OMNIVOICE_REF_TEXT = os.getenv("OMNIVOICE_REF_TEXT", "").strip() or None
OMNIVOICE_PRELOAD_MODEL = os.getenv("OMNIVOICE_PRELOAD_MODEL", "false").lower() in {"1", "true", "yes", "on"}
OMNIVOICE_NUM_STEP = int(os.getenv("OMNIVOICE_NUM_STEP", "32"))
OMNIVOICE_SPEED = float(os.getenv("OMNIVOICE_SPEED", "1.0"))
OMNIVOICE_SAMPLE_RATE = int(os.getenv("OMNIVOICE_SAMPLE_RATE", "24000"))

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "caise-voicemed")

app = FastAPI(title=f"VoiceMed Real TTS Adapter - {ENGINE_DISPLAY_NAME}", version="0.3.0")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

_model = None
_model_loaded_at: Optional[float] = None
_model_lock = Lock()
_infer_lock = Lock()


class TTSGenerateRequest(BaseModel):
    """Kontrakt zgodny z XTTS, Chatterbox i Piper w VoiceMed."""

    job_id: str
    engine: str
    text: str = Field(..., min_length=1)
    language: str = "pl"
    voice: str = "default"
    output_prefix: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DirectGenerateRequest(BaseModel):
    """Endpoint diagnostyczny: zwraca WAV bezpośrednio w odpowiedzi HTTP."""

    text: str = Field(min_length=1, max_length=5000)
    language_id: str | None = "pl"
    ref_audio: str | None = None
    ref_text: str | None = None
    instruct: str | None = None
    num_step: int = Field(default=32, ge=4, le=64)
    speed: float = Field(default=1.0, gt=0.1, le=3.0)

    @model_validator(mode="after")
    def validate_mode(self) -> "DirectGenerateRequest":
        if self.ref_audio and self.instruct:
            raise ValueError("Użyj ref_audio albo instruct, nie obu jednocześnie.")
        return self


def parse_output_prefix(prefix: str) -> str:
    expected = f"s3://{S3_BUCKET}/"
    if prefix.startswith(expected):
        return prefix[len(expected):].rstrip("/")
    if prefix.startswith("s3://"):
        parts = prefix.split("/", 3)
        if len(parts) < 4:
            raise ValueError(f"Nieprawidłowy output_prefix: {prefix}")
        return parts[3].rstrip("/")
    return prefix.rstrip("/")


def upload_file(path: Path, key: str, content_type: str) -> None:
    with path.open("rb") as file_obj:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=file_obj, ContentType=content_type)


def upload_json(key: str, payload: Any) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ContentType="application/json; charset=utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audio_info(path: Path) -> Dict[str, Any]:
    info = sf.info(str(path))
    return {
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_sec": float(info.frames / info.samplerate) if info.samplerate else None,
        "format": "wav",
    }


def load_model():
    global _model, _model_loaded_at

    with _model_lock:
        if _model is not None:
            return _model

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA nie jest dostępna w kontenerze. Sprawdź --gpus all i NVIDIA Container Toolkit."
            )

        from omnivoice import OmniVoice

        started = time.perf_counter()
        _model = OmniVoice.from_pretrained(
            OMNIVOICE_MODEL_ID,
            device_map=OMNIVOICE_DEVICE,
            dtype=torch.float16,
        )
        _model_loaded_at = time.perf_counter() - started
        return _model


def normalize_language(language: str | None) -> str:
    return (language or "pl").strip().lower()


def resolve_generation_settings(payload: TTSGenerateRequest) -> Dict[str, Any]:
    metadata = payload.metadata or {}

    ref_audio = str(metadata.get("ref_audio") or OMNIVOICE_SPEAKER_WAV)
    ref_text = metadata.get("ref_text") or OMNIVOICE_REF_TEXT
    num_step = int(metadata.get("num_step", OMNIVOICE_NUM_STEP))
    speed = float(metadata.get("speed", OMNIVOICE_SPEED))

    if not 4 <= num_step <= 64:
        raise ValueError(f"num_step poza zakresem 4..64: {num_step}")
    if not 0.1 < speed <= 3.0:
        raise ValueError(f"speed poza zakresem (0.1, 3.0]: {speed}")

    return {
        "language_id": normalize_language(payload.language),
        "ref_audio": ref_audio,
        "ref_text": ref_text,
        "num_step": num_step,
        "speed": speed,
    }


def synthesize_to_file(
    *,
    text: str,
    wav_path: Path,
    language_id: str | None,
    ref_audio: str | None,
    ref_text: str | None,
    instruct: str | None,
    num_step: int,
    speed: float,
) -> tuple[float, Dict[str, Any]]:
    model = load_model()

    kwargs: Dict[str, Any] = {
        "text": text,
        "num_step": num_step,
        "speed": speed,
    }
    if language_id:
        kwargs["language_id"] = language_id
    if ref_audio:
        ref_path = Path(ref_audio)
        if not ref_path.is_file():
            raise FileNotFoundError(f"Nie znaleziono pliku referencyjnego: {ref_audio}")
        kwargs["ref_audio"] = str(ref_path)
        if ref_text:
            kwargs["ref_text"] = ref_text
    elif instruct:
        kwargs["instruct"] = instruct

    started = time.perf_counter()
    with _infer_lock:
        audio_list = model.generate(**kwargs)
    elapsed_sec = time.perf_counter() - started

    if not audio_list:
        raise RuntimeError("Model zwrócił pusty wynik audio.")

    waveform = np.asarray(audio_list[0], dtype=np.float32).squeeze()
    if waveform.ndim != 1:
        raise RuntimeError(f"Nieoczekiwany kształt audio: {waveform.shape}")

    sf.write(
        str(wav_path),
        waveform,
        OMNIVOICE_SAMPLE_RATE,
        format="WAV",
        subtype="PCM_16",
    )
    return elapsed_sec, audio_info(wav_path)


@app.on_event("startup")
async def startup() -> None:
    if OMNIVOICE_PRELOAD_MODEL:
        try:
            load_model()
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] OmniVoice preload failed: {exc}", flush=True)


@app.get("/health")
async def health() -> Dict[str, Any]:
    speaker_path = Path(OMNIVOICE_SPEAKER_WAV)
    return {
        "status": "ok",
        "engine": ENGINE_NAME,
        "display_name": ENGINE_DISPLAY_NAME,
        "model_name": OMNIVOICE_MODEL_ID,
        "model_loaded": _model is not None,
        "model_device": OMNIVOICE_DEVICE,
        "model_load_elapsed_sec": round(_model_loaded_at, 3) if _model_loaded_at else None,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "speaker_wav": str(speaker_path),
        "speaker_wav_exists": speaker_path.exists(),
        "speaker_wav_size_bytes": speaker_path.stat().st_size if speaker_path.exists() else None,
        "s3_endpoint": S3_ENDPOINT,
        "s3_bucket": S3_BUCKET,
    }


@app.post("/warmup")
async def warmup() -> Dict[str, Any]:
    try:
        started = time.perf_counter()
        load_model()
        return {
            "status": "ok",
            "engine": ENGINE_NAME,
            "model_loaded": True,
            "model_device": OMNIVOICE_DEVICE,
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "speaker_wav": OMNIVOICE_SPEAKER_WAV,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=repr(exc)) from exc


@app.post("/tts/generate")
async def generate_tts(payload: TTSGenerateRequest) -> Dict[str, Any]:
    if payload.engine != ENGINE_NAME:
        raise HTTPException(
            status_code=400,
            detail=f"This adapter is {ENGINE_NAME}, got {payload.engine}",
        )

    try:
        settings = resolve_generation_settings(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Błędne parametry OmniVoice: {exc}") from exc

    speaker_path = Path(settings["ref_audio"])
    if not speaker_path.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Brak pliku głosu {speaker_path}. "
                "Oczekiwano Arek.wav zamontowanego w kontenerze."
            ),
        )

    try:
        prefix_key = parse_output_prefix(payload.output_prefix)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audio_key = f"{prefix_key}/output.wav"
    metadata_key = f"{prefix_key}/metadata.json"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "output.wav"
            elapsed_sec, info = synthesize_to_file(
                text=payload.text,
                wav_path=wav_path,
                language_id=settings["language_id"],
                ref_audio=settings["ref_audio"],
                ref_text=settings["ref_text"],
                instruct=None,
                num_step=settings["num_step"],
                speed=settings["speed"],
            )

            duration_sec = float(info.get("duration_sec") or 0.0)
            audio_sha256 = sha256_file(wav_path)
            speaker_sha256 = sha256_file(speaker_path)

            upload_file(wav_path, audio_key, "audio/wav")

            metadata = {
                "job_id": payload.job_id,
                "engine": ENGINE_NAME,
                "engine_display_name": ENGINE_DISPLAY_NAME,
                "language": settings["language_id"],
                "voice": payload.voice,
                "model_name": OMNIVOICE_MODEL_ID,
                "model_device": OMNIVOICE_DEVICE,
                "speaker_wav": str(speaker_path),
                "speaker_wav_sha256": speaker_sha256,
                "ref_text_provided": bool(settings["ref_text"]),
                "sample_rate": info.get("sample_rate"),
                "channels": info.get("channels"),
                "frames": info.get("frames"),
                "format": "wav",
                "demo_mode": False,
                "real_tts": True,
                "elapsed_sec": round(elapsed_sec, 6),
                "audio_duration_sec": round(duration_sec, 6),
                "rtf": round(elapsed_sec / duration_sec, 6) if duration_sec else None,
                "input_chars": len(payload.text),
                "input_words": len(payload.text.split()),
                "audio_uri": f"s3://{S3_BUCKET}/{audio_key}",
                "audio_sha256": audio_sha256,
                "generation_params": {
                    "num_step": settings["num_step"],
                    "speed": settings["speed"],
                    "language_id": settings["language_id"],
                },
                "request_metadata": payload.metadata,
            }
            upload_json(metadata_key, metadata)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Błąd generacji lub zapisu S3 OmniVoice: {type(exc).__name__}: {exc}",
        ) from exc

    return {
        "job_id": payload.job_id,
        "engine": ENGINE_NAME,
        "engine_display_name": ENGINE_DISPLAY_NAME,
        "status": "completed",
        "audio_uri": f"s3://{S3_BUCKET}/{audio_key}",
        "metadata_uri": f"s3://{S3_BUCKET}/{metadata_key}",
        "elapsed_sec": round(elapsed_sec, 6),
        "audio_duration_sec": round(duration_sec, 6),
        "rtf": round(elapsed_sec / duration_sec, 6) if duration_sec else None,
        "demo_mode": False,
        "real_tts": True,
        "model_name": OMNIVOICE_MODEL_ID,
        "model_device": OMNIVOICE_DEVICE,
    }


@app.post("/generate")
async def generate_direct(req: DirectGenerateRequest) -> Response:
    """Zachowany endpoint diagnostyczny z wersji 0.2.0."""

    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "output.wav"
            generation_elapsed_sec, info = synthesize_to_file(
                text=req.text,
                wav_path=wav_path,
                language_id=req.language_id,
                ref_audio=req.ref_audio,
                ref_text=req.ref_text,
                instruct=req.instruct,
                num_step=req.num_step,
                speed=req.speed,
            )
            wav_bytes = wav_path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Generacja OmniVoice nie powiodła się: {type(exc).__name__}: {exc}",
        ) from exc

    request_elapsed_sec = time.perf_counter() - started
    headers = {
        "X-Generation-Time-Sec": f"{generation_elapsed_sec:.6f}",
        "X-Request-Time-Sec": f"{request_elapsed_sec:.6f}",
        "X-Audio-Duration-Sec": f"{float(info.get('duration_sec') or 0.0):.6f}",
        "X-Sample-Rate": str(info.get("sample_rate") or OMNIVOICE_SAMPLE_RATE),
        "X-Model": OMNIVOICE_MODEL_ID,
    }
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)

"""TASK Piper HTTP adapter, native 22050 Hz WAV, CPU only."""

import array
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
import wave

MAX_WAV = 30 * 1024 * 1024

MODEL = "pl_PL-gosia-medium"
MODEL_SHA = (
    "38f66464240ed74f186e6b7dc13c6e3b22e"
    "023426299f25c2b3cc9dfa9373fbc"
)


def generate(base_url, text):

    payload = {
        "text": text,
        "language_id": "pl",
        "voice_id": MODEL,
    }

    request = urllib.request.Request(
        base_url.rstrip("/") + "/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=180
        ) as response:

            if response.status != 200:
                raise ValueError("Unexpected HTTP status")

            if response.headers.get_content_type() != "audio/wav":
                raise ValueError("Unexpected content type")

            headers = response.headers

            def required(name):
                value = headers.get(name)

                if value is None:
                    raise ValueError(
                        "Missing header: " + name
                    )

                return value

            if required("X-Engine") != "piper":
                raise ValueError("Incorrect engine")

            if required("X-Model") != MODEL:
                raise ValueError("Incorrect model")

            if required("X-Model-SHA256") != MODEL_SHA:
                raise ValueError("Incorrect ONNX checksum")

            if required("X-GPU-Used").lower() != "false":
                raise ValueError("Unexpected GPU execution")

            if required("X-Speaker-Wav-Used").lower() != "false":
                raise ValueError("Unexpected speaker cloning")

            if required("X-Sample-Rate") != "22050":
                raise ValueError("Unexpected sample rate")

            declared_sha = required("X-Wav-SHA256")

            generation_sec = float(
                required("X-Generation-Time-Sec")
            )

            cpu_sec = float(
                required("X-CPU-Time-Sec")
            )

            model_load_sec = float(
                required("X-Model-Load-Sec")
            )

            peak_ram_mib = float(
                required("X-Process-Peak-RSS-MiB")
            )

            data = response.read(MAX_WAV + 1)

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Piper returned HTTP {exc.code}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Piper HTTP connection failed"
        ) from exc

    if len(data) > MAX_WAV:
        raise ValueError("Piper WAV too large")

    actual_sha = hashlib.sha256(data).hexdigest()

    if actual_sha.lower() != declared_sha.lower():
        raise ValueError("Piper WAV SHA256 mismatch")

    with wave.open(io.BytesIO(data), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.getnframes()

        if sample_rate != 22050:
            raise ValueError("Piper must retain native 22050 Hz")

        if channels != 1 or sample_width != 2:
            raise ValueError("Expected mono PCM16")

        if frames <= 0:
            raise ValueError("Empty WAV")

        pcm = wav.readframes(frames)

    samples = array.array("h")
    samples.frombytes(pcm)

    if sys.byteorder != "little":
        samples.byteswap()

    if not any(samples):
        raise ValueError("Silent WAV")

    duration = frames / sample_rate

    metrics = {
        "model": MODEL,
        "model_sha256": MODEL_SHA,
        "model_type": "piper-onnx",
        "model_device": "cpu",
        "language": "pl_PL",
        "voice": MODEL,
        "speaker_wav_used": False,
        "gpu_used": False,
        "sample_rate": sample_rate,
        "channels": channels,
        "generation_time_sec": str(generation_sec),
        "cpu_generation_sec": cpu_sec,
        "model_load_sec": model_load_sec,
        "process_peak_rss_mib": peak_ram_mib,
        "audio_duration_sec": str(duration),
        "duration_verified_sec": round(duration, 6),
        "rtf": round(generation_sec / duration, 6),
        "noise_scale": 0.667,
        "length_scale": 1.0,
        "noise_w_scale": 0.8,
        "sha256_provider": actual_sha,
    }

    return data, metrics

"""TASK Chatterbox Multilingual HTTP WAV adapter.

Polish only, Arek reference voice.
Watermark disabled explicitly by provider.
No MinIO, no downloading models.
"""

import array
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
import wave

MAX_WAV = 30 * 1024 * 1024


def generate(base_url, text):

    request = urllib.request.Request(
        base_url.rstrip("/") + "/generate",
        data=json.dumps({
            "text": text,
            "language_id": "pl",
            "voice_id": "Arek",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=240
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
                        "Missing response header: " + name
                    )
                return value

            if required("X-Watermark-Enabled").lower() != "false":
                raise ValueError(
                    "Watermark configuration mismatch"
                )

            if required("X-Language") != "pl":
                raise ValueError("Unexpected language")

            model = required("X-Model")
            snapshot = required("X-Model-Snapshot")
            generation_sec = float(
                required("X-Generation-Time-Sec")
            )
            model_load_sec = float(
                required("X-Model-Load-Sec")
            )
            cuda_mib = float(
                required("X-Peak-Cuda-Allocated-MiB")
            )
            expected_sha = required("X-Wav-SHA256")

            data = response.read(MAX_WAV + 1)

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Chatterbox HTTP {exc.code}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Chatterbox HTTP connection failed"
        ) from exc

    if len(data) > MAX_WAV:
        raise ValueError("Chatterbox WAV too large")

    actual_sha = hashlib.sha256(data).hexdigest()

    if actual_sha.lower() != expected_sha.lower():
        raise ValueError("Chatterbox SHA256 mismatch")

    with wave.open(io.BytesIO(data), "rb") as wav:

        if wav.getframerate() != 24000:
            raise ValueError("Unexpected sample rate")

        if wav.getnchannels() != 1:
            raise ValueError("Expected mono")

        if wav.getsampwidth() != 2:
            raise ValueError("Expected PCM16")

        frames = wav.getnframes()

        if frames <= 0:
            raise ValueError("Empty WAV")

        pcm = wav.readframes(frames)

    samples = array.array("h")
    samples.frombytes(pcm)

    if sys.byteorder != "little":
        samples.byteswap()

    if not any(sample != 0 for sample in samples):
        raise ValueError("Silent WAV")

    metrics = {
        "model": model,
        "model_snapshot": snapshot,
        "language": "pl",
        "voice": "Arek",
        "watermark_enabled": False,
        "watermark_implementation": "NoOpWatermarker",
        "chinese_segmenter": "skipped_pl_only",
        "generation_time_sec": str(generation_sec),
        "audio_duration_sec": str(frames / 24000),
        "duration_verified_sec": round(frames / 24000, 6),
        "sample_rate": "24000",
        "model_load_sec": str(model_load_sec),
        "peak_cuda_allocated_mib": str(cuda_mib),
        "sha256_provider": actual_sha,
    }

    return data, metrics

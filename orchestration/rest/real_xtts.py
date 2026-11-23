"""Direct real XTTS v2 HTTP adapter, without S3."""

import io
import json
import urllib.error
import urllib.request
import wave

MAX_WAV = 30 * 1024 * 1024


def generate(base_url, text):
    payload = {
        "text": text,
        "language_id": "pl",
        "voice_id": "Arek",
    }

    request = urllib.request.Request(
        base_url.rstrip("/") + "/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.headers.get_content_type() != "audio/wav":
                raise ValueError("Unexpected XTTS content type")

            metrics = {
                "model": response.headers.get("X-Model"),
                "generation_time_sec": response.headers.get(
                    "X-Generation-Time-Sec"
                ),
                "audio_duration_sec": response.headers.get(
                    "X-Audio-Duration-Sec"
                ),
                "sample_rate": response.headers.get("X-Sample-Rate"),
                "model_load_sec": response.headers.get(
                    "X-Model-Load-Sec"
                ),
                "peak_cuda_allocated_mib": response.headers.get(
                    "X-Peak-Cuda-Allocated-MiB"
                ),
            }

            data = response.read(MAX_WAV + 1)

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"XTTS returned HTTP {exc.code}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "XTTS HTTP connection failed"
        ) from exc

    if len(data) > MAX_WAV:
        raise ValueError("XTTS WAV too large")

    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() > 0

        frames = wav.getnframes()
        pcm = wav.readframes(frames)

        if not any(pcm):
            raise ValueError("XTTS produced silent audio")

        metrics["duration_verified_sec"] = round(
            frames / 24000, 6
        )

    return data, metrics

"""Adapter to the existing OmniVoice 0.3.0 /generate endpoint."""
import io
import json
import urllib.error
import urllib.request
import wave

MAX_WAV = 30 * 1024 * 1024


def generate(url: str, text: str):
    payload = {
        "text": text,
        "language_id": "pl",
        "ref_audio": "/voices/Arek.wav",
        "num_step": 16,
        "speed": 1.0,
    }

    request = urllib.request.Request(
        url.rstrip("/") + "/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_type = response.headers.get_content_type()
            if content_type != "audio/wav":
                raise ValueError("Unexpected response Content-Type")

            audio = response.read(MAX_WAV + 1)
            metrics = {
                "generation_time_sec": response.headers.get(
                    "X-Generation-Time-Sec"
                ),
                "audio_duration_sec": response.headers.get(
                    "X-Audio-Duration-Sec"
                ),
                "sample_rate": response.headers.get("X-Sample-Rate"),
                "model": response.headers.get("X-Model"),
            }
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"OmniVoice returned HTTP {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "OmniVoice connection failed"
        ) from exc

    if len(audio) > MAX_WAV:
        raise ValueError("Audio exceeds configured size limit")

    with wave.open(io.BytesIO(audio), "rb") as wav:
        if wav.getnchannels() != 1:
            raise ValueError("Expected mono WAV")
        if wav.getsampwidth() != 2:
            raise ValueError("Expected 16-bit PCM WAV")
        if wav.getframerate() != 24000:
            raise ValueError("Expected 24 kHz WAV")
        if wav.getnframes() < 1:
            raise ValueError("Empty WAV")

        pcm = wav.readframes(wav.getnframes())
        if not any(pcm):
            raise ValueError("Generated audio is silent")

        metrics["frames"] = wav.getnframes()
        metrics["duration_verified_sec"] = round(
            wav.getnframes() / wav.getframerate(), 6
        )

    return audio, metrics

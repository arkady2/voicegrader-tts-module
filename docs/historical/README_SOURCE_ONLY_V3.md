# TTSCompare — SoftwareX source-only candidate v3

Status: CANDIDATE — not publication-ready.

This package contains source code and configuration extracted
from the checksum-verified v2 laboratory package.

Model weights, Hugging Face cache and private Arek.wav are
not included. The original full v2 research archive is
preserved separately.

## Verified laboratory experiments

- Piper, XTTS, Chatterbox and OmniVoice clean builds: PASS.
- REST API v0.7 real TTS end-to-end: PASS 4/4.
- Isolated n8n 2.26.5 real TTS end-to-end: PASS 4/4.

## n8n provenance

Original laboratory workflow:
orchestration/n8n/workflow-four-real-tts-cli.json

Actually tested isolated workflow:
verification-v3/n8n-real-tested-workflow.json

The tested workflow uses isolated service addresses and
additional WAV validation. These workflows are not identical.

## Model dependencies

OmniVoice requires openai/whisper-large-v3-turbo when
reference-audio transcription is not explicitly supplied.

Private voice recordings must be provided independently.
Piper uses pl_PL-gosia-medium.

XTTS model terms require user-side review and acceptance.
No license acceptance is implied by this package.

## Outstanding reproducibility work

The REST Dockerfile inherits from a local base image.
Independent reconstruction of that base image is not
yet demonstrated.

A clean installation test, license review, security audit
and manuscript consistency review remain necessary.

## Integrity

verification-v3/provenance.json contains SHA-256 hashes
of local experimental evidence and model revision metadata.

SHA256SUMS.v3 covers this source-only candidate.

The original v2 SHA256SUMS is intentionally not copied:
it describes the full v2 package including model assets.

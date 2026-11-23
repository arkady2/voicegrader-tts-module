# TTSCompare RLHF v0.7 REAL-ONLY — r1

Image: task-ttscompare-rlhf-realonly:0.7.0-r1
Image ID: sha256:8c242d425fc8bd5ad43ae1a8b77591187a8f325ffe61722a7e918f553a792bad

Base image: task-ttscompare-rlhf-base:v06-2a32c18a8b04
Base ID: sha256:2a32c18a8b04b5971f308be199fabfeea3e75483b3f3faa0fb6c50ce79858834

Fix: COPY --chmod=0644 for Python source files.

Validation:
- All four adapter modules import successfully.
- Application source SHA-256 verified.
- Runs as non-root with a read-only filesystem.
- No network access or TTS inference used during validation.
- Docker Compose configuration validated.

IMPORTANT:
- Existing v0.7 container was not replaced.
- compose-tested.yaml is prepared but not deployed.
- The image remains local to ksmvm1.

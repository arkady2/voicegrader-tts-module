# Engine run modes

OmniVoice, XTTS and Chatterbox use NVIDIA GPUs; Piper runs on CPU. The supplied Compose configurations allow individual engine selection. `compose.engines.profiles.yaml` additionally provides an `all` profile for hosts with sufficient resources.

For a GPU with 8 GB VRAM, the operational policy is **one GPU TTS engine at a time**. This policy has not been validated through runtime measurements on the target RTX 5060. GPU usage by processes outside Docker must also be considered.

The `tts-run.sh` verification gate is intentional: do not bypass it or create its marker without completing the required verification. An engine build or REST end-to-end test does not establish that every Compose profile will run unchanged on a new host. The standalone REST image does not start n8n or the engines.

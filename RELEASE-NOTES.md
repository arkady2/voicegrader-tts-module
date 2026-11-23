# VoiceGrader — TTS Module Source Release

Release date: 2026-11-23

## Contents

Source code and Docker configurations for OmniVoice, XTTS v2, Chatterbox and Piper; REST API v0.7 REAL_ONLY; n8n workflow definitions; model asset utilities and provenance metadata; and laboratory provenance metadata. Detailed historical verification records, model weights, private voice recordings and runtime credentials are excluded.

## Verification

TASK laboratory verification covered builds and synthesis for the four engines, REST HTTP smoke tests, an independent REST image build, four-engine REST end-to-end synthesis and n8n end-to-end processing. The detailed historical verification records are not included in this repository. These results apply to the tested configurations and do not establish full VoiceGrader pipeline validation or clean-host reproducibility.

## Integrity and licensing

`SHA256SUMS.v4` is a historical source manifest and does not verify the current repository contents. Third-party model terms apply; licensing of the application source awaits a decision by the authorized rights holder. See `LICENSE-REVIEW.md`.

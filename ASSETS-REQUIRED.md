# Model and reference voice assets

The source distribution excludes model weights and private reference recordings. Model identifiers, paths and provenance information are listed in `models/models-and-runtime.json`.

| Engine | Model or voice asset |
|---|---|
| OmniVoice | `k2-fsa/OmniVoice` |
| XTTS v2 | `coqui/XTTS-v2` |
| Chatterbox | `ResembleAI/chatterbox` |
| Piper | `pl_PL-gosia-medium` |

## Reference voice configuration

OmniVoice requires a reference WAV recording **and a matching transcription** for the supported VoiceGrader TTS configuration. Supply the recording separately and configure the corresponding transcription through `OMNIVOICE_REF_TEXT` or the request's `ref_text` field. The recording path is configured through `OMNIVOICE_SPEAKER_WAV` (the supplied Compose files use `/voices/Arek.wav`). The current engine implementation accepts an unset `ref_text`; it does not enforce this project-level requirement during request validation. Other reference configurations are outside the scope of this release.

The laboratory setup used the private `Arek.wav` recording with OmniVoice, XTTS and Chatterbox. No reference recording or transcription is redistributed in this package. Operators must use recordings they are authorized to process.

Model files must be supplied separately. XTTS model terms require operator review and explicit acceptance; the package does not create an acceptance file automatically. See [LICENSE-REVIEW.md](LICENSE-REVIEW.md).

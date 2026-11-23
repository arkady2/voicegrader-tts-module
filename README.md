# VoiceGrader — Text-to-Speech Module

This repository contains the TTS component of VoiceGrader, a pipeline for speech resynthesis and RLHF-based ASR fine-tuning. It integrates OmniVoice, XTTS v2, Chatterbox and Piper through engine HTTP services, an asynchronous REST API and an independent n8n workflow. Model weights and private reference recordings are not distributed.

The module was developed and tested in the TASK laboratory under the TTSCompare name. Some source files and deployment identifiers retain the historical TASK RLHF and TTSCompare names. SoftwareX refers to the publication context, not a software version.

## Engines

| Engine | Processing | Configured voice |
|---|---|---|
| OmniVoice | NVIDIA GPU | Arek (reference WAV and matching transcription) |
| XTTS v2 | NVIDIA GPU | Arek (reference WAV) |
| Chatterbox | NVIDIA GPU | Arek (reference WAV) |
| Piper | CPU | `pl_PL-gosia-medium` |

The operator must supply the reference recording and, for the supported OmniVoice configuration, its transcription. See [ASSETS-REQUIRED.md](ASSETS-REQUIRED.md) for model and voice assets.

## Repository layout

| Path | Contents |
|---|---|
| `engines/` | Engine HTTP services and Dockerfiles |
| `orchestration/rest/` | REST API v0.7 source and standalone Dockerfile |
| `orchestration/n8n/` | Laboratory four-engine workflow |
| `orchestration/rest-release/` | Historical REST deployment artifacts; not the standalone build path |
| `models/`, `tools/` | Model metadata and asset-management utilities |

## Engine deployment

Two Compose configurations are included: `compose.engines.profiles.yaml` and `compose.engines.proxmox.yaml`. Both support individual engine selection. The former also defines an `all` profile. Published host ports in these files are bound to `127.0.0.1`; their mapped ports are `19805` (OmniVoice), `19864` (XTTS), `19867` (Chatterbox) and `19869` (Piper).

Inspect the Piper service configuration without starting it:

```bash
docker compose -f compose.engines.proxmox.yaml --profile piper config --services
```

The `tts-run.sh` helper provides planning and a verification gate. Engine startup through this helper requires a local `BUILD-AND-SYNTHESIS-VERIFIED` marker. The marker is not distributed with the source release and must not be created without completing the required build and synthesis verification:

```bash
bash tts-run.sh piper plan
```

See [RUN-MODES.md](RUN-MODES.md) for GPU constraints. The standalone REST image can be built separately from engine images:

```bash
docker build -f orchestration/rest/Dockerfile.standalone -t ttscompare-rest:local orchestration/rest
```

This command builds the REST service; it does not start engines or n8n.

## REST API v0.7

The REST service submits synthesis jobs asynchronously and returns a ZIP archive containing generated audio and a result manifest. Its principal endpoints are:

| Method | Path | Result |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/v1/capabilities` | Available engines, formats and advertised limits |
| `POST` | `/v1/jobs` | Accept a job (`202`) and return its identifier |
| `GET` | `/v1/jobs/{jid}` | Job status, counters and archive metadata |
| `GET` | `/v1/results/{jid}/archive` | Download the ZIP when ready |

Example request body for `POST /v1/jobs` (use a new `request_id` for a new job):

```json
{
  "request_id": "example-001",
  "language": "pl",
  "audio_format": "wav",
  "archive_format": "zip",
  "items": [
    {"item_id": "item-001", "text": "To jest test syntezy.", "engine": "piper", "voice_id": "pl_PL-gosia-medium"}
  ]
}
```

Accepted jobs return a response of the form `{"job_id":"job-...","status":"queued"}`. Poll `GET /v1/jobs/{jid}` until the status changes from `queued` or `running` to `completed`, `completed_with_failures` or `failed`. A status response includes `request_id`, item counters, `archive_url`, archive size and SHA-256 when available, and timestamps. Item-level failures are recorded in the result archive when processing reaches that stage.

**Effective limits:** the request schema accepts 1–100 items and text fields up to 4,000 characters, and `/v1/capabilities` advertises `max_batch_size: 100`. The REAL_ONLY submission path applies a stricter limit to configured real-engine items: at most **one item per engine per job**, with **280 characters per such item**. A request using all four engines therefore contains at most four configured real-engine items. The server also limits active jobs to five, and concurrent requests for a busy engine can be rejected. The advertised schema limit is not the effective real-engine synthesis limit.

Only `pl` / `wav` / `zip` is accepted. Configured voices are `Arek` for OmniVoice, XTTS and Chatterbox, and `pl_PL-gosia-medium` for Piper. Reusing a `request_id` with the same payload returns the existing job; a different payload with that ID is rejected.

Errors use an `error` object with `code`, `message` and `retryable`. Typical responses include `422` for invalid input or unsupported formats, `409` for request-ID conflicts or an archive that is not ready, `429` for engine contention or a full queue, `404` for an unknown job, `410` for an expired archive and `500` when an expected archive file is missing. Engine failures may also be represented as failed items in a completed job.

### Storage and access

The REST implementation uses SQLite under `RLHF_POC_DATA` (default `/state`). The `jobs.payload` field stores the submitted JSON, **including synthesis text**; `job_events` records state changes. Completed ZIP archives are stored in the `archives/` subdirectory. The API sets a 24-hour archive expiry (`result_retention_seconds: 86400`) and rejects expired downloads, but the supplied REST code does **not** implement automatic physical deletion of ZIP files or SQLite records. No application-level authentication is implemented in this REST source. Network access must therefore be controlled by the deployment; do not expose the service directly to untrusted networks.

## n8n workflow

The n8n path calls engine services directly and is separate from the REST job queue.

| File | Purpose | Engine addresses | WAV checks |
|---|---|---|---|
| `orchestration/n8n/workflow-four-real-tts-cli.json` | Laboratory workflow | Host loopback: `8005`, `18764`, `18767`, `18769` | Checks for returned binary data; labels it `received_binary_unverified` |

These addresses are environment-specific and differ from the host ports in the supplied Compose configurations (`19805`, `19864`, `19867`, `19869`). Importing the workflow alone does not configure network routing. The distributed workflow does not independently verify WAV structure. A separate validation workflow was used in laboratory testing but is not included in the current repository.

## Verification and release

TASK laboratory verification covered engine builds and synthesis, REST HTTP checks, an independent REST build, four-engine REST end-to-end synthesis, and n8n end-to-end processing. These were **component and integration tests**, not proof of deployment on an arbitrary fresh host or operation of the complete VoiceGrader pipeline. Detailed historical verification records are not included in the current repository. See [RELEASE-NOTES.md](RELEASE-NOTES.md).

`SHA256SUMS.v4` describes an earlier source state and is not a checksum manifest for the current repository. The application source license remains subject to a decision by the authorized rights holder; see [LICENSE-REVIEW.md](LICENSE-REVIEW.md).

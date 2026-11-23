"""VoiceGrader TTS REST v0.7: asynchronous real-engine synthesis jobs."""
import hashlib
import io
import json
import os
import sqlite3
import threading
import wave
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from real_omnivoice import generate as generate_real_omnivoice
from real_xtts import generate as generate_real_xtts
from real_chatterbox import generate as generate_real_chatterbox
from real_piper import generate as generate_real_piper

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get('RLHF_POC_DATA', '/state'))
DB = ROOT / 'jobs.sqlite3'
ENGINES = ('xtts', 'chatterbox', 'omnivoice', 'piper')
MAX_BATCH, MAX_ACTIVE, TTL = 100, 5, 86400
PUBLIC_BASE = os.environ.get('RLHF_PUBLIC_BASE_URL', '').rstrip('/')
OMNIVOICE_URL = os.environ.get('RLHF_OMNIVOICE_URL', '').rstrip('/')
XTTS_URL = os.environ.get('RLHF_XTTS_URL', '').rstrip('/')
CHATTERBOX_URL = os.environ.get('RLHF_CHATTERBOX_URL', '').rstrip('/')
PIPER_URL = os.environ.get('RLHF_PIPER_URL', '').rstrip('/')
POOL = ThreadPoolExecutor(max_workers=2)
LOCK = threading.RLock()
app = FastAPI(title='TTSCompare-RLHF TASK v0.3 laboratory', version='0.7.0')


def utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')


def db():
    c = sqlite3.connect(str(DB), timeout=20)
    c.row_factory = sqlite3.Row
    return c


def fail(code, message, http_status=422, retryable=False):
    raise HTTPException(
        http_status,
        detail={'code': code, 'message': message, 'retryable': retryable}
    )


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    detail = (
        exc.detail if isinstance(exc.detail, dict)
        else {'code': 'http_error', 'message': str(exc.detail), 'retryable': False}
    )
    return JSONResponse(status_code=exc.status_code, content={'error': detail})


@app.exception_handler(RequestValidationError)
async def request_error(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={'error': {
            'code': 'invalid_request',
            'message': 'Request schema validation failed',
            'retryable': False
        }}
    )


class Item(BaseModel):
    item_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)
    engine: str = Field(min_length=1, max_length=128)
    voice_id: str = Field(min_length=1, max_length=128)


class Batch(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    language: str = 'pl'
    audio_format: str = 'wav'
    archive_format: str = 'zip'
    items: list[Item] = Field(min_length=1, max_length=MAX_BATCH)




def process(jid):
    with LOCK:
        with db() as c:
            row = c.execute(
                'SELECT payload FROM jobs WHERE job_id=? AND status=?',
                (jid, 'queued')
            ).fetchone()
            if row is None:
                return

            c.execute(
                'UPDATE jobs SET status=?, started_at=?, '
                'processed=0, succeeded=0, failed=0 WHERE job_id=?',
                ('running', iso(utc()), jid)
            )
            payload = json.loads(row['payload'])

    records, files = [], {}

    try:
        for index, item in enumerate(payload['items'], 1):
            result = {
                'item_id': item['item_id'],
                'engine': item['engine'],
                'voice_id': item['voice_id'],
                'engine_version': 'REAL_UNAVAILABLE'
            }

            is_real_omni = (
                item['engine'] == 'omnivoice'
                and item['voice_id'] == 'Arek'
                and bool(OMNIVOICE_URL)
            )
            is_real_xtts = (
                item['engine'] == 'xtts'
                and item['voice_id'] == 'Arek'
                and bool(XTTS_URL)
            )
            is_real_chatterbox = (
                item['engine'] == 'chatterbox'
                and item['voice_id'] == 'Arek'
                and bool(CHATTERBOX_URL)
            )
            is_real_piper = (
                item['engine'] == 'piper'
                and item['voice_id'] == 'pl_PL-gosia-medium'
                and bool(PIPER_URL)
            )
            is_real = (
                is_real_omni
                or is_real_xtts
                or is_real_chatterbox
                or is_real_piper
            )
            result['real_tts_attempted'] = is_real
            result['real_tts'] = False
            result['engine_version'] = (
                'REAL_OMNIVOICE_0.3.0'
                if is_real_omni
                else (
                    'REAL_XTTS_v2'
                    if is_real_xtts
                    else (
                        'REAL_CHATTERBOX_MULTILINGUAL_v2_NOWM'
                        if is_real_chatterbox
                        else (
                            'REAL_PIPER_GOSIA_MEDIUM_CPU'
                            if is_real_piper
                            else 'REAL_UNAVAILABLE'
                        )
                    )
                )
            )
            real_audio = None
            real_metrics = None
            reason = None

            if is_real:
                try:
                    if is_real_omni:
                        real_audio, real_metrics = generate_real_omnivoice(
                            OMNIVOICE_URL, item['text']
                        )
                    elif is_real_xtts:
                        real_audio, real_metrics = generate_real_xtts(
                            XTTS_URL, item['text']
                        )
                    elif is_real_chatterbox:
                        real_audio, real_metrics = generate_real_chatterbox(
                            CHATTERBOX_URL, item['text']
                        )
                    else:
                        real_audio, real_metrics = generate_real_piper(
                            PIPER_URL, item['text']
                        )
                except Exception as exc:
                    reason = (
                        (
                            'real_omnivoice_error'
                            if is_real_omni
                            else (
                                'real_xtts_error'
                                if is_real_xtts
                                else (
                                    'real_chatterbox_error'
                                    if is_real_chatterbox
                                    else 'real_piper_error'
                                )
                            )
                        ),
                        f'{type(exc).__name__}: {str(exc)[:180]}',
                        True
                    )
            elif item['engine'] not in ENGINES:
                reason = ('invalid_engine', 'Unknown engine', False)
            elif item['voice_id'] != ('pl_PL-gosia-medium' if item['engine'] == 'piper' else 'Arek'):
                reason = ('invalid_voice', 'Voice not advertised for engine', False)
            else:
                reason = (
                    'engine_unavailable',
                    'Real engine is unavailable',
                    True,
                )

            if reason:
                code, message, retry = reason
                result.update(
                    status='failed',
                    file=None,
                    error={
                        'code': code,
                        'message': message,
                        'retryable': retry
                    }
                )
            else:
                name = f'audio/file-{index:06d}.wav'
                content = real_audio
                files[name] = content
                result.update(
                    status='success',
                    file=name,
                    real_tts=is_real,
                    generation_metrics=real_metrics if is_real else None,
                    bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    error=None
                )

            records.append(result)

            with db() as c:
                c.execute(
                    'UPDATE jobs SET processed=?, succeeded=?, '
                    'failed=? WHERE job_id=?',
                    (
                        len(records),
                        sum(x['status'] == 'success' for x in records),
                        sum(x['status'] == 'failed' for x in records),
                        jid
                    )
                )

        succeeded = sum(x['status'] == 'success' for x in records)
        failed = len(records) - succeeded
        final_status = (
            'completed' if failed == 0
            else (
                'completed_with_failures'
                if succeeded > 0 else 'failed'
            )
        )

        manifest = {
            'schema_version': '1',
            'producer_mode': (
                'REAL_ONLY'
                if any(x['real_tts_attempted'] for x in records)
                else 'REAL_ONLY'
            ),
            'real_tts_succeeded': sum(
                x['real_tts'] is True for x in records
            ),
            'job_id': jid,
            'request_id': payload['request_id'],
            'status': final_status,
            'items_total': len(records),
            'items_succeeded': succeeded,
            'items_failed': failed,
            'items': records
        }

        target = ROOT / 'archives' / f'{jid}.zip'
        tmp = ROOT / 'archives' / f'{jid}.zip.part'

        with zipfile.ZipFile(
            tmp, mode='w', compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(
                'manifest.json',
                json.dumps(manifest, ensure_ascii=False, indent=2)
            )
            for path, content in files.items():
                archive.writestr(path, content)

        tmp.replace(target)
        ready = utc()

        with db() as c:
            c.execute(
                '''UPDATE jobs SET
                   status=?, ready_at=?, expires_at=?,
                   archive_path=?, byte_size=?, sha256=?
                   WHERE job_id=?''',
                (
                    final_status,
                    iso(ready),
                    iso(ready + timedelta(seconds=TTL)),
                    str(target),
                    target.stat().st_size,
                    hashlib.sha256(target.read_bytes()).hexdigest(),
                    jid
                )
            )

    except Exception as exc:
        with db() as c:
            c.execute(
                'UPDATE jobs SET status=?, failure=? WHERE job_id=?',
                ('failed', type(exc).__name__, jid)
            )


@app.on_event('startup')
def startup():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'archives').mkdir(exist_ok=True)

    with db() as c:
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                processed INTEGER DEFAULT 0,
                succeeded INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                ready_at TEXT,
                expires_at TEXT,
                archive_path TEXT,
                byte_size INTEGER,
                sha256 TEXT,
                failure TEXT
            )
        ''')
        c.execute(
            "UPDATE jobs SET status='queued', processed=0, "
            "succeeded=0, failed=0 WHERE status='running'"
        )

        # Trwaly dziennik operacji bez zapisywania tekstow syntezy.
        c.execute("""CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            event TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            at_utc TEXT NOT NULL DEFAULT (
                strftime('%Y-%m-%dT%H:%M:%fZ','now')
            )
        )""")

        c.execute("""CREATE TRIGGER IF NOT EXISTS job_events_insert
            AFTER INSERT ON jobs
            BEGIN
                INSERT INTO job_events(job_id,event,to_status)
                VALUES(NEW.job_id,'created',NEW.status);
            END""")

        c.execute("""CREATE TRIGGER IF NOT EXISTS job_events_status
            AFTER UPDATE OF status ON jobs
            WHEN OLD.status <> NEW.status
            BEGIN
                INSERT INTO job_events(
                    job_id,event,from_status,to_status
                )
                VALUES(
                    NEW.job_id,'status_change',OLD.status,NEW.status
                );
            END""")
        queued = [
            r[0] for r in c.execute(
                "SELECT job_id FROM jobs WHERE status='queued'"
            )
        ]

    for jid in queued:
        POOL.submit(process, jid)


@app.get('/health')
def health():
    configured = {
        'omnivoice': OMNIVOICE_URL,
        'xtts': XTTS_URL,
        'chatterbox': CHATTERBOX_URL,
        'piper': PIPER_URL,
    }

    active = [key for key, value in configured.items() if value]

    return {
        'status': 'ok' if len(active) == 4 else 'degraded',
        'version': '0.7.0',
        'mode': 'REAL_ONLY',
        'configured_engines': active,
    }



@app.get('/v1/capabilities')
def capabilities():
    configured = [
        ('xtts', XTTS_URL, 'REAL_XTTS_v2', 'Arek'),
        (
            'chatterbox',
            CHATTERBOX_URL,
            'REAL_CHATTERBOX_MULTILINGUAL_v2_NOWM',
            'Arek',
        ),
        (
            'omnivoice',
            OMNIVOICE_URL,
            'REAL_OMNIVOICE_0.3.0',
            'Arek',
        ),
        (
            'piper',
            PIPER_URL,
            'REAL_PIPER_GOSIA_MEDIUM_CPU',
            'pl_PL-gosia-medium',
        ),
    ]

    engines = []

    for engine, endpoint, version, voice in configured:
        if not endpoint:
            continue

        engines.append({
            'id': engine,
            'version': version,
            'mode': 'real',
            'voices': [{
                'id': voice,
                'name': voice,
            }],
        })

    return {
        'api_version': '1',
        'languages': ['pl'],
        'audio_formats': ['wav'],
        'archive_formats': ['zip'],
        'max_batch_size': MAX_BATCH,
        'result_retention_seconds': TTL,
        'engines': engines,
    }



@app.post('/v1/jobs', status_code=202)
def submit(req: Batch):
    if (
        req.language,
        req.audio_format,
        req.archive_format
    ) != ('pl', 'wav', 'zip'):
        fail('unsupported_format', 'Only pl/wav/zip supported')

    real_omni_items = [
        item for item in req.items
        if item.engine == 'omnivoice' and item.voice_id == 'Arek'
    ]
    real_xtts_items = [
        item for item in req.items
        if item.engine == 'xtts' and item.voice_id == 'Arek'
    ]
    real_chatterbox_items = [
        item for item in req.items
        if item.engine == 'chatterbox' and item.voice_id == 'Arek'
    ]

    real_piper_items = [
        item for item in req.items
        if (
            item.engine == 'piper'
            and item.voice_id == 'pl_PL-gosia-medium'
        )
    ]

    real_items = (
        real_omni_items
        + real_xtts_items
        + real_chatterbox_items
        + real_piper_items
    )

    if real_omni_items and not OMNIVOICE_URL:
        fail('engine_unavailable', 'OmniVoice is unavailable')

    if real_xtts_items and not XTTS_URL:
        fail('engine_unavailable', 'XTTS is unavailable')

    if real_chatterbox_items and not CHATTERBOX_URL:
        fail('engine_unavailable', 'Chatterbox is unavailable')

    if real_piper_items and not PIPER_URL:
        fail('engine_unavailable', 'Piper is unavailable')

    if (
        len(real_omni_items) > 1
        or len(real_xtts_items) > 1
        or len(real_chatterbox_items) > 1
        or len(real_piper_items) > 1
        or any(len(item.text) > 280 for item in real_items)
    ):
        fail(
            'real_poc_limit',
            'Maximum one item per real engine, 280 chars each'
        )

    ids = [item.item_id for item in req.items]
    if len(set(ids)) != len(ids):
        fail('duplicate_item_id', 'item_id must be unique within a batch')

    obj = req.model_dump() if hasattr(req, 'model_dump') else req.dict()
    payload = json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')
    )
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    jid = 'job-' + uuid4().hex

    with LOCK:
        with db() as c:
            existing = c.execute(
                'SELECT job_id, fingerprint, status '
                'FROM jobs WHERE request_id=?',
                (req.request_id,)
            ).fetchone()

            if existing:
                if existing['fingerprint'] != fingerprint:
                    fail(
                        'request_id_conflict',
                        'Different payload with same request_id',
                        http_status=409
                    )
                return {
                    'job_id': existing['job_id'],
                    'status': existing['status']
                }

            if real_items:
                requested_engines = {
                    item.engine for item in real_items
                }

                active_payloads = c.execute(
                    "SELECT payload FROM jobs "
                    "WHERE status IN ('queued','running')"
                ).fetchall()

                for row in active_payloads:
                    active_items = json.loads(
                        row['payload']
                    )['items']

                    active_engines = {
                        item['engine']
                        for item in active_items
                        if (
                            item['engine'] in (
                                'omnivoice', 'xtts', 'chatterbox', 'piper'
                            )
                            and (
                                item['voice_id'] == 'Arek'
                                or (
                                    item['engine'] == 'piper'
                                    and item['voice_id'] == 'pl_PL-gosia-medium'
                                )
                            )
                        )
                    }

                    if requested_engines & active_engines:
                        fail(
                            'real_engine_busy',
                            'Requested real engine is busy',
                            http_status=429,
                            retryable=True
                        )

            active = c.execute(
                "SELECT COUNT(*) FROM jobs "
                "WHERE status IN ('queued','running')"
            ).fetchone()[0]

            if active >= MAX_ACTIVE:
                fail(
                    'queue_full',
                    'Too many active jobs',
                    http_status=429,
                    retryable=True
                )

            c.execute(
                'INSERT INTO jobs('
                'job_id,request_id,fingerprint,payload,status,created_at'
                ') VALUES(?,?,?,?,?,?)',
                (
                    jid, req.request_id, fingerprint,
                    payload, 'queued', iso(utc())
                )
            )

    POOL.submit(process, jid)
    return {'job_id': jid, 'status': 'queued'}


@app.get('/v1/jobs/{jid}')
def job_status(jid: str):
    with db() as c:
        row = c.execute(
            'SELECT * FROM jobs WHERE job_id=?', (jid,)
        ).fetchone()

    if not row:
        fail('unknown_job', 'Unknown job_id', http_status=404)

    return {
        'job_id': row['job_id'],
        'request_id': row['request_id'],
        'status': row['status'],
        'total_items': len(json.loads(row['payload'])['items']),
        'processed_items': row['processed'],
        'successful_items': row['succeeded'],
        'failed_items': row['failed'],
        'archive_url': (
            f'{PUBLIC_BASE}/v1/results/{jid}/archive'
            if row['archive_path'] else None
        ),
        'archive_format': 'zip' if row['archive_path'] else None,
        'byte_size': row['byte_size'],
        'sha256': row['sha256'],
        'created_at': row['created_at'],
        'ready_at': row['ready_at'],
        'expires_at': row['expires_at'],
        'failure': row['failure']
    }


@app.get('/v1/results/{jid}/archive')
def get_archive(jid: str):
    with db() as c:
        row = c.execute(
            'SELECT * FROM jobs WHERE job_id=?', (jid,)
        ).fetchone()

    if not row:
        fail('unknown_job', 'Unknown job_id', http_status=404)

    if row['expires_at'] and datetime.fromisoformat(
        row['expires_at'].replace('Z', '+00:00')
    ) <= utc():
        fail('archive_expired', 'Archive expired', http_status=410)

    if not row['archive_path']:
        fail(
            'archive_not_ready', 'Archive is not ready',
            http_status=409, retryable=True
        )

    path = Path(row['archive_path'])
    if not path.is_file():
        fail(
            'archive_missing', 'Archive is missing',
            http_status=500, retryable=True
        )

    return FileResponse(
        path,
        media_type='application/zip',
        filename=f'{jid}.zip'
    )

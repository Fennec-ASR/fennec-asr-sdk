# fennec-asr (Python SDK)

A small, friendly Python SDK for the Fennec ASR API. It supports:

- **Batch transcription (HTTP)** – upload a file or provide a URL, then poll until complete.
- **Realtime transcription (WebSocket)** – stream raw PCM audio bytes and receive partial/final results.
- **One-liner convenience** – `transcribe("sample.mp3")` using `FENNEC_API_KEY` from your environment.
- **CLI** – `fennec-asr <file-or-url>` prints the transcript.

> **API base:** `https://asr-api-hso0.onrender.com/api/v1` (configurable)

---

## Install

```bash
pip install fennec-asr
```

> Optional live-microphone helper (via `sounddevice`):
>
> ```bash
> pip install sounddevice numpy
> ```

---

## Quickstarts

### 1) One-liner (batch)

```python
from fennec_asr import transcribe

# FENNEC_API_KEY must be set in your env
print(transcribe("sample.mp3"))
```

Environment:

```bash
export FENNEC_API_KEY="sk_***"
# optional:
# export FENNEC_BASE_URL="https://your-deployment/api/v1"
```

### 2) Batch with options

```python
from fennec_asr import FennecASRClient

client = FennecASRClient(api_key="sk_***")

job_id = client.submit_url(
    "https://example.com/audio.mp3",
    context="Lightly punctuate. Keep acronyms uppercase.",
    apply_contextual_correction=False,
    formatting={"newline_pause_threshold": 0.65, "double_newline_pause_threshold": 0.7},
)

final = client.wait_for_completion(job_id, timeout_s=300)
if final["status"] == "completed":
    print(final["transcript"])
else:
    print("Failed:", final.get("transcript"))
```

### 3) Realtime (WebSocket)

```python
import asyncio
from fennec_asr import Realtime

async def main():
    rt = Realtime("sk_***").on("final", print).on("error", lambda e: print("ERR:", e))
    async with rt:
        # Send 16kHz, mono, 16-bit PCM bytes (no helper; bring your own frames)
        await rt.send_bytes(b"...")
        await rt.send_eos()
        async for _ in rt.messages():  # drain until server closes
            pass

asyncio.run(main())
```

> To receive only “complete thoughts”, construct with `Realtime("sk_***", detect_thoughts=True)`
> and subscribe to `.on("thought", ...)`.

### 4) CLI

```bash
fennec-asr sample.mp3
# or:
fennec-asr "https://example.com/audio.mp3"
# with options:
fennec-asr sample.mp3 --context "meeting notes" --apply-correction --formatting '{"newline_pause_threshold":0.65}'
```

---

## API

### `FennecASRClient(api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: int = 60)`

- `submit_file(path, context=None, apply_contextual_correction=False, formatting=None) -> job_id`
- `submit_url(audio_url, context=None, apply_contextual_correction=False, formatting=None) -> job_id`
- `get_status(job_id) -> dict`
- `wait_for_completion(job_id, poll_interval_s=3.0, timeout_s=300.0) -> dict`
- `transcribe_file(path, ...) -> str` (submit + wait)

### `Realtime(api_key: str, *, ws_url=..., sample_rate=16000, channels=1, detect_thoughts=False, ...)`

Event-driven WS client:

- Register events with `.on("partial"|"final"|"thought"|"open"|"close"|"error", callback)`
- `await open() / close()` (or use `async with`)
- `await send_bytes(chunk: bytes)` – raw **16kHz mono 16-bit PCM**
- `await send_eos()`
- `async for msg in messages(): ...` – raw JSON frames if you want lower-level access

Back-compat alias: `StreamingSession = Realtime`.

### Convenience

- `transcribe(source, *, context=None, apply_contextual_correction=False, formatting=None, timeout_s=300.0) -> str`
- `get_default_client()` – reads `FENNEC_API_KEY` / `FENNEC_BASE_URL` from env.

---

## Errors

Exceptions live in `fennec_asr.exceptions`:

- `AuthenticationError` – 401/403
- `NotFoundError` – 404
- `APIError` – other non-2xx or SDK-level errors
- `FennecASRError` – base class

The client surfaces server messages; future versions may include `request_id` and structured problem details if the server provides them.

---

## Notes & Expectations

- **Audio format (WS):** 16kHz, mono, 16-bit PCM (`int16`). Convert with `ffmpeg`:
  ```bash
  ffmpeg -y -i input.wav -ac 1 -ar 16000 -acodec pcm_s16le output.pcm
  ```
  Then read bytes from `output.pcm`.
- **Formatting options:** pass a dict; the SDK will JSON-encode when required.
- **Idempotency & retries:** basic happy-path covered; advanced policies can be added (see roadmap).

---

## Development

```bash
# setup
python -m venv .venv && source .venv/bin/activate
pip install -U pip build twine pytest

# run tests
pytest -q

# build & upload (needs PyPI creds)
python -m build
twine upload dist/*
```

---

## License

MIT © Fennec ASR

"""
Live microphone -> Realtime WebSocket helper (optional).

Quickstart
----------
pip install sounddevice numpy   # or add as optional deps
# then:

import asyncio
from fennec_asr import Realtime
from fennec_asr.mic import stream_microphone

async def main():
    rt = Realtime("YOUR_API_KEY").on("final", print).on("error", lambda e: print("ERR:", e))
    async with rt:
        await stream_microphone(rt)  # Ctrl+C to stop

asyncio.run(main())

Notes
-----
- Captures 16 kHz, mono, 16-bit PCM and forwards frames to the WebSocket.
- If you maintain extras, you can expose this as `pip install fennec-asr[mic]`.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .streaming import Realtime

try:
    import sounddevice as sd  # type: ignore
except Exception as _e:  # pragma: no cover
    sd = None
    _sd_import_err = _e
else:
    _sd_import_err = None


async def stream_microphone(
    rt: Realtime,
    *,
    samplerate: int = 16000,
    channels: int = 1,
    chunk_ms: int = 50,
    duration_s: Optional[float] = None,
    device: Optional[int | str] = None,
) -> None:
    """
    Start a live microphone stream and forward PCM frames to `rt.send_bytes()`.

    Parameters
    ----------
    rt : Realtime
        An opened Realtime client (use `async with Realtime(...) as rt:`).
    samplerate : int
        Sampling rate. Server expects 16000 Hz.
    channels : int
        Number of channels. Server expects mono (1).
    chunk_ms : int
        Frame size in milliseconds per audio chunk sent.
    duration_s : float | None
        Total capture duration. If None, runs until cancelled (Ctrl+C).
    device : int | str | None
        Optional sounddevice device index or name.

    Raises
    ------
    RuntimeError
        If `sounddevice` is not installed/available.
    """
    if sd is None:
        raise RuntimeError(
            "sounddevice not available. Install with: pip install sounddevice numpy"
        ) from _sd_import_err

    loop = asyncio.get_running_loop()
    q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=8)

    # frames per callback block
    blocksize = max(1, int(samplerate * (chunk_ms / 1000.0)))

    def _safe_put_nowait(queue: asyncio.Queue, data: bytes) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except Exception:
                pass
        queue.put_nowait(data)

    # sounddevice callback runs in a PortAudio thread
    def _cb(indata, frames, time_info, status):  # noqa: ANN001
        try:
            if status:
                # Optional: hook a logger here (drop glitches rather than raising)
                pass
            # With RawInputStream, `indata` is a bytes-like buffer; cast to bytes
            loop.call_soon_threadsafe(_safe_put_nowait, q, bytes(indata))
        except Exception:
            # Never propagate exceptions from audio callback
            pass

    stream = sd.RawInputStream(
        samplerate=samplerate,
        channels=channels,
        dtype="int16",
        blocksize=blocksize,
        callback=_cb,
        device=device,
    )

    start_t = loop.time()
    try:
        stream.start()
        while True:
            data = await q.get()
            await rt.send_bytes(data)
            if duration_s is not None and (loop.time() - start_t) >= duration_s:
                break
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        # Always signal end-of-stream so server can flush finals
        try:
            await rt.send_eos()
        except Exception:
            pass

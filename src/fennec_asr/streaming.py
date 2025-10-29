import asyncio
import json
from typing import Any, AsyncIterator, Callable, Dict, Optional
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

import requests
import websockets
from websockets import WebSocketClientProtocol

from .exceptions import APIError
from .client import DEFAULT_BASE_URL as _DEFAULT_HTTP_BASE
from .utils import env

DEFAULT_WS = "wss://api.fennec-asr.com/api/v1/transcribe/stream"
EventCallback = Callable[[Any], None]


class Realtime:
    """
    Event-driven WebSocket client for Fennec ASR.

    It now automatically fetches a short-lived streaming token from
    {HTTP_BASE}/transcribe/streaming-token and connects with ?token=...

    Subscribe with .on(event, callback):
      - "open":    () -> None
      - "partial": (text: str) -> None
      - "final":   (text: str) -> None
      - "thought": (text: str) -> None         # when detect_thoughts=True
      - "close":   () -> None
      - "error":   (exc_or_payload: Any) -> None

    Usage:
        import asyncio
        from fennec_asr.streaming import Realtime

        async def main():
            rt = (Realtime("YOUR_API_KEY")
                  .on("final", print)
                  .on("error", lambda e: print("ERR:", e)))
            async with rt:
                # send raw 16kHz mono 16-bit PCM chunks:
                await rt.send_bytes(b"...")
                await rt.send_eos()
                async for _ in rt.messages():  # drain until server closes
                    pass

        asyncio.run(main())
    """

    def __init__(
        self,
        api_key: str,
        *,
        ws_url: str = DEFAULT_WS,
        base_url: Optional[str] = None,
        token_endpoint: str = "/transcribe/streaming-token",
        force_token: bool = True,
        sample_rate: int = 16000,
        channels: int = 1,
        single_utterance: bool = False,
        vad: Optional[Dict[str, Any]] = None,
        detect_thoughts: bool = False,
        ping_interval: int = 20,
        ping_timeout: int = 30,
        queue_max: int = 128,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key  # may be used by the token endpoint if required
        self._ws_url = ws_url
        # HTTP base for token fetch; allow env override like the REST client
        self._http_base = (base_url or env("FENNEC_BASE_URL", _DEFAULT_HTTP_BASE) or _DEFAULT_HTTP_BASE).rstrip("/")
        self._token_endpoint = token_endpoint
        self._force_token = force_token

        self._detect_thoughts = detect_thoughts
        self._start_msg = {"type": "start", "sample_rate": sample_rate, "channels": channels}
        if single_utterance:
            self._start_msg["single_utterance"] = True
        if vad:
            self._start_msg["vad"] = vad
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout

        self._events: Dict[str, EventCallback] = {}
        self._ws: Optional[WebSocketClientProtocol] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._q: asyncio.Queue[dict] = asyncio.Queue(maxsize=queue_max)

    # ---------------- Token ----------------
    def _fetch_streaming_token_sync(self) -> str:
        """
        Synchronously fetches a short-lived token from:
          GET {HTTP_BASE}/transcribe/streaming-token
        Returns: token string.
        """
        url = f"{self._http_base}{self._token_endpoint}"
        headers = {"Accept": "application/json"}
        # Even if the endpoint is public, sending X-API-Key is harmless and keeps behavior consistent
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 405:  # method not allowed -> try POST if server enforces verb
            resp = requests.post(url, headers=headers, timeout=15)

        if not (200 <= resp.status_code < 300):
            raise APIError(f"Token fetch failed (HTTP {resp.status_code}): {resp.text}")
        try:
            token = resp.json().get("token")
        except Exception as e:
            raise APIError(f"Invalid token response: {e}") from e
        if not token:
            raise APIError("Missing 'token' in token response")
        return token

    def _with_query(self, base: str, extra: Dict[str, Any]) -> str:
        """Append/merge query params cleanly."""
        p = urlparse(base)
        existing = dict(parse_qsl(p.query, keep_blank_values=True))
        existing.update({k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in extra.items() if v is not None})
        new_q = urlencode(existing)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))

    # ---------------- Event API ----------------
    def on(self, event: str, callback: EventCallback) -> "Realtime":
        """Register a callback for an event; chainable."""
        self._events[event] = callback
        return self

    def off(self, event: str) -> "Realtime":
        """Unregister a callback; chainable."""
        self._events.pop(event, None)
        return self

    def _emit(self, event: str, payload: Any = None) -> None:
        cb = self._events.get(event)
        if not cb:
            return
        try:
            cb(payload) if payload is not None else cb()
        except Exception as e:  # never raise into user app from callbacks
            err = self._events.get("error")
            if err and event != "error":
                try:
                    err(e)
                except Exception:
                    pass

    # ---------------- Lifecycle ----------------
    async def open(self) -> None:
        """Open the WebSocket, perform the handshake, and start listening."""
        # Prefer short-lived token (more secure; avoids passing api_key in WS URL)
        url = self._ws_url
        if self._force_token:
            token = await asyncio.to_thread(self._fetch_streaming_token_sync)
            q = {"streaming_token": token, "detect_thoughts": True if self._detect_thoughts else None}
            url = self._with_query(url, q)
        else:
            # Legacy fallback (not recommended): put api_key in query
            q = {"api_key": self._api_key, "detect_thoughts": True if self._detect_thoughts else None}
            url = self._with_query(url, q)

        # 1. Connect to the server
        self._ws = await websockets.connect(
            url,
            max_size=None,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
        )

        try:
            # 2. Send the 'start' message to initiate the handshake
            await self._ws.send(json.dumps(self._start_msg))

            # 3. Wait for the server's 'ready' confirmation
            ready_message = await asyncio.wait_for(self._ws.recv(), timeout=10)
            ready_data = json.loads(ready_message)

            if ready_data.get("type") != "ready":
                await self._ws.close(code=1002, reason="protocol_error")
                raise APIError(f"Handshake failed: Server did not respond with 'ready'. Got: {ready_message}")

        except (asyncio.TimeoutError, websockets.ConnectionClosed, json.JSONDecodeError) as e:
            # Clean up and raise a specific error if the handshake fails
            if self._ws and not self._ws.closed:
                await self._ws.close()
            raise APIError(f"WebSocket handshake failed: {e}") from e

        # 4. Handshake complete! Start the background receive loop and emit 'open'
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._emit("open")

    async def close(self) -> None:
        """Close the WebSocket and stop background tasks."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except Exception:
                pass
            self._recv_task = None

        if self._ws and not self._ws.closed:
            try:
                await self._ws.close(code=1000, reason="client_done")
            finally:
                self._ws = None

        self._emit("close")

    async def __aenter__(self) -> "Realtime":
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ---------------- Send ----------------
    async def send_bytes(self, chunk: bytes) -> None:
        """Send raw audio bytes (16 kHz mono 16-bit PCM)."""
        if not self._ws:
            raise APIError("WebSocket not connected")
        await self._ws.send(chunk)

    async def send_text(self, text: str) -> None:
        """Send a text control frame (rarely needed)."""
        if not self._ws:
            raise APIError("WebSocket not connected")
        await self._ws.send(text)

    async def send_eos(self) -> None:
        """Signal end-of-stream to the server."""
        if not self._ws:
            raise APIError("WebSocket not connected")
        await self._ws.send('{"type":"eos"}')

    # ---------------- Receive ----------------
    async def messages(self) -> AsyncIterator[dict]:
        """
        Async iterator yielding raw JSON-decoded server messages.
        Ends when a sentinel 'closed' event is queued.
        """
        while True:
            msg = await self._q.get()
            if msg.get("_event") == "closed":
                break
            yield msg

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                # Server may send JSON strings
                try:
                    msg = json.loads(raw)
                except Exception:
                    # Non-JSON frames are ignored
                    continue

                # Special-case server error frames
                if isinstance(msg, dict) and msg.get("type") == "error":
                    self._emit("error", msg)
                    # Some servers then close the socket; we continue to push raw message to queue
                else:
                    # Pretty events
                    text = msg.get("text")
                    mtype = msg.get("type")
                    is_final = bool(msg.get("is_final"))

                    if self._detect_thoughts and mtype == "complete_thought" and text:
                        self._emit("thought", text)
                    elif text:
                        if is_final:
                            self._emit("final", text)
                        else:
                            self._emit("partial", text)

                # Always queue raw message for consumers
                try:
                    self._q.put_nowait(msg)
                except asyncio.QueueFull:
                    # Drop the oldest to keep latency low
                    try:
                        _ = self._q.get_nowait()
                        self._q.put_nowait(msg)
                    except Exception:
                        pass

        except Exception as e:
            self._emit("error", e)
        finally:
            await self._q.put({"_event": "closed"})


# Back-compat alias for older imports/export wiring
StreamingSession = Realtime

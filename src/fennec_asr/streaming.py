import asyncio
import json
from typing import Any, AsyncIterator, Callable, Dict, Optional

import websockets
from websockets import WebSocketClientProtocol

from .exceptions import APIError

DEFAULT_WS = "wss://asr-api-hso0.onrender.com/api/v1/transcribe/stream"
EventCallback = Callable[[Any], None]


class Realtime:
    """
    Event-driven WebSocket client for Fennec ASR.

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
        sample_rate: int = 16000,
        channels: int = 1,
        detect_thoughts: bool = False,
        ping_interval: int = 20,
        ping_timeout: int = 30,
        queue_max: int = 128,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._base_url = ws_url
        self._detect_thoughts = detect_thoughts
        self._start_msg = {"type": "start", "sample_rate": sample_rate, "channels": channels}
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout

        self._events: Dict[str, EventCallback] = {}
        self._ws: Optional[WebSocketClientProtocol] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._q: asyncio.Queue[dict] = asyncio.Queue(maxsize=queue_max)

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
        url = f"{self._base_url}?api_key={self._api_key}"
        if self._detect_thoughts:
            url += "&detect_thoughts=true"

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

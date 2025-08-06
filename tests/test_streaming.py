import asyncio
import json
import types

import pytest

from fennec_asr.streaming import Realtime


@pytest.mark.asyncio
async def test_requires_api_key():
    with pytest.raises(ValueError):
        Realtime("")


def test_event_api_is_chainable():
    called = {"final": False}

    def on_final(text: str):
        called["final"] = True

    rt = Realtime("key").on("final", on_final).off("final")
    assert isinstance(rt, Realtime)
    # ensure removing doesn't error
    rt.off("missing")


def test_emit_errors_are_captured():
    captured = {"err": None}

    def bad_cb(_):
        raise RuntimeError("boom")

    def on_error(e):
        captured["err"] = e

    rt = Realtime("key").on("partial", bad_cb).on("error", on_error)
    # call internal emit to simulate an incoming partial
    rt._emit("partial", "hello")  # type: ignore[attr-defined]
    assert isinstance(captured["err"], Exception)


@pytest.mark.asyncio
async def test_context_manager_open_close_without_network(monkeypatch):
    """
    We mock websockets.connect so no real network call happens.
    Ensures:
      - open() sends the start message
      - background recv loop exits cleanly
      - close() is called and 'closed' sentinel is queued
    """

    class FakeWS:
        def __init__(self):
            self.sent = []
            self.closed = False

        async def send(self, data):
            self.sent.append(data)

        async def close(self, code=1000, reason=""):
            self.closed = True

        # async iterator protocol used by `async for raw in self._ws:`
        def __aiter__(self):
            return self

        async def __anext__(self):
            # End immediately (no incoming frames)
            raise StopAsyncIteration

    fake_ws = FakeWS()

    async def fake_connect(*args, **kwargs):
        return fake_ws

    # Patch websockets.connect
    import fennec_asr.streaming as streaming_mod

    monkeypatch.setattr(streaming_mod.websockets, "connect", fake_connect)

    opened = []
    closed = []

    rt = (
        Realtime("key")
        .on("open", lambda: opened.append(True))
        .on("close", lambda: closed.append(True))
    )

    async with rt:
        # After open, the start message should be sent
        assert any(
            '"type": "start"' in msg if isinstance(msg, str) else False
            for msg in fake_ws.sent
        )
        # Drain messages iterator (should close immediately due to StopAsyncIteration)
        async for _ in rt.messages():
            pass

    # Context manager should have closed the socket
    assert fake_ws.closed is True
    assert opened and closed

import json
import types
from pathlib import Path

import pytest

from fennec_asr.client import FennecASRClient
from fennec_asr.exceptions import APIError, AuthenticationError, NotFoundError


def test_client_init_requires_key():
    with pytest.raises(ValueError):
        FennecASRClient(api_key="")


def test_submit_file_missing_path_raises(tmp_path: Path):
    c = FennecASRClient(api_key="key")
    missing = tmp_path / "nope.wav"
    with pytest.raises(FileNotFoundError):
        c.submit_file(missing)


def test_get_status_404_raises(monkeypatch):
    c = FennecASRClient(api_key="key")

    class R:
        status_code = 404
        text = "Not found"

        def json(self):
            return {"detail": "not found"}

    monkeypatch.setattr(c.session, "get", lambda *a, **k: R())

    with pytest.raises(NotFoundError):
        c.get_status("job-id")


def test_auth_errors_raise(monkeypatch):
    c = FennecASRClient(api_key="key")

    class R:
        status_code = 401
        text = "Unauthorized"

        def json(self):
            return {"detail": "invalid key"}

    monkeypatch.setattr(c.session, "get", lambda *a, **k: R())

    with pytest.raises(AuthenticationError):
        c.get_status("job-id")


def test_submit_url_success(monkeypatch):
    c = FennecASRClient(api_key="key")

    class R:
        status_code = 200

        def json(self):
            return {"job_id": "abc-123"}

    def fake_post(url, json=None, timeout=None):
        # ensure we sent the expected payload keys
        assert "audio" in json
        return R()

    monkeypatch.setattr(c.session, "post", fake_post)

    job_id = c.submit_url("https://example.com/a.mp3")
    assert job_id == "abc-123"


def test_submit_file_success(monkeypatch, tmp_path: Path):
    # create a small dummy file
    f = tmp_path / "a.bin"
    f.write_bytes(b"\x00\x01")

    c = FennecASRClient(api_key="key")

    class R:
        status_code = 200

        def json(self):
            return {"job_id": "job-1"}

    def fake_post(url, data=None, files=None, timeout=None):
        # basic assertions on multipart form
        assert "audio" in files
        return R()

    monkeypatch.setattr(c.session, "post", fake_post)

    job_id = c.submit_file(f)
    assert job_id == "job-1"


def test_wait_for_completion_transitions_to_completed(monkeypatch):
    c = FennecASRClient(api_key="key")

    # Simulate queued -> processing -> completed
    states = iter(
        [
            {"status": "queued"},
            {"status": "processing"},
            {"status": "completed", "transcript": "hello"},
        ]
    )

    monkeypatch.setattr(c, "get_status", lambda job_id: next(states))
    monkeypatch.setattr(c, "timeout", 1)  # not used but harmless

    # avoid real sleeping
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)

    final = c.wait_for_completion("job-1", poll_interval_s=0.0, timeout_s=5.0)
    assert final["status"] == "completed"
    assert final.get("transcript") == "hello"


def test_transcribe_file_failed_raises(monkeypatch, tmp_path: Path):
    c = FennecASRClient(api_key="key")

    # Simulate submitting and then a failed status
    monkeypatch.setattr(c, "submit_file", lambda *a, **k: "job-xyz")
    monkeypatch.setattr(
        c,
        "wait_for_completion",
        lambda *_a, **_k: {"status": "failed", "transcript": "bad audio"},
    )

    with pytest.raises(APIError) as ei:
        c.transcribe_file(tmp_path / "fake.wav")

    assert "bad audio" in str(ei.value)

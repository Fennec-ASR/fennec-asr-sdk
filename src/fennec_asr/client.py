import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .exceptions import APIError, AuthenticationError, NotFoundError
from .types import TranscriptionStatus

DEFAULT_BASE_URL = "https://asr-api-hso0.onrender.com/api/v1"

class FennecASRClient:
    """
    Thin client for Fennec ASR REST endpoints.
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: int = 60):
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
        self.timeout = timeout

    # ---------- Submit jobs ----------
    def submit_file(
        self,
        file_path: str | Path,
        *,
        context: Optional[str] = None,
        apply_contextual_correction: bool = False,
        formatting: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        POST /transcribe (multipart). Returns job_id.
        """
        url = f"{self.base_url}/transcribe"
        fp = Path(file_path)
        if not fp.exists():
            raise FileNotFoundError(fp)

        files = {"audio": (fp.name, fp.open("rb"), "application/octet-stream")}
        data: Dict[str, Any] = {}
        if context is not None:
            data["context"] = context
        data["apply_contextual_correction"] = str(bool(apply_contextual_correction)).lower()
        if formatting is not None:
            data["formatting"] = json.dumps(formatting)

        try:
            resp = self.session.post(url, data=data, files=files, timeout=self.timeout)
        finally:
            files["audio"][1].close()

        self._raise_for_status(resp)
        job_id = resp.json().get("job_id")
        if not job_id:
            raise APIError("Missing job_id in response")
        return job_id

    def submit_url(
        self,
        audio_url: str,
        *,
        context: Optional[str] = None,
        apply_contextual_correction: bool = False,
        formatting: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        POST /transcribe/url (JSON). Returns job_id.
        """
        url = f"{self.base_url}/transcribe/url"
        payload: Dict[str, Any] = {"audio": audio_url}
        if context is not None:
            payload["context"] = context
        payload["apply_contextual_correction"] = bool(apply_contextual_correction)
        if formatting is not None:
            payload["formatting"] = formatting  # server parses JSON string or object

        resp = self.session.post(url, json=payload, timeout=self.timeout)
        self._raise_for_status(resp)
        job_id = resp.json().get("job_id")
        if not job_id:
            raise APIError("Missing job_id in response")
        return job_id

    # ---------- Status ----------
    def get_status(self, job_id: str) -> TranscriptionStatus:
        """
        GET /transcribe/status/{job_id}
        """
        url = f"{self.base_url}/transcribe/status/{job_id}"
        resp = self.session.get(url, timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()  # Typed by TranscriptionStatus

    # ---------- Convenience ----------
    def wait_for_completion(
        self,
        job_id: str,
        *,
        poll_interval_s: float = 3.0,
        timeout_s: float = 300.0,
    ) -> TranscriptionStatus:
        """
        Polls until 'completed' or 'failed', or times out.
        """
        start = time.monotonic()
        while True:
            status = self.get_status(job_id)
            s = status.get("status")
            if s in {"completed", "failed"}:
                return status
            if time.monotonic() - start > timeout_s:
                raise APIError("Polling timed out")
            time.sleep(poll_interval_s)

    def transcribe_file(
        self,
        file_path: str | Path,
        *,
        context: Optional[str] = None,
        apply_contextual_correction: bool = False,
        formatting: Optional[Dict[str, Any]] = None,
        poll_interval_s: float = 3.0,
        timeout_s: float = 300.0,
    ) -> str:
        """
        Submit + wait. Returns final transcript string.
        """
        job_id = self.submit_file(
            file_path,
            context=context,
            apply_contextual_correction=apply_contextual_correction,
            formatting=formatting,
        )
        final = self.wait_for_completion(job_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s)
        if final.get("status") == "failed":
            raise APIError(final.get("transcript") or "Transcription failed")
        return final.get("transcript", "")

    def transcribe_url(
            self,
            audio_url: str,
            *,
            context: Optional[str] = None,
            apply_contextual_correction: bool = False,
            formatting: Optional[Dict[str, Any]] = None,
            poll_interval_s: float = 3.0,
            timeout_s: float = 300.0,
    ) -> str:
        job_id = self.submit_url(
            audio_url,
            context=context,
            apply_contextual_correction=apply_contextual_correction,
            formatting=formatting,
        )
        final = self.wait_for_completion(job_id, poll_interval_s=poll_interval_s, timeout_s=timeout_s)
        if final.get("status") == "failed":
            raise APIError(final.get("transcript") or "Transcription failed")
        return final.get("transcript", "")

    # ---------- Internal ----------
    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if 200 <= resp.status_code < 300:
            return
        if resp.status_code in (401, 403):
            raise AuthenticationError(f"Auth error ({resp.status_code}): {resp.text}")
        if resp.status_code == 404:
            raise NotFoundError("Resource not found")
        raise APIError(f"HTTP {resp.status_code}: {resp.text}")

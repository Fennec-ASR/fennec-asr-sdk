from pathlib import Path
from typing import Any, Dict, Optional, Union, IO

from .client import FennecASRClient, DEFAULT_BASE_URL
from .exceptions import APIError
from .utils import is_url, env

_default_client: Optional[FennecASRClient] = None


def get_default_client() -> FennecASRClient:
    global _default_client
    if _default_client is None:
        api_key = env("FENNEC_API_KEY")
        if not api_key:
            raise RuntimeError("Set FENNEC_API_KEY or pass api_key to FennecASRClient()")
        base_url = env("FENNEC_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
        _default_client = FennecASRClient(api_key=api_key, base_url=base_url)
    return _default_client


def transcribe(
        source: Union[str, Path, IO[bytes], bytes],
        *,
        context: Optional[str] = None,
        apply_contextual_correction: bool = False,
        formatting: Optional[Dict[str, Any]] = None,
        diarize: bool = False,
        speaker_recognition_context: Optional[str] = None,
        timeout_s: float = 300.0,
) -> str:
    """
    One-liner: returns final transcript for URL or local file path/bytes/IO.
    """
    c = get_default_client()
    common_kwargs = {
        "context": context,
        "apply_contextual_correction": apply_contextual_correction,
        "formatting": formatting,
        "diarize": diarize,
        "speaker_recognition_context": speaker_recognition_context,
    }

    job = None

    if isinstance(source, (str, Path)):
        p = Path(source)
        if isinstance(source, str) and is_url(source):
            job = c.submit_url(source, **common_kwargs)
        elif p.exists():
            job = c.submit_file(p, **common_kwargs)
        else:
            raise FileNotFoundError(f"{source}")
    elif isinstance(source, (bytes,)):
        # Write temp and use submit_file for simplicity (or add submit_bytes)
        import tempfile
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(source);
            tmp.flush()
            job = c.submit_file(tmp.name, **common_kwargs)

    # Handle IO[bytes] (file-like objects)
    elif hasattr(source, "read") and callable(getattr(source, "read")):
        data = source.read()
        if not isinstance(data, bytes):
            raise TypeError(f"Expected bytes from IO object, got {type(data)}")
        # Recurse with the bytes data
        return transcribe(data, **common_kwargs, timeout_s=timeout_s)

    else:
        raise TypeError("Unsupported source type. Use str (URL/path), Path, bytes, or IO[bytes].")

    # job might be None if we handled IO[bytes] (which recurses)
    if job:
        final = c.wait_for_completion(job, timeout_s=timeout_s)
        if final.get("status") != "completed":
            raise APIError(final.get("transcript") or "Transcription failed")
        return final.get("transcript", "")

    # Should be unreachable if logic above is sound
    raise RuntimeError("Internal error: Failed to process source.")
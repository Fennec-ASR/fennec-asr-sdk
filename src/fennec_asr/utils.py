import hashlib, json, os
from pathlib import Path
from typing import Any, Dict, Union, IO
from urllib.parse import urlparse

Source = Union[str, bytes, IO[bytes], Path]

def is_url(s: str) -> bool:
    try:
        sch = urlparse(s).scheme
        return sch in ("http", "https", "data")
    except Exception:
        return False

def coerce_formatting(fmt: Union[str, Dict[str, Any], None]) -> Union[str, None]:
    if fmt is None: return None
    if isinstance(fmt, str): return fmt
    return json.dumps(fmt)

def file_hash_for_idempotency(fp: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with fp.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)

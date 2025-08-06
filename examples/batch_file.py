"""
Simple batch transcription example (local file).

Setup:
  python -m venv .venv && source .venv/bin/activate
  pip install -e .
  export FENNEC_API_KEY="sk_***"

Run:
  python examples/batch_file.py /path/to/audio.mp3
"""

import sys
import os
from pathlib import Path

from fennec_asr import FennecASRClient


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/batch_file.py <audio-file>")
        sys.exit(2)

    api_key = os.getenv("FENNEC_API_KEY")
    if not api_key:
        raise RuntimeError("Set FENNEC_API_KEY in your environment.")

    path = Path(sys.argv[1]).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    client = FennecASRClient(api_key=api_key)
    print("Submitting job...")
    job_id = client.submit_file(path, formatting={"newline_pause_threshold": 0.65})
    print("Job ID:", job_id)

    print("Waiting for completion...")
    final = client.wait_for_completion(job_id, poll_interval_s=2.0, timeout_s=300.0)

    if final.get("status") == "completed":
        print("\n=== TRANSCRIPT ===\n")
        print(final.get("transcript", ""))
    else:
        print("Failed:", final.get("error_code") or final.get("transcript"))


if __name__ == "__main__":
    main()

"""
Simple batch transcription example (local file).

Setup:
  python -m venv .venv && source .venv/bin/activate
  pip install -e .
  export FENNEC_API_KEY="sk_***"

Run:
  python examples/batch_file.py /path/to/audio.mp3
  # With diarization:
  python examples/batch_file.py /path/to/audio.mp3 --diarize --speaker-context "John and Jane"
"""

import sys
import os
import argparse
from pathlib import Path

from fennec_asr import FennecASRClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch transcription example.")
    parser.add_argument("audio_file", help="Path to the audio file.")
    parser.add_argument("--diarize", action="store_true", help="Enable speaker diarization.")
    parser.add_argument("--speaker-context", help="Context for speaker recognition (requires --diarize).")
    args = parser.parse_args()

    api_key = os.getenv("FENNEC_API_KEY")
    if not api_key:
        raise RuntimeError("Set FENNEC_API_KEY in your environment.")

    path = Path(args.audio_file).expanduser()
    if not path.exists():
        raise FileNotFoundError(path)

    # Validation
    if args.speaker_context and not args.diarize:
        parser.error("--speaker-context requires --diarize.")

    client = FennecASRClient(api_key=api_key)
    print(f"Submitting job (Diarization: {'Yes' if args.diarize else 'No'})...")

    # Formatting options are ignored if diarization is enabled (and the SDK won't send them)
    formatting = {"newline_pause_threshold": 0.65} if not args.diarize else None

    try:
        job_id = client.submit_file(
            path,
            formatting=formatting,
            diarize=args.diarize,
            speaker_recognition_context=args.speaker_context
        )
        print("Job ID:", job_id)

        print("Waiting for completion...")
        final = client.wait_for_completion(job_id, poll_interval_s=2.0, timeout_s=300.0)

        if final.get("status") == "completed":
            print("\n=== TRANSCRIPT ===\n")
            # Transcript will include speaker labels if diarize=True
            print(final.get("transcript", ""))
        else:
            print("Failed:", final.get("error_code") or final.get("transcript"))
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
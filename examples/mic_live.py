"""
Live microphone -> Fennec ASR realtime example.

Setup:
  python -m venv .venv && source .venv/bin/activate
  pip install -e .[mic]    # installs sounddevice, numpy
  export FENNEC_API_KEY="sk_***"

Run:
  python examples/mic_live.py
"""

import asyncio
import os
from fennec_asr import Realtime
from fennec_asr.mic import stream_microphone


API_KEY = os.getenv("FENNEC_API_KEY")


async def main() -> None:
    if not API_KEY:
        raise RuntimeError("Set FENNEC_API_KEY in your environment.")

    # Print finals; show errors in console
    rt = (
        Realtime(API_KEY)
        .on("open", lambda: print("✅ connected"))
        .on("final", lambda t: print(f"📝 {t}"))
        .on("error", lambda e: print("❌ error:", e))
        .on("close", lambda: print("👋 closed"))
    )

    async with rt:
        # Stream from mic until Ctrl+C
        await stream_microphone(rt, samplerate=16000, channels=1, chunk_ms=50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")

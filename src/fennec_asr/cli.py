import argparse, sys, json, os
from .shortcuts import transcribe

def main():
    p = argparse.ArgumentParser(description="Transcribe audio using Fennec ASR.")
    p.add_argument("source", help="file path or URL")
    p.add_argument("--context", help="Context for the transcription.")
    p.add_argument("--formatting", help='JSON string, e.g. {"newline_pause_threshold":0.65}. Ignored if --diarize is used.')
    p.add_argument("--apply-correction", action="store_true", help="Apply AI contextual correction.")

    # Diarization options
    p.add_argument("--diarize", action="store_true", help="Enable speaker diarization.")
    p.add_argument("--speaker-context", dest="speaker_recognition_context", help="Context for AI speaker name replacement (requires --diarize).")

    args = p.parse_args()

    # Validation
    if args.speaker_recognition_context and not args.diarize:
        p.error("--speaker-context requires --diarize.")

    fmt = None
    if args.formatting:
        try:
            fmt = json.loads(args.formatting)
        except json.JSONDecodeError as e:
            p.error(f"Invalid JSON format for --formatting: {e}")

    if args.diarize and args.formatting:
        print("Warning: --formatting options are ignored when --diarize is enabled.", file=sys.stderr)

    try:
        text = transcribe(
            args.source,
            context=args.context,
            apply_contextual_correction=args.apply_correction,
            formatting=fmt,
            diarize=args.diarize,
            speaker_recognition_context=args.speaker_recognition_context,
        )
        print(text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
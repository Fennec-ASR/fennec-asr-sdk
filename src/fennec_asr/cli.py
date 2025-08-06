import argparse, sys, json, os
from .shortcuts import transcribe

def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", help="file path or URL")
    p.add_argument("--context")
    p.add_argument("--formatting", help='JSON string, e.g. {"newline_pause_threshold":0.65}')
    p.add_argument("--apply-correction", action="store_true")
    args = p.parse_args()

    fmt = None
    if args.formatting:
        fmt = json.loads(args.formatting)

    try:
        text = transcribe(
            args.source,
            context=args.context,
            apply_contextual_correction=args.apply_correction,
            formatting=fmt,
        )
        print(text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

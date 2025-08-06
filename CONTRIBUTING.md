# Contributing to `fennec-asr`

This repo is a small SDK that wraps the Fennec ASR API. Please keep changes minimal and developer-friendly.

## Getting Started

```bash
git clone https://github.com/Fennec-ASR/fennec-asr-sdk.git
cd fennec-asr-sdk
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .[mic]        # optional mic extra (sounddevice, numpy)
pip install -U pytest
```

Run tests:

```bash
pytest -q
```

## Philosophy

- **Thin by default.** Avoid heavy dependencies, global state, or complex abstractions.
- **Predictable errors.** Raise typed exceptions from `fennec_asr.exceptions`.
- **Non-breaking changes first.** Keep API surface stable; prefer additive changes.
- **Doc-first.** Update README/examples when you add features.

## Code Style

- Python ≥ 3.9.
- Type hints everywhere (`py.typed` is shipped).
- Keep modules small and single-purpose.
- Avoid side effects at import time.

## Structure

```
src/fennec_asr/
  client.py        # HTTP client (batch)
  streaming.py     # Realtime WS client
  mic.py           # Optional mic helper (sounddevice)
  shortcuts.py     # One-liners (transcribe, default client)
  exceptions.py    # Typed errors
  types.py         # TypedDicts / Literals
  utils.py
tests/
  test_client.py
  test_streaming.py
examples/
  batch_file.py
  mic_live.py
```

## Adding Dependencies

- Keep the default install light.
- Put optional stuff under `[project.optional-dependencies]`.
- For dev-only tools, prefer a separate `dev`/`test` extra if needed.

## Commit & PR Guidelines

- One logical change per PR.
- Include tests for new behavior.
- Update README/examples if the public API changes.
- Describe any user-visible change in the PR body.

## Versioning & Releases

- Bump `src/fennec_asr/_version.py`.
- Tag release in Git and publish to PyPI.
- CI builds wheels/sdists automatically.

## Security

- Don’t log API keys.
- Never hardcode secrets.
- If you discover a vulnerability, please see `SECURITY.md`.

## License

By contributing, you agree that your contributions are licensed under the MIT License included in this repository.

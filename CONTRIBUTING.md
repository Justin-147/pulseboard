# Contributing to PulseBoard

Thanks for helping improve PulseBoard.

## Before opening an issue

- Search existing issues first.
- For bugs, include the Windows version, GPU model, PulseBoard version, and steps to reproduce.
- Remove computer names, account details, process lists, and Codex session content from screenshots or logs.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m pulseboard.desktop
```

## Pull requests

- Keep each pull request focused on one change.
- Add or update tests when behavior changes.
- Preserve the compact, native, privacy-first design.
- Do not add telemetry, cloud storage, or a browser requirement.
- Confirm that all tests pass before submitting.

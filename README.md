# PulseBoard

[简体中文](README.zh-CN.md) · English

[![Release](https://img.shields.io/github/v/release/Justin-147/pulseboard?style=flat-square)](https://github.com/Justin-147/pulseboard/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Justin-147/pulseboard/total?style=flat-square)](https://github.com/Justin-147/pulseboard/releases)
[![Tests](https://img.shields.io/github/actions/workflow/status/Justin-147/pulseboard/test.yml?branch=main&style=flat-square&label=tests)](https://github.com/Justin-147/pulseboard/actions/workflows/test.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4?style=flat-square)](#requirements)
[![License](https://img.shields.io/github/license/Justin-147/pulseboard?style=flat-square)](LICENSE)

**A compact, privacy-first native Windows dashboard for CPU, GPU, memory, disk, network, top processes, and Codex usage — all in one window.**

[Download for Windows](https://github.com/Justin-147/pulseboard/releases/latest) · [Report a bug](https://github.com/Justin-147/pulseboard/issues/new?template=bug_report.yml) · [Request a feature](https://github.com/Justin-147/pulseboard/issues/new?template=feature_request.yml)

![PulseBoard interface preview with sample data](assets/pulseboard-preview.svg)

> The preview uses sample values. PulseBoard processes live metrics locally and never uploads them.

## Why PulseBoard?

- **One compact native window:** no browser, local web server, account, or scrolling.
- **Useful at a glance:** four gauges, a 60-second trend, live throughput, and top-five CPU/memory programs.
- **Codex-aware:** shows quota, reset time, token totals, and the current task's context usage.
- **Windows-friendly:** portable standalone executable, optional login startup, and single-instance behavior.
- **Privacy-first:** metrics stay in memory on your computer; no telemetry and no history database.

## Quick start

1. Download and extract the latest [Windows release](https://github.com/Justin-147/pulseboard/releases/latest).
2. Double-click `PulseBoard.exe`.
3. Optional: double-click `Install-Autostart.bat` to open PulseBoard automatically after Windows login.

The release is self-contained: Python and a browser are **not** required.

## Autostart behavior

PulseBoard **does not enable autostart by default**. Running `PulseBoard.exe` never changes your Windows startup settings.

- Run `Install-Autostart.bat` only when you want PulseBoard to open after Windows login.
- Run `Uninstall-Autostart.bat` to disable it again. This does not remove PulseBoard or your files.
- Autostart is configured for the current Windows user and does not require administrator privileges.

## Features

| Area | What you get |
| --- | --- |
| System | CPU, GPU, memory, and system-drive gauges |
| Trends | CPU, GPU, and memory history for the latest 60 seconds |
| Throughput | Network upload/download and disk read/write rates |
| Programs | Top five CPU and memory consumers, grouped by executable name |
| NVIDIA GPU | Utilization, VRAM, and temperature through `nvidia-smi` |
| Other GPUs | Best-effort utilization through Windows performance counters |
| Codex | Plan/quota window, reset time, daily/lifetime tokens, and task context |
| Desktop | Resizable 920 × 640 default window, optional autostart, and single-instance focus |

## Requirements

- Windows 10 or Windows 11 (x64 release build).
- Codex Desktop/CLI is optional; system monitoring continues when Codex data is unavailable.

## Codex data compatibility

PulseBoard starts a hidden local Codex app-server process and reads local Codex Desktop activity/session files in read-only mode. It does not modify Codex data and does not depend on the older `codex-usage-hud` project.

These are local implementation interfaces rather than a stable public API. A future Codex update may require a matching PulseBoard update.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m pulseboard.desktop
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

[MIT](LICENSE)

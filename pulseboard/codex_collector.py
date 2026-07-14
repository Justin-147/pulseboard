from __future__ import annotations

import copy
import json
import os
import queue
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _read_tail(path: Path, max_bytes: int = 4 * 1024 * 1024) -> str:
    size = path.stat().st_size
    length = min(size, max_bytes)
    with path.open("rb") as handle:
        handle.seek(max(0, size - length))
        return handle.read(length).decode("utf-8", errors="replace")


def _token_breakdown(value: dict[str, Any] | None) -> dict[str, int] | None:
    if not value:
        return None
    return {
        "total_tokens": int(value.get("total_tokens") or 0),
        "input_tokens": int(value.get("input_tokens") or 0),
        "cached_input_tokens": int(value.get("cached_input_tokens") or 0),
        "output_tokens": int(value.get("output_tokens") or 0),
        "reasoning_output_tokens": int(value.get("reasoning_output_tokens") or 0),
    }


def parse_rollout_token_usage(thread: dict[str, Any] | None) -> dict[str, Any] | None:
    if not thread or not thread.get("path"):
        return None
    path = Path(str(thread["path"]))
    if not path.is_file():
        return None
    try:
        lines = _read_tail(path).splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        if '"token_count"' not in raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") or {}
        if event.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        total = _token_breakdown(info.get("total_token_usage"))
        last = _token_breakdown(info.get("last_token_usage"))
        if not total or not last:
            continue
        return {
            "total": total,
            "last": last,
            "model_context_window": int(info.get("model_context_window") or 0) or None,
            "updated_at": event.get("timestamp"),
        }
    return None


def parse_usage_snapshot(
    account: dict[str, Any] | None,
    rate_limits: dict[str, Any] | None,
    usage: dict[str, Any] | None,
    thread: dict[str, Any] | None,
    thread_usage: dict[str, Any] | None,
) -> dict[str, Any]:
    account_data = (account or {}).get("account") or {}
    limits_root = rate_limits or {}
    by_id = limits_root.get("rateLimitsByLimitId") or {}
    main = by_id.get("codex") or limits_root.get("rateLimits") or {}
    primary = main.get("primary") or {}
    buckets = (usage or {}).get("dailyUsageBuckets") or []
    latest = buckets[-1] if buckets else {}
    summary = (usage or {}).get("summary") or {}
    last = (thread_usage or {}).get("last") or {}
    context_window = (thread_usage or {}).get("model_context_window")
    last_tokens = last.get("total_tokens")
    context_percent = None
    if last_tokens is not None and context_window:
        context_percent = min(100.0, float(last_tokens) / float(context_window) * 100)
    duration = int(primary.get("windowDurationMins") or 0)
    return {
        "connected": True,
        "plan": account_data.get("planType") or main.get("planType"),
        "quota": {
            "used_percent": primary.get("usedPercent"),
            "window_minutes": duration,
            "resets_at": primary.get("resetsAt"),
        },
        "tokens": {
            "latest_date": latest.get("startDate"),
            "latest_daily": latest.get("tokens"),
            "lifetime": summary.get("lifetimeTokens"),
        },
        "context": {
            "used_percent": context_percent,
            "last_tokens": last_tokens,
            "window_tokens": context_window,
            "total_tokens": ((thread_usage or {}).get("total") or {}).get("total_tokens"),
            "thread_name": (thread or {}).get("name") or (thread or {}).get("preview"),
        },
    }


class CodexCollector:
    """Read Codex quota and local thread context through the local app-server."""

    def __init__(self, poll_seconds: float = 15.0) -> None:
        self.poll_seconds = poll_seconds
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._next_id = 1
        self._process: subprocess.Popen[str] | None = None
        self._running = True
        self._state: dict[str, Any] = {
            "connected": False,
            "plan": None,
            "quota": {"used_percent": None, "window_minutes": 0, "resets_at": None},
            "tokens": {"latest_date": None, "latest_daily": None, "lifetime": None},
            "context": {
                "used_percent": None,
                "last_tokens": None,
                "window_tokens": None,
                "total_tokens": None,
                "thread_name": None,
            },
            "updated_at": None,
            "error": None,
        }
        threading.Thread(target=self._run, name="pulseboard-codex", daemon=True).start()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def close(self) -> None:
        self._running = False
        process = self._process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass

    @staticmethod
    def _find_codex_exe() -> str:
        explicit = os.environ.get("CODEX_EXE")
        if explicit and Path(explicit).is_file():
            return explicit
        root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        candidates: list[Path] = []
        try:
            candidates = [path for path in root.glob("*/codex.exe") if path.is_file()]
        except OSError:
            pass
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))
        return "codex.exe"

    @staticmethod
    def _desktop_log_root() -> Path:
        packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
        try:
            for package in packages.iterdir():
                if package.is_dir() and package.name.lower().startswith("openai.codex_"):
                    candidate = package / "LocalCache" / "Local" / "Codex" / "Logs"
                    if candidate.is_dir():
                        return candidate
        except OSError:
            pass
        return packages / "OpenAI.Codex_2p2nqsd0c76g0" / "LocalCache" / "Local" / "Codex" / "Logs"

    def _focused_thread_id(self) -> str | None:
        root = self._desktop_log_root()
        if not root.is_dir():
            return None
        try:
            files = sorted(root.rglob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)[:24]
        except OSError:
            return None
        active_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}T\S+).*thread_stream_view_activity_changed active=true "
            r"conversationId=([0-9a-f-]{36}).*rendererWindowVisible=true"
        )
        owner_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}T\S+).*ownerRoutePath=/local/([0-9a-f-]{36})"
        )
        best: tuple[float, str] | None = None
        for path in files:
            try:
                lines = _read_tail(path, 1024 * 1024).splitlines()
            except OSError:
                continue
            for line in lines:
                match = active_pattern.search(line) or owner_pattern.search(line)
                if not match:
                    continue
                try:
                    timestamp = datetime.fromisoformat(match.group(1).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
                if not best or timestamp > best[0]:
                    best = (timestamp, match.group(2))
        return best[1] if best else None

    def _send(self, method: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            raise RuntimeError("Codex app-server is not running")
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._write_lock:
            request_id = self._next_id
            self._next_id += 1
            self._pending[request_id] = response_queue
            payload = json.dumps({"method": method, "id": request_id, "params": params}, separators=(",", ":"))
            process.stdin.write(payload + "\n")
            process.stdin.flush()
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"{method} timed out") from exc
        if response.get("error"):
            raise RuntimeError(f"{method}: {response['error']}")
        return response.get("result")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        process = self._process
        if not process or not process.stdin:
            return
        with self._write_lock:
            process.stdin.write(json.dumps({"method": method, "params": params}, separators=(",", ":")) + "\n")
            process.stdin.flush()

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            if not self._running:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = message.get("id")
            if request_id is not None:
                target = self._pending.pop(int(request_id), None)
                if target:
                    target.put(message)

    def _select_thread(self, threads: dict[str, Any] | None) -> dict[str, Any] | None:
        data = (threads or {}).get("data") or []
        focused_id = self._focused_thread_id()
        selected = next((thread for thread in data if thread.get("id") == focused_id), None)
        if not selected and focused_id:
            try:
                result = self._send("thread/read", {"threadId": focused_id, "includeTurns": False})
                selected = (result or {}).get("thread")
            except (RuntimeError, TimeoutError):
                selected = None
        return selected or (data[0] if data else None)

    def _poll(self) -> None:
        account = self._send("account/read", {"refreshToken": False})
        rate_limits = self._send("account/rateLimits/read")
        usage = self._send("account/usage/read")
        threads = self._send(
            "thread/list",
            {"limit": 10, "sortKey": "updated_at", "sortDirection": "desc", "useStateDbOnly": True},
        )
        selected = self._select_thread(threads)
        thread_usage = parse_rollout_token_usage(selected)
        state = parse_usage_snapshot(account, rate_limits, usage, selected, thread_usage)
        state["updated_at"] = time.time()
        state["error"] = None
        with self._lock:
            self._state = state

    def _set_error(self, error: Exception) -> None:
        with self._lock:
            self._state["connected"] = False
            self._state["error"] = str(error)[:240]
            self._state["updated_at"] = time.time()

    def _run(self) -> None:
        while self._running:
            try:
                self._process = subprocess.Popen(
                    [self._find_codex_exe(), "app-server", "--stdio"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=CREATE_NO_WINDOW,
                )
                threading.Thread(target=self._read_stdout, name="pulseboard-codex-reader", daemon=True).start()
                self._send(
                    "initialize",
                    {
                        "clientInfo": {"name": "pulseboard", "title": "PulseBoard", "version": "1.2.0"},
                        "capabilities": {"experimentalApi": True, "requestAttestation": False},
                    },
                )
                self._notify("initialized")
                while self._running and self._process.poll() is None:
                    started = time.monotonic()
                    self._poll()
                    delay = max(0.5, self.poll_seconds - (time.monotonic() - started))
                    for _ in range(max(1, int(delay * 2))):
                        if not self._running:
                            break
                        time.sleep(0.5)
            except (OSError, RuntimeError, TimeoutError) as error:
                self._set_error(error)
            finally:
                process = self._process
                if process and process.poll() is None:
                    try:
                        process.terminate()
                    except OSError:
                        pass
                self._process = None
            if self._running:
                time.sleep(5)

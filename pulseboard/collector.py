from __future__ import annotations

import csv
import io
import os
import platform
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import psutil


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _round(value: float | int | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


@dataclass
class RateSample:
    at: float
    read: int
    write: int


class SystemCollector:
    """Collect local machine metrics while keeping sampling state between calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        now = time.monotonic()
        disk = psutil.disk_io_counters()
        net = psutil.net_io_counters()
        self._disk = RateSample(now, disk.read_bytes if disk else 0, disk.write_bytes if disk else 0)
        self._net = RateSample(now, net.bytes_recv if net else 0, net.bytes_sent if net else 0)
        self._gpu_cache: dict[str, Any] = {
            "available": False,
            "name": "GPU 正在采样",
            "percent": None,
            "memory_percent": None,
            "memory_used": None,
            "memory_total": None,
            "temperature_c": None,
            "source": "sampling",
        }
        self._program_cache: tuple[list[dict[str, Any]], list[dict[str, Any]], int] = ([], [], 0)
        self._process_times: dict[int, tuple[float, float]] = {}
        psutil.cpu_percent(interval=None, percpu=True)
        threading.Thread(target=self._gpu_loop, name="pulseboard-gpu", daemon=True).start()
        threading.Thread(target=self._program_loop, name="pulseboard-programs", daemon=True).start()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            cpu_each = psutil.cpu_percent(interval=None, percpu=True)
            cpu = sum(cpu_each) / len(cpu_each) if cpu_each else psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            root = os.environ.get("SystemDrive", "C:") + "\\"
            disk_usage = psutil.disk_usage(root)
            disk_rate = self._disk_rates(now)
            net_rate = self._net_rates(now)
            gpu = self._gpu_cache
            top_cpu, top_memory, process_count = self._program_cache
            freq = psutil.cpu_freq()
            boot = psutil.boot_time()

            return {
                "timestamp": int(time.time() * 1000),
                "host": {
                    "name": platform.node() or "Windows PC",
                    "os": f"{platform.system()} {platform.release()}",
                    "uptime_seconds": max(0, int(time.time() - boot)),
                },
                "cpu": {
                    "percent": _round(cpu),
                    "per_core": [_round(value) for value in cpu_each],
                    "logical_cores": psutil.cpu_count(logical=True),
                    "physical_cores": psutil.cpu_count(logical=False),
                    "frequency_mhz": _round(freq.current, 0) if freq else None,
                },
                "memory": {
                    "percent": _round(memory.percent),
                    "used": memory.used,
                    "available": memory.available,
                    "total": memory.total,
                    "swap_percent": _round(swap.percent),
                },
                "gpu": gpu,
                "disk": {
                    "percent": _round(disk_usage.percent),
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "total": disk_usage.total,
                    **disk_rate,
                },
                "network": net_rate,
                "processes": {
                    "count": process_count,
                    "top_cpu": top_cpu,
                    "top_memory": top_memory,
                },
            }

    def _disk_rates(self, now: float) -> dict[str, float]:
        counters = psutil.disk_io_counters()
        if not counters:
            return {"read_bps": 0.0, "write_bps": 0.0}
        elapsed = max(now - self._disk.at, 0.001)
        result = {
            "read_bps": max(0.0, (counters.read_bytes - self._disk.read) / elapsed),
            "write_bps": max(0.0, (counters.write_bytes - self._disk.write) / elapsed),
        }
        self._disk = RateSample(now, counters.read_bytes, counters.write_bytes)
        return result

    def _net_rates(self, now: float) -> dict[str, float]:
        counters = psutil.net_io_counters()
        if not counters:
            return {"download_bps": 0.0, "upload_bps": 0.0}
        elapsed = max(now - self._net.at, 0.001)
        result = {
            "download_bps": max(0.0, (counters.bytes_recv - self._net.read) / elapsed),
            "upload_bps": max(0.0, (counters.bytes_sent - self._net.write) / elapsed),
        }
        self._net = RateSample(now, counters.bytes_recv, counters.bytes_sent)
        return result

    def _programs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        sampled_at = time.monotonic()
        logical_cores = max(psutil.cpu_count(logical=True) or 1, 1)
        next_process_times: dict[int, tuple[float, float]] = {}
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"cpu_percent": 0.0, "memory_bytes": 0, "instances": 0, "pids": []}
        )
        count = 0
        for process in psutil.process_iter(["pid", "name", "memory_info", "cpu_times"]):
            try:
                name = (process.info.get("name") or f"PID {process.pid}").strip()
                if process.pid == 0 or name.lower() == "system idle process":
                    continue
                stats = grouped[name]
                cpu_times = process.info.get("cpu_times")
                cpu_total = (cpu_times.user + cpu_times.system) if cpu_times else 0.0
                previous = self._process_times.get(process.pid)
                if previous:
                    elapsed = max(sampled_at - previous[0], 0.001)
                    stats["cpu_percent"] += max(0.0, cpu_total - previous[1]) / elapsed * 100 / logical_cores
                next_process_times[process.pid] = (sampled_at, cpu_total)
                memory_info = process.info.get("memory_info")
                stats["memory_bytes"] += memory_info.rss if memory_info else 0
                stats["instances"] += 1
                if len(stats["pids"]) < 3:
                    stats["pids"].append(process.pid)
                count += 1
            except (psutil.Error, OSError, ValueError):
                continue

        self._process_times = next_process_times

        rows = [
            {
                "name": name,
                "cpu_percent": _round(_clamp(values["cpu_percent"])),
                "memory_bytes": values["memory_bytes"],
                "instances": values["instances"],
                "pids": values["pids"],
            }
            for name, values in grouped.items()
        ]
        top_cpu = sorted(rows, key=lambda item: item["cpu_percent"], reverse=True)[:5]
        top_memory = sorted(rows, key=lambda item: item["memory_bytes"], reverse=True)[:5]
        return top_cpu, top_memory, count

    def _gpu_loop(self) -> None:
        while True:
            self._gpu_cache = self._nvidia_gpu() or self._windows_gpu() or {
                "available": False,
                "name": "未检测到可读取的 GPU",
                "percent": None,
                "memory_percent": None,
                "memory_used": None,
                "memory_total": None,
                "temperature_c": None,
                "source": "unavailable",
            }
            time.sleep(5)

    def _program_loop(self) -> None:
        while True:
            self._program_cache = self._programs()
            time.sleep(2)

    @staticmethod
    def _nvidia_gpu() -> dict[str, Any] | None:
        executable = shutil.which("nvidia-smi")
        if not executable:
            return None
        query = "name,utilization.gpu,memory.used,memory.total,temperature.gpu"
        try:
            completed = subprocess.run(
                [executable, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=True,
            )
            rows = list(csv.reader(io.StringIO(completed.stdout)))
            if not rows:
                return None
            name, use, mem_used, mem_total, temp = [value.strip() for value in rows[0][:5]]
            used_bytes = float(mem_used) * 1024 * 1024
            total_bytes = float(mem_total) * 1024 * 1024
            return {
                "available": True,
                "name": name,
                "percent": _round(_clamp(float(use))),
                "memory_percent": _round(100 * used_bytes / total_bytes) if total_bytes else None,
                "memory_used": int(used_bytes),
                "memory_total": int(total_bytes),
                "temperature_c": _round(float(temp)),
                "source": "nvidia-smi",
            }
        except (subprocess.SubprocessError, OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _windows_gpu() -> dict[str, Any] | None:
        if platform.system() != "Windows":
            return None
        script = (
            "$ProgressPreference='SilentlyContinue';"
            "$name=(Get-CimInstance Win32_VideoController | Where-Object {$_.Name -notmatch 'Remote|Basic'} | "
            "Select-Object -First 1 -ExpandProperty Name);"
            "$v=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | "
            "Measure-Object CookedValue -Sum | Select-Object -ExpandProperty Sum;"
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
            "Write-Output ($name); Write-Output ($v)"
        )
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            if not lines:
                return None
            try:
                percent = _round(_clamp(float(lines[-1].replace(",", "."))))
                name = " ".join(lines[:-1]) or "Windows GPU"
            except ValueError:
                percent, name = None, " ".join(lines)
            return {
                "available": True,
                "name": name,
                "percent": percent,
                "memory_percent": None,
                "memory_used": None,
                "memory_total": None,
                "temperature_c": None,
                "source": "windows-performance-counter",
            }
        except (subprocess.SubprocessError, OSError):
            return None

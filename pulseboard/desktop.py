from __future__ import annotations

import ctypes
import math
import platform
import queue
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import font as tkfont
from typing import Any

from .collector import SystemCollector


BG = "#080b0e"
PANEL = "#10151a"
PANEL_ALT = "#0c1115"
LINE = "#20292e"
TEXT = "#eef4f1"
MUTED = "#788783"
CYAN = "#59e1d0"
VIOLET = "#a58cff"
LIME = "#b6ef5b"
ORANGE = "#ffad5c"
RED = "#ff6b68"
WINDOW_TITLE = "PulseBoard · 系统脉搏"


def format_bytes(value: float | int | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while abs(number) >= 1024 and index < len(units) - 1:
        number /= 1024
        index += 1
    digits = 0 if number >= 100 else 1
    return f"{number:.{digits}f} {units[index]}"


def format_uptime(seconds: int) -> str:
    days, remainder = divmod(max(0, seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    return f"{days}天 {hours}小时" if days else f"{hours}小时 {minutes}分"


def pressure_color(value: float | int | None, normal: str) -> str:
    number = float(value or 0)
    if number >= 90:
        return RED
    if number >= 75:
        return ORANGE
    return normal


class Gauge(tk.Canvas):
    def __init__(self, master: tk.Misc, label: str, color: str) -> None:
        super().__init__(master, bg=PANEL, highlightthickness=0, height=154, width=190)
        self.label = label
        self.base_color = color
        self.value: float | None = None
        self.meta = "正在采样"
        self.bg_arc = self.create_arc(0, 0, 1, 1, start=135, extent=270, style="arc", outline=LINE, width=10)
        self.value_arc = self.create_arc(0, 0, 1, 1, start=135, extent=0, style="arc", outline=color, width=10)
        self.label_item = self.create_text(0, 0, text=label, fill=MUTED, font=("Segoe UI", 9, "bold"))
        self.value_item = self.create_text(0, 0, text="—", fill=TEXT, font=("Segoe UI Variable Display", 29, "bold"))
        self.unit_item = self.create_text(0, 0, text="%", fill=MUTED, font=("Segoe UI", 9))
        self.meta_item = self.create_text(0, 0, text=self.meta, fill=MUTED, font=("Segoe UI", 8))
        self.bind("<Configure>", lambda _event: self.redraw())

    def update_value(self, value: float | None, meta: str) -> None:
        self.value = value
        self.meta = meta
        self.redraw()

    def redraw(self) -> None:
        width = max(self.winfo_width(), 150)
        height = max(self.winfo_height(), 130)
        cx, cy = width / 2, height * 0.59
        radius = min(width * 0.31, height * 0.36)
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        self.coords(self.bg_arc, *box)
        self.itemconfigure(self.bg_arc, start=135, extent=270)
        value = max(0.0, min(100.0, float(self.value or 0)))
        color = pressure_color(value, self.base_color)
        self.coords(self.value_arc, *box)
        self.itemconfigure(
            self.value_arc,
            start=135,
            extent=-270 * value / 100,
            outline=color,
            state="normal" if self.value is not None else "hidden",
        )
        self.coords(self.label_item, cx, 18)
        display = "—" if self.value is None else str(round(value))
        self.coords(self.value_item, cx, cy - 3)
        self.itemconfigure(self.value_item, text=display)
        self.coords(self.unit_item, cx + 31, cy + 7)
        self.coords(self.meta_item, cx, height - 15)
        self.itemconfigure(self.meta_item, text=self.meta)


class TrendCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=PANEL, highlightthickness=0, height=92)
        self.series: dict[str, deque[float | None]] = {
            "CPU": deque(maxlen=60),
            "GPU": deque(maxlen=60),
            "内存": deque(maxlen=60),
        }
        self.colors = {"CPU": CYAN, "GPU": VIOLET, "内存": LIME}
        self.grid_lines = [self.create_line(0, 0, 1, 1, fill="#182126") for _ in range(3)]
        self.title_item = self.create_text(10, 9, anchor="w", text="最近 60 秒", fill=MUTED, font=("Segoe UI", 8, "bold"))
        self.legend_dots = [self.create_oval(0, 0, 1, 1, outline="") for _ in range(3)]
        self.legend_text = [self.create_text(0, 0, anchor="w", fill=MUTED, font=("Segoe UI", 7)) for _ in range(3)]
        self.series_lines = {name: self.create_line(0, 0, 0, 0, fill=color, width=2, smooth=True) for name, color in self.colors.items()}
        self.bind("<Configure>", lambda _event: self.redraw())

    def add(self, cpu: float | None, gpu: float | None, memory: float | None) -> None:
        for key, value in (("CPU", cpu), ("GPU", gpu), ("内存", memory)):
            self.series[key].append(value)
        self.redraw()

    def redraw(self) -> None:
        width, height = max(self.winfo_width(), 100), max(self.winfo_height(), 60)
        for item, level in zip(self.grid_lines, (25, 50, 75)):
            y = height - 8 - level / 100 * (height - 20)
            self.coords(item, 0, y, width, y)
        self.coords(self.title_item, 10, 9)
        legend_x = width - 150
        for index, name in enumerate(("CPU", "GPU", "内存")):
            x = legend_x + index * 50
            self.coords(self.legend_dots[index], x, 6, x + 5, 11)
            self.itemconfigure(self.legend_dots[index], fill=self.colors[name])
            self.coords(self.legend_text[index], x + 9, 9)
            self.itemconfigure(self.legend_text[index], text=name)
        for name, values in self.series.items():
            points: list[float] = []
            for index, value in enumerate(values):
                if value is None:
                    continue
                x = index / 59 * width
                y = height - 8 - max(0, min(100, value)) / 100 * (height - 20)
                points.extend((x, y))
            line = self.series_lines[name]
            if len(points) >= 4:
                self.coords(line, *points)
                self.itemconfigure(line, state="normal")
            else:
                self.itemconfigure(line, state="hidden")


class ProcessList(tk.Frame):
    def __init__(self, master: tk.Misc, title: str, mode: str) -> None:
        super().__init__(master, bg=PANEL, padx=16, pady=12)
        self.mode = mode
        head = tk.Frame(self, bg=PANEL)
        head.pack(fill="x", pady=(0, 7))
        tk.Label(head, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(head, text="按程序合并", bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
        columns = tk.Frame(self, bg=PANEL_ALT, padx=8, pady=4)
        columns.pack(fill="x")
        tk.Label(columns, text="程序", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 7)).pack(side="left")
        tk.Label(columns, text="实例    占用", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 7)).pack(side="right")
        self.rows = tk.Frame(self, bg=PANEL)
        self.rows.pack(fill="both", expand=True)
        self.row_widgets: list[tuple[tk.Label, tk.Label, tk.Label, tk.Label]] = []
        for index in range(5):
            frame = tk.Frame(self.rows, bg=PANEL, height=34)
            frame.pack(fill="x")
            frame.pack_propagate(False)
            badge = tk.Label(frame, text="", width=2, bg="#182126", fg=CYAN, font=("Segoe UI", 8, "bold"))
            badge.pack(side="left", padx=(0, 8), pady=5)
            name_label = tk.Label(frame, text="", bg=PANEL, fg=TEXT, anchor="w", font=("Segoe UI", 9))
            name_label.pack(side="left", fill="x", expand=True)
            value_label = tk.Label(frame, text="", width=10, bg=PANEL, fg=TEXT, anchor="e", font=("Segoe UI", 9, "bold"))
            value_label.pack(side="right")
            instances_label = tk.Label(frame, text="", width=4, bg=PANEL, fg=MUTED, anchor="e", font=("Segoe UI", 8))
            instances_label.pack(side="right")
            self.row_widgets.append((badge, name_label, value_label, instances_label))
            if index < 4:
                tk.Frame(self.rows, bg=LINE, height=1).pack(fill="x")

    def update_rows(self, rows: list[dict[str, Any]]) -> None:
        for index, widgets in enumerate(self.row_widgets):
            badge, name_label, value_label, instances_label = widgets
            row = rows[index] if index < len(rows) else None
            if row:
                name = row["name"]
                initial = (name[:1] or "?").upper()
                value = f'{row["cpu_percent"]:.1f}%' if self.mode == "cpu" else format_bytes(row["memory_bytes"])
                badge.configure(text=initial)
                name_label.configure(text=name)
                value_label.configure(text=value)
                instances_label.configure(text=str(row["instances"]))
            else:
                badge.configure(text="")
                name_label.configure(text="")
                value_label.configure(text="")
                instances_label.configure(text="")


class PulseBoardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG)
        self.root.geometry("920x640")
        self.root.minsize(800, 590)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=2)
        self.running = True
        self.collector = SystemCollector()
        self._build()
        threading.Thread(target=self._sample_loop, name="pulseboard-ui-sampler", daemon=True).start()
        self.root.after(100, self._consume)

    def _panel(self, master: tk.Misc, **kwargs: Any) -> tk.Frame:
        return tk.Frame(master, bg=PANEL, highlightbackground=LINE, highlightthickness=1, **kwargs)

    def _build(self) -> None:
        body = tk.Frame(self.root, bg=BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)

        header = tk.Frame(body, bg=BG, height=43)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)
        mark = tk.Canvas(header, width=30, height=30, bg=BG, highlightthickness=0)
        mark.pack(side="left", pady=4)
        mark.create_rectangle(3, 3, 27, 27, outline=CYAN, width=1)
        mark.create_line(7, 17, 12, 17, 15, 10, 18, 21, 22, 14, fill=CYAN, width=2)
        title = tk.Frame(header, bg=BG)
        title.pack(side="left", padx=9)
        tk.Label(title, text="PulseBoard", bg=BG, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.host_label = tk.Label(title, text="正在连接本机", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.host_label.pack(anchor="w")
        status = tk.Frame(header, bg=BG)
        status.pack(side="right", pady=3)
        self.health_label = tk.Label(status, text="正在采集", bg=BG, fg=CYAN, font=("Segoe UI", 11, "bold"))
        self.health_label.pack(anchor="e")
        self.time_label = tk.Label(status, text="—", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.time_label.pack(anchor="e")

        gauges_panel = self._panel(body)
        gauges_panel.pack(fill="x", pady=(0, 8))
        gauges_panel.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="gauge")
        self.gauges = {
            "cpu": Gauge(gauges_panel, "CPU", CYAN),
            "gpu": Gauge(gauges_panel, "GPU", VIOLET),
            "memory": Gauge(gauges_panel, "内存", LIME),
            "disk": Gauge(gauges_panel, "系统盘", ORANGE),
        }
        for column, gauge in enumerate(self.gauges.values()):
            gauge.grid(row=0, column=column, sticky="nsew", padx=4, pady=2)

        middle = tk.Frame(body, bg=BG, height=106)
        middle.pack(fill="x", pady=(0, 8))
        middle.pack_propagate(False)
        trend_panel = self._panel(middle)
        trend_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.trend = TrendCanvas(trend_panel)
        self.trend.pack(fill="both", expand=True, padx=6, pady=5)
        flow = self._panel(middle, width=320)
        flow.pack(side="right", fill="y")
        flow.pack_propagate(False)
        tk.Label(flow, text="实时吞吐", bg=PANEL, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(5, 0))
        values = tk.Frame(flow, bg=PANEL)
        values.pack(fill="both", expand=True, padx=12)
        self.flow_labels: dict[str, tk.Label] = {}
        for index, (key, caption) in enumerate((("down", "网络下行"), ("up", "网络上行"), ("read", "磁盘读取"), ("write", "磁盘写入"))):
            cell = tk.Frame(values, bg=PANEL)
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else 10, 0), pady=0)
            tk.Label(cell, text=caption, bg=PANEL, fg=MUTED, font=("Segoe UI", 7)).pack(anchor="w")
            label = tk.Label(cell, text="—", bg=PANEL, fg=TEXT, font=("Segoe UI", 9, "bold"))
            label.pack(anchor="w")
            self.flow_labels[key] = label
        values.grid_columnconfigure((0, 1), weight=1)

        lists = tk.Frame(body, bg=BG)
        lists.pack(fill="both", expand=True)
        lists.grid_columnconfigure((0, 1), weight=1, uniform="list")
        lists.grid_rowconfigure(0, weight=1)
        left = self._panel(lists)
        right = self._panel(lists)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.cpu_list = ProcessList(left, "CPU 占用前 5", "cpu")
        self.memory_list = ProcessList(right, "内存占用前 5", "memory")
        self.cpu_list.pack(fill="both", expand=True)
        self.memory_list.pack(fill="both", expand=True)

        footer = tk.Frame(body, bg=BG, height=25)
        footer.pack(fill="x", pady=(7, 0))
        footer.pack_propagate(False)
        self.gpu_label = tk.Label(footer, text="GPU 正在采样", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.gpu_label.pack(side="left")
        self.process_label = tk.Label(footer, text="数据仅在本机处理", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.process_label.pack(side="right")

    def _sample_loop(self) -> None:
        while self.running:
            started = time.monotonic()
            try:
                snapshot = self.collector.snapshot()
                while self.queue.full():
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        break
                self.queue.put_nowait(snapshot)
            except Exception:
                pass
            time.sleep(max(0.1, 1.0 - (time.monotonic() - started)))

    def _consume(self) -> None:
        latest = None
        try:
            while True:
                latest = self.queue.get_nowait()
        except queue.Empty:
            pass
        if latest:
            self._render(latest)
        if self.running:
            self.root.after(150, self._consume)

    def _render(self, data: dict[str, Any]) -> None:
        cpu, gpu, memory, disk = data["cpu"], data["gpu"], data["memory"], data["disk"]
        self.gauges["cpu"].update_value(cpu["percent"], f'{cpu["logical_cores"]} 线程 · {cpu["frequency_mhz"] or "—"} MHz')
        gpu_meta = f'{gpu["temperature_c"]}°C' if gpu["temperature_c"] is not None else ("已连接" if gpu["available"] else "不可用")
        self.gauges["gpu"].update_value(gpu["percent"], gpu_meta)
        self.gauges["memory"].update_value(memory["percent"], f'{format_bytes(memory["used"])} / {format_bytes(memory["total"])}')
        self.gauges["disk"].update_value(disk["percent"], f'剩余 {format_bytes(disk["free"])}')
        self.trend.add(cpu["percent"], gpu["percent"], memory["percent"])
        self.flow_labels["down"].configure(text=f'{format_bytes(data["network"]["download_bps"])}/s')
        self.flow_labels["up"].configure(text=f'{format_bytes(data["network"]["upload_bps"])}/s')
        self.flow_labels["read"].configure(text=f'{format_bytes(disk["read_bps"])}/s')
        self.flow_labels["write"].configure(text=f'{format_bytes(disk["write_bps"])}/s')
        self.cpu_list.update_rows(data["processes"]["top_cpu"])
        self.memory_list.update_rows(data["processes"]["top_memory"])
        peak = max(cpu["percent"] or 0, gpu["percent"] or 0, memory["percent"] or 0, disk["percent"] or 0)
        health = "压力较高" if peak >= 90 else "负载上升" if peak >= 75 else "运行平稳"
        self.health_label.configure(text=health, fg=pressure_color(peak, CYAN))
        self.time_label.configure(text=f'已运行 {format_uptime(data["host"]["uptime_seconds"])} · {time.strftime("%H:%M:%S")}')
        self.host_label.configure(text=f'{data["host"]["name"]} · {data["host"]["os"]}')
        gpu_detail = gpu["name"]
        if gpu["memory_total"]:
            gpu_detail += f' · 显存 {format_bytes(gpu["memory_used"])} / {format_bytes(gpu["memory_total"])}'
        self.gpu_label.configure(text=gpu_detail)
        self.process_label.configure(text=f'{data["processes"]["count"]} 个进程 · 数据仅在本机处理')

    def close(self) -> None:
        self.running = False
        self.root.destroy()


def acquire_single_instance() -> tuple[bool, int | None]:
    if platform.system() != "Windows":
        return True, None
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
    handle = kernel32.CreateMutexW(None, True, "Local\\PulseBoardDesktop-5F38D7B6")
    if kernel32.GetLastError() == 183:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
        kernel32.CloseHandle(handle)
        return False, None
    return True, handle


def main() -> None:
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    acquired, mutex = acquire_single_instance()
    if not acquired:
        return
    root = tk.Tk()
    app = PulseBoardApp(root)
    try:
        root.mainloop()
    finally:
        app.running = False
        if mutex and platform.system() == "Windows":
            ctypes.windll.kernel32.ReleaseMutex(mutex)
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()

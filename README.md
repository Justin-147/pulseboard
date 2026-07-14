# PulseBoard

[![Release](https://img.shields.io/github/v/release/Justin-147/pulseboard)](https://github.com/Justin-147/pulseboard/releases)
[![Test](https://github.com/Justin-147/pulseboard/actions/workflows/test.yml/badge.svg)](https://github.com/Justin-147/pulseboard/actions/workflows/test.yml)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)](README.md)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

PulseBoard 是一个紧凑的原生 Windows 系统资源仪表盘。它不使用浏览器、不启动本地 Web 服务，以单个约 920 × 640 的窗口展示 CPU、GPU、内存、磁盘、网络和高占用程序。

## 功能

- 四个实时表盘：CPU、GPU、内存、系统盘。
- 最近 60 秒 CPU、GPU、内存趋势。
- 网络上下行与磁盘读写速度。
- CPU 和内存占用前 5 的程序，自动合并同名进程。
- NVIDIA 显卡可显示显存与温度；其他显卡使用 Windows 性能计数器。
- 登录 Windows 后可自动弹出仪表盘。
- 单实例运行：重复双击只会聚焦已有窗口。
- 数据只在本机内存中处理，不上传、不写入历史数据库。

## 快速开始

需要 Windows 10/11 与 Python 3.10 或更高版本。推荐使用 [python.org](https://www.python.org/downloads/windows/) 的标准安装程序，并保留默认的 Tcl/Tk 组件。

1. 下载并解压最新 [Release](https://github.com/Justin-147/pulseboard/releases)。
2. 双击 `PulseBoard.exe`，或双击兼容入口 `Start-PulseBoard.bat`。
3. Release 已包含独立运行程序，不需要浏览器、Python 或额外安装。

如果从源代码启动，`Start-PulseBoard.bat` 会自动创建 Python 独立环境并安装唯一依赖 `psutil`。

窗口可以缩放，默认尺寸为 920 × 640，最小尺寸为 800 × 590。所有核心内容都在同一页内，不需要滚动。

## 开机自启动

- 双击 `Install-Autostart.bat`：为当前 Windows 用户启用自启动，下次登录后直接弹出仪表盘。
- 双击 `Uninstall-Autostart.bat`：取消自启动。

该操作不需要管理员权限，也不会创建系统服务。

## GPU 兼容性

PulseBoard 优先调用 NVIDIA 驱动自带的 `nvidia-smi`，因此 NVIDIA 用户可获得利用率、显存和温度。AMD、Intel 及其他显卡会尝试读取 Windows GPU Engine 性能计数器；驱动未公开的温度或显存数据会显示为不可用，不使用估算值。

## 本地开发与测试

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m pulseboard.desktop
```

## 设计依据

界面采用“表盘概览 → 短期趋势 → 高占用程序”的顺序：先判断资源压力，再观察变化，最后定位原因。百分比指标统一使用 0–100 范围，只在 75% 和 90% 阈值改变颜色。

信息选择参考了 [Grafana 仪表盘最佳实践](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/)、[Glances 进程列表](https://glances.readthedocs.io/en/latest/aoa/ps.html)和 [Netdata 实时进程视图](https://learn.netdata.cloud/docs/live-view/processes)。

## License

[MIT](LICENSE)

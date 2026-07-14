# PulseBoard

PulseBoard 是一个面向 Windows 的本地实时系统资源仪表盘。它以低认知负担的方式展示 CPU、GPU、内存、磁盘、网络、最近 60 秒趋势，以及资源占用前 5 的程序。

## 功能

- CPU：总体利用率、逻辑线程、当前频率、每核心采样。
- GPU：利用率；NVIDIA 显卡额外显示显存与温度，其他 Windows GPU 使用系统性能计数器。
- 内存与系统盘：使用率、已用/可用容量。
- 实时吞吐：网络上下行、磁盘读写速度。
- 程序排行：按程序名合并进程，分别展示 CPU 和内存占用前 5。
- 趋势：浏览器内保留最近 60 秒数据，不写入硬盘。
- 隐私：服务仅监听 `127.0.0.1`，不上传遥测或资源数据。

## 快速开始

需要 Windows 10/11 与 Python 3.10 或更高版本。

1. 下载并解压 Release。
2. 双击 `Start-PulseBoard.bat`。
3. 首次启动会自动创建独立运行环境并安装 `psutil`，随后打开 `http://127.0.0.1:17865`。

后续双击启动通常只需一两秒。如果仪表盘已经在后台运行，脚本只会再次打开页面，不会启动第二份服务。

## 开机自启动

- 双击 `Install-Autostart.bat`：登录 Windows 后在后台启动，不自动弹出浏览器。
- 双击 `Uninstall-Autostart.bat`：取消自启动。

自启动只为当前 Windows 用户创建“启动”文件夹快捷方式，不需要管理员权限。

## GPU 兼容性

PulseBoard 优先调用 NVIDIA 驱动自带的 `nvidia-smi`，因此 NVIDIA 用户可获得利用率、显存与温度。AMD、Intel 及其他显卡会尝试读取 Windows GPU Engine 性能计数器；不同驱动对温度和显存指标的开放程度不同，界面会诚实显示可用项，而不会填入估算值。

## 设计依据

界面采用“概览 → 趋势 → 定位高占用程序”的阅读顺序：先回答电脑是否吃紧，再解释何时出现压力，最后定位哪个程序造成压力。百分比指标采用统一的 0–100 范围，并仅在达到阈值时改变颜色；页面刷新周期为 1 秒，GPU 的较重采样在后台每 5 秒更新一次。

这套信息架构参考了 [Grafana 的仪表盘最佳实践](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/)（降低认知负担、统一量纲、谨慎使用颜色）、[Glances 的进程列表设计](https://glances.readthedocs.io/en/latest/aoa/ps.html)（按 CPU、内存与 I/O 快速定位进程）以及 [Netdata 的实时进程视图](https://learn.netdata.cloud/docs/live-view/processes)（从概览下钻到资源消费者）。Windows 降级采样基于系统提供的[性能计数器](https://learn.microsoft.com/windows/win32/perfctrs/about-performance-counters)。

## 本地开发与测试

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m pulseboard.server
```

## 安全说明

- 默认仅允许本机访问，不要将 `--host` 改为公网地址。
- 进程列表只显示程序名、实例数、少量 PID 与资源占用，不读取文件内容。
- 页面不依赖 CDN，断网时也能完整使用。

## License

[MIT](LICENSE)

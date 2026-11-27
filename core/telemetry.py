"""Lightweight optional host and GPU metrics for the local dashboard."""
import ctypes
import sys
import threading


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]


class SystemTelemetry:
    def __init__(self):
        self._psutil = None
        self._nvml = None
        self._nvml_error = None
        self._cpu_lock = threading.Lock()
        self._cpu_previous = None
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
        except Exception as exc:
            self._nvml_error = str(exc)

    def snapshot(self):
        result = {"ram": None, "cpu_percent": None, "gpu": self._gpu(), "errors": []}
        try:
            result["ram"] = self._memory()
        except Exception as exc:
            result["errors"].append(f"RAM: {exc}")
        try:
            result["cpu_percent"] = self._cpu_percent()
        except Exception as exc:
            result["errors"].append(f"CPU: {exc}")
        return result

    def _memory(self):
        if sys.platform == "win32":
            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise ctypes.WinError()
            total = int(status.ullTotalPhys)
            available = int(status.ullAvailPhys)
            return {
                "total_mb": round(total / (1024 * 1024)),
                "used_mb": round((total - available) / (1024 * 1024)),
                "percent": int(status.dwMemoryLoad),
            }
        if self._psutil:
            memory = self._psutil.virtual_memory()
            return {
                "total_mb": round(memory.total / (1024 * 1024)),
                "used_mb": round(memory.used / (1024 * 1024)),
                "percent": int(memory.percent),
            }
        return None

    def _cpu_percent(self):
        if self._psutil:
            return self._psutil.cpu_percent(interval=None)
        if sys.platform != "win32":
            return None

        idle = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            raise ctypes.WinError()

        def ticks(value):
            return (value.high << 32) | value.low

        current = (ticks(idle), ticks(kernel), ticks(user))
        with self._cpu_lock:
            previous = self._cpu_previous
            self._cpu_previous = current
        if previous is None:
            return None
        idle_delta = current[0] - previous[0]
        total_delta = (current[1] - previous[1]) + (current[2] - previous[2])
        if total_delta <= 0:
            return None
        return round(max(0, min(100, (total_delta - idle_delta) * 100 / total_delta)))

    def _gpu(self):
        if self._nvml is None:
            return {"available": False, "reason": self._nvml_error}
        try:
            handle = self._nvml.nvmlDeviceGetHandleByIndex(0)
            memory = self._nvml.nvmlDeviceGetMemoryInfo(handle)
            name = self._nvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            temperature = self._nvml.nvmlDeviceGetTemperature(
                handle, self._nvml.NVML_TEMPERATURE_GPU
            )
            return {
                "available": True,
                "name": name,
                "vram_total_mb": round(memory.total / (1024 * 1024)),
                "vram_used_mb": round(memory.used / (1024 * 1024)),
                "temperature_c": int(temperature),
            }
        except Exception as exc:
            return {"available": False, "reason": str(exc)}

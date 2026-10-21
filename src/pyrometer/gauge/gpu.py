"""NVIDIA GPU metrics via NVML. Needs ``pip install pyrometer[gpu]``."""

from __future__ import annotations

from typing import Any

from pyrometer.core.collector import CollectorUnavailable, registry
from pyrometer.core.sample import Sample


@registry.register("gpu")
class GpuCollector:
    """Metrics per GPU (tags ``gpu`` index and ``model``):
    ``gpu.utilization_percent``, ``gpu.memory_utilization_percent``,
    ``gpu.memory_used_bytes``, ``gpu.memory_total_bytes``,
    ``gpu.temperature_celsius``, ``gpu.power_watts``.

    Raises ``CollectorUnavailable`` if ``nvidia-ml-py`` is not installed or
    NVML cannot initialise (no driver / no GPU).
    """

    name = "gpu"

    def __init__(self) -> None:
        try:
            import pynvml
        except ImportError as exc:
            raise CollectorUnavailable(
                "nvidia-ml-py is not installed (pip install pyrometer[gpu])"
            ) from exc
        try:
            pynvml.nvmlInit()
        except Exception as exc:
            raise CollectorUnavailable(f"NVML could not initialise: {exc}") from exc
        self._nvml: Any = pynvml
        count = pynvml.nvmlDeviceGetCount()
        self._devices = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            model = pynvml.nvmlDeviceGetName(handle)
            if isinstance(model, bytes):
                model = model.decode()
            self._devices.append((handle, {"gpu": str(i), "model": str(model)}))

    def collect(self, timestamp: float) -> list[Sample]:
        nvml = self._nvml
        samples: list[Sample] = []
        for handle, tags in self._devices:
            util = nvml.nvmlDeviceGetUtilizationRates(handle)
            mem = nvml.nvmlDeviceGetMemoryInfo(handle)
            samples += [
                Sample(timestamp, "gpu.utilization_percent", float(util.gpu), tags),
                Sample(timestamp, "gpu.memory_utilization_percent", float(util.memory), tags),
                Sample(timestamp, "gpu.memory_used_bytes", float(mem.used), tags),
                Sample(timestamp, "gpu.memory_total_bytes", float(mem.total), tags),
            ]
            try:
                temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                samples.append(Sample(timestamp, "gpu.temperature_celsius", float(temp), tags))
            except nvml.NVMLError:
                pass
            try:
                milliwatts = nvml.nvmlDeviceGetPowerUsage(handle)
                samples.append(Sample(timestamp, "gpu.power_watts", milliwatts / 1000.0, tags))
            except nvml.NVMLError:
                pass
        return samples

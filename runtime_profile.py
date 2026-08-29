"""
CLARA-AGI Phase 2 - Runtime Resource Governor.

Read-only hardware probing + conservative profile selection for local laptops.
No heavy dependencies; best-effort with safe fallbacks.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    max_concurrency: int = 1
    context_default: int = 2048
    context_hard_cap: int = 4096
    completion_default: int = 384
    reserve_ram_bytes: int = 3 * 1024 * 1024 * 1024
    max_idle_minutes_per_session: int = 10
    max_idle_minutes_per_day: int = 20
    max_idle_topics_per_session: int = 3
    max_idle_facts_per_session: int = 5
    note: str = ""


PROFILES: dict[str, RuntimeProfile] = {
    "eco": RuntimeProfile(
        name="eco",
        max_concurrency=1,
        context_default=2048,
        context_hard_cap=4096,
        completion_default=384,
        reserve_ram_bytes=2 * 1024 * 1024 * 1024,
        max_idle_minutes_per_session=5,
        max_idle_minutes_per_day=10,
        max_idle_topics_per_session=2,
        max_idle_facts_per_session=3,
        note="Tiết kiệm tài nguyên, ưu tiên chat.",
    ),
    "mobile_12gb_safe": RuntimeProfile(
        name="mobile_12gb_safe",
        max_concurrency=1,
        context_default=2048,
        context_hard_cap=4096,
        completion_default=384,
        reserve_ram_bytes=3 * 1024 * 1024 * 1024,
        max_idle_minutes_per_session=10,
        max_idle_minutes_per_day=20,
        max_idle_topics_per_session=3,
        max_idle_facts_per_session=5,
        note="Cân bằng cho máy ~11-12GB RAM, không làm lag máy.",
    ),
    "custom": RuntimeProfile(
        name="custom",
        max_concurrency=1,
        context_default=2048,
        context_hard_cap=4096,
        completion_default=384,
        reserve_ram_bytes=3 * 1024 * 1024 * 1024,
        max_idle_minutes_per_session=10,
        max_idle_minutes_per_day=20,
        max_idle_topics_per_session=3,
        max_idle_facts_per_session=5,
        note="Tùy biến; chỉnh thủ công khi biết rõ phần cứng.",
    ),
}


@dataclass
class RuntimeState:
    profile: RuntimeProfile
    ram_total_bytes: int | None = None
    ram_available_bytes: int | None = None
    swap_used_bytes: int | None = None
    cpu_threads: int | None = None
    load1: float | None = None
    disk_free_bytes: int | None = None
    battery_power_plugged: bool | None = None
    gpu_known: bool = False
    gpu_vram_known: bool = False
    mode: str = "chat"
    degraded_reason: str | None = None
    provider_model: str | None = None
    backend: str | None = None


def _read_int(path: Path) -> int | None:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace").strip()
        if txt.isdigit():
            return int(txt)
    except Exception:
        pass
    return None


def _parse_meminfo() -> dict[str, int | None]:
    out: dict[str, int | None] = {
        "MemTotal": None,
        "MemAvailable": None,
        "SwapTotal": None,
        "SwapFree": None,
    }
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            key = parts[0].strip()
            if key not in out:
                continue
            val = parts[1].strip().split()
            if not val:
                continue
            num = val[0]
            if num.isdigit():
                out[key] = int(num) * 1024
    except Exception:
        pass
    return out


def _parse_loadavg() -> float | None:
    try:
        txt = Path("/proc/loadavg").read_text(encoding="utf-8", errors="replace").strip()
        return float(txt.split()[0])
    except Exception:
        return None


def _parse_cpuinfo() -> int | None:
    try:
        return sum(1 for _ in open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") if _.startswith("processor")) or None
    except Exception:
        return None


def _parse_stat() -> int | None:
    try:
        txt = Path("/proc/stat").read_text(encoding="utf-8", errors="replace").splitlines()[0]
        parts = txt.split()
        return int(parts[1]) + int(parts[2]) + int(parts[3]) if len(parts) >= 4 else None
    except Exception:
        return None


def _disk_free() -> int | None:
    try:
        st = os.statvfs(str(Path(__file__).resolve().parent))
        return st.f_bavail * st.f_frsize
    except Exception:
        return None


def _battery_status() -> bool | None:
    candidates = sorted(Path("/sys/class/power_supply").glob("*")) if Path("/sys/class/power_supply").exists() else []
    for p in candidates:
        try:
            online = (p / "status").read_text(encoding="utf-8", errors="replace").strip().lower()
            return online in {"charging", "full"}
        except Exception:
            continue
    return None


def _cpu_active() -> int | None:
    a = _parse_stat()
    if a is None:
        return None
    b = _parse_stat()
    if b is None:
        return None
    return max(0, b - a)


def probe_hardware() -> dict[str, object]:
    mem = _parse_meminfo()
    threads = _parse_cpuinfo() or os.cpu_count()
    swap_total = mem.get("SwapTotal") or 0
    swap_free = mem.get("SwapFree") or 0
    swap_used = max(0, (swap_total or 0) - (swap_free or 0))
    out: dict[str, object] = {
        "ram_total_bytes": mem.get("MemTotal"),
        "ram_available_bytes": mem.get("MemAvailable"),
        "swap_used_bytes": swap_used,
        "cpu_threads": threads,
        "load1": _parse_loadavg(),
        "disk_free_bytes": _disk_free(),
        "battery_power_plugged": _battery_status(),
        "gpu_known": False,
        "gpu_vram_known": False,
    }
    return out


def degraded_reason(hw: dict[str, object], profile: RuntimeProfile) -> str | None:
    avail = hw.get("ram_available_bytes")
    if avail is not None and profile.reserve_ram_bytes and avail < profile.reserve_ram_bytes:
        return f"low_ram available_bytes={avail}"
    swap_used = hw.get("swap_used_bytes")
    if isinstance(swap_used, int) and swap_used >= 1024 * 1024 * 1024:
        return f"high_swap swap_used={swap_used}"
    battery = hw.get("battery_power_plugged")
    if battery is False:
        return "on_battery"
    return None


def choose_profile(name: str) -> RuntimeProfile:
    return PROFILES.get(name, PROFILES["mobile_12gb_safe"])


def governor_status(
    profile_name: str = "mobile_12gb_safe",
    provider_model: str | None = None,
    backend: str | None = None,
) -> dict[str, object]:
    profile = choose_profile(profile_name)
    hw = probe_hardware()
    reason = degraded_reason(hw, profile)
    mode = "chat" if reason is None else "degraded"
    return {
        "profile": profile.name,
        "mode": mode,
        "degraded_reason": reason,
        "backend": backend,
        "provider_model": provider_model or "unknown",
        "hardware": hw,
        "config": {
            "max_concurrency": profile.max_concurrency,
            "context_default": profile.context_default,
            "context_hard_cap": profile.context_hard_cap,
            "completion_default": profile.completion_default,
            "reserve_ram_bytes": profile.reserve_ram_bytes,
        },
    }


__all__ = [
    "PROFILES",
    "RuntimeProfile",
    "RuntimeState",
    "choose_profile",
    "degraded_reason",
    "governor_status",
    "probe_hardware",
]

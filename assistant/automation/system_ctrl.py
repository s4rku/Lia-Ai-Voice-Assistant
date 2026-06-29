"""
System-level controls: volume, brightness, power, shell execution.
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from loguru import logger

try:
    import screen_brightness_control as sbc  # type: ignore
    _SBC_AVAILABLE = True
except (ImportError, OSError, Exception):
    sbc = None  # type: ignore
    _SBC_AVAILABLE = False

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    from comtypes import CLSCTX_ALL  # type: ignore
    import ctypes
    _PYCAW_AVAILABLE = True
except Exception:
    _PYCAW_AVAILABLE = False


# ── Volume ────────────────────────────────────────────────────────────────────

async def set_volume(level: int, **_: Any) -> str:
    """Set system volume 0-100."""
    level = max(0, min(100, int(level)))
    loop = asyncio.get_running_loop()
    if _PYCAW_AVAILABLE:
        await loop.run_in_executor(None, _set_vol_pycaw, level)
        return f"Volume set to {level}%."
    # Fallback: PowerShell
    ps = f"(New-Object -ComObject WScript.Shell).SendKeys([char]174 * 50); " \
         f"$vol = {level}; " \
         f"$wsh = New-Object -ComObject WScript.Shell; " \
         f"Add-Type -AssemblyName System.Windows.Forms; " \
         f"[System.Windows.Forms.SendKeys]::SendWait('%{{F2}}')"
    # Simpler PowerShell approach
    script = (
        f"$obj = New-Object -ComObject WScript.Shell; "
        f"$nircmd = 'nircmd.exe setsysvolume {int(level * 655.35)}'; "
        f"Invoke-Expression $nircmd"
    )
    await _run_ps(script)
    return f"Volume set to {level}%."


def _set_vol_pycaw(level: int) -> None:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    from comtypes import CLSCTX_ALL  # type: ignore
    import ctypes
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    scalar = level / 100.0
    volume.SetMasterVolumeLevelScalar(scalar, None)


async def mute(state: bool = True, **_: Any) -> str:
    if _PYCAW_AVAILABLE:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _mute_pycaw, state)
        return "Muted." if state else "Unmuted."
    return "Volume control library not available."


def _mute_pycaw(state: bool) -> None:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    from comtypes import CLSCTX_ALL  # type: ignore
    import ctypes
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    volume.SetMute(int(state), None)


# ── Brightness ────────────────────────────────────────────────────────────────

async def set_brightness(level: int, **_: Any) -> str:
    level = max(0, min(100, int(level)))
    if not _SBC_AVAILABLE:
        return "screen-brightness-control not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: sbc.set_brightness(level))
    return f"Brightness set to {level}%."


# ── Power controls ────────────────────────────────────────────────────────────

async def shutdown(delay: int = 0, **_: Any) -> str:
    await _run_shell(f"shutdown /s /t {delay}")
    return f"Shutting down in {delay}s."


async def restart(delay: int = 0, **_: Any) -> str:
    await _run_shell(f"shutdown /r /t {delay}")
    return f"Restarting in {delay}s."


async def sleep(**_: Any) -> str:
    await _run_shell("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "Going to sleep."


async def lock(**_: Any) -> str:
    await _run_shell("rundll32.exe user32.dll,LockWorkStation")
    return "PC locked."


# ── Shell execution ───────────────────────────────────────────────────────────

async def run_cmd(command: str, **_: Any) -> str:
    result = await _run_shell(command, capture=True)
    return result[:500] if result else "Command executed."


async def run_powershell(script: str, **_: Any) -> str:
    result = await _run_ps(script, capture=True)
    return result[:500] if result else "Script executed."


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_shell(cmd: str, capture: bool = False) -> str:
    loop = asyncio.get_running_loop()
    proc = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            cmd, shell=True, capture_output=capture, text=True,
            timeout=30,
        ),
    )
    return (proc.stdout or proc.stderr or "").strip() if capture else ""


async def _run_ps(script: str, capture: bool = False) -> str:
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    loop = asyncio.get_running_loop()
    proc = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, capture_output=capture, text=True, timeout=30),
    )
    return (proc.stdout or proc.stderr or "").strip() if capture else ""

"""
App / window management automation.
"""
from __future__ import annotations

import subprocess
import asyncio
from typing import Any

from loguru import logger

try:
    import pygetwindow as gw  # type: ignore
    _GW_AVAILABLE = True
except ImportError:
    gw = None  # type: ignore
    _GW_AVAILABLE = False

try:
    import psutil  # type: ignore
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False

try:
    import pyautogui  # type: ignore
    _PAG_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore
    _PAG_AVAILABLE = False


# ── Well-known app aliases ─────────────────────────────────────────────────────
_APP_ALIASES: dict[str, str] = {
    "notepad":      "notepad.exe",
    "calculator":   "calc.exe",
    "explorer":     "explorer.exe",
    "paint":        "mspaint.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
    "powerpoint":   "powerpnt.exe",
    "chrome":       "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "vscode":       "code.exe",
    "vs code":      "code.exe",
    "discord":      "discord.exe",
    "spotify":      "spotify.exe",
    "steam":        "steam.exe",
    "task manager": "taskmgr.exe",
    "cmd":          "cmd.exe",
    "powershell":   "powershell.exe",
    "terminal":     "wt.exe",
    "obs":          "obs64.exe",
    "vlc":          "vlc.exe",
    "zoom":         "zoom.exe",
    "teams":        "teams.exe",
    "slack":        "slack.exe",
    "control panel":"control.exe",
    "settings":     "ms-settings:",
    "snipping tool":"snippingtool.exe",
}


async def open_app(app: str, **_: Any) -> str:
    resolved = _APP_ALIASES.get(app.lower(), app)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, lambda: subprocess.Popen(
            resolved, shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        ))
        return f"Opened {app}."
    except Exception as exc:
        return f"Could not open {app}: {exc}"


async def close_app(app: str, **_: Any) -> str:
    if not _PSUTIL_AVAILABLE:
        return "psutil not installed."
    name = _APP_ALIASES.get(app.lower(), app).lower()
    killed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        if proc.info["name"] and proc.info["name"].lower().startswith(name.replace(".exe", "")):
            try:
                proc.kill()
                killed += 1
            except psutil.NoSuchProcess:
                pass
    return f"Closed {killed} instance(s) of {app}." if killed else f"{app} was not running."


async def kill_process(pid: int | None = None, name: str | None = None, **_: Any) -> str:
    if not _PSUTIL_AVAILABLE:
        return "psutil not installed."
    killed = []
    for proc in psutil.process_iter(["name", "pid"]):
        if pid and proc.info["pid"] == int(pid):
            proc.kill(); killed.append(str(pid))
        elif name and proc.info["name"] and name.lower() in proc.info["name"].lower():
            proc.kill(); killed.append(proc.info["name"])
    return f"Killed: {', '.join(killed)}." if killed else "No matching process found."


async def switch_window(title: str, **_: Any) -> str:
    if not _GW_AVAILABLE:
        return "pygetwindow not installed."
    wins = gw.getWindowsWithTitle(title)
    if not wins:
        return f"No window found with title containing '{title}'."
    win = wins[0]
    win.activate()
    return f"Switched to: {win.title}"


async def minimize_window(title: str = "", **_: Any) -> str:
    if not _GW_AVAILABLE:
        return "pygetwindow not installed."
    if title:
        wins = gw.getWindowsWithTitle(title)
    else:
        wins = [gw.getActiveWindow()]
    if not wins or not wins[0]:
        return "No window found."
    wins[0].minimize()
    return "Window minimised."


async def maximize_window(title: str = "", **_: Any) -> str:
    if not _GW_AVAILABLE:
        return "pygetwindow not installed."
    if title:
        wins = gw.getWindowsWithTitle(title)
    else:
        wins = [gw.getActiveWindow()]
    if not wins or not wins[0]:
        return "No window found."
    wins[0].maximize()
    return "Window maximised."


async def list_windows(**_: Any) -> str:
    if not _GW_AVAILABLE:
        return "pygetwindow not installed."
    titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
    return "Open windows: " + ", ".join(titles[:15]) if titles else "No windows found."

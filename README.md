# Sarku — AI Voice Assistant for Windows

> A Jarvis-like desktop AI companion. Listens continuously, understands natural language,
> speaks with a realistic voice, and controls your entire Windows PC.

---

## What Sarku Can Do

| Category | Capabilities |
|---|---|
| **Conversation** | Natural fluid dialogue, short-term + long-term memory, context awareness, follow-up questions |
| **Wake Word** | Offline detection — say *"Hey Sarku"*, *"Sarku"*, or *"Hello Sarku"* |
| **Voice** | Microsoft Edge neural TTS, interruptible mid-sentence, streaming playback |
| **Speech Recognition** | faster-whisper (Whisper model), Silero VAD, noise suppression |
| **Apps** | Open, close, kill, switch, minimize, maximize any Windows app |
| **System** | Volume, brightness, shutdown, restart, sleep, lock, run CMD/PowerShell |
| **Files** | Create, delete, move, copy, rename, zip, extract, search, read PDFs/Word/Excel |
| **Browser** | Chrome/Edge/Firefox — open URLs, Google search, tabs, YouTube, Gmail, Discord |
| **Vision** | Screenshot, OCR, find & click text on screen, GPT-4o screen description |
| **AI Brain** | OpenAI GPT-4o-mini, streaming responses, fact extraction, user preferences |
| **Memory** | SQLite (sessions, history, facts) + ChromaDB (semantic recall) |
| **GUI** | Floating animated orb, conversation history, system stats, dark/light theme |
| **Safety** | Confirmation required for dangerous actions (delete, shutdown, PowerShell) |
| **Plugins** | Extensible architecture — add any capability as a plugin |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Windows 10 / 11** | Required |
| **Python 3.10+** | 3.12 recommended. [Download](https://python.org) |
| **OpenAI API Key** | [Get one here](https://platform.openai.com/api-keys) |
| **Tesseract OCR** | Required for screen reading. [Download](https://github.com/UB-Mannheim/tesseract/wiki) |
| **FFmpeg** | Required for audio. [Download](https://ffmpeg.org/download.html) |
| **CUDA GPU** | Optional — makes speech recognition 5–10× faster |
| **Microphone** | Any microphone works |

---

## Installation

### Option A — One command

```bat
setup.bat
```

This creates the virtual environment, installs all dependencies, and copies `.env.example` → `.env`.

### Option B — Manual

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### After install — configure your API key

Open `.env` and set at minimum:

```env
OPENAI_API_KEY=sk-...
```

---

## Running Sarku

```bat
.venv\Scripts\activate
python -m assistant.main
```

A floating window appears with the animated orb. Say one of the wake words to start:

- **"Hey Sarku"**
- **"Sarku"**
- **"Hello Sarku"**

To stop listening say: *"Goodbye"*, *"Sleep"*, or *"That's all"*.

---

## Configuration

All settings live in `.env`. No code changes needed.

```env
# ── Identity ──────────────────────────────────────────────────────────────────
ASSISTANT_NAME=Sarku
USER_NAME=Boss

# ── Wake words (comma-separated) ──────────────────────────────────────────────
WAKE_WORDS=hey sarku,sarku,hello sarku

# ── AI ────────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# ── Speech Recognition ────────────────────────────────────────────────────────
STT_MODEL=base.en        # tiny.en | base.en | small.en | medium.en | large-v3
STT_DEVICE=cpu           # cpu | cuda

# ── Voice ─────────────────────────────────────────────────────────────────────
TTS_VOICE=en-US-GuyNeural
TTS_RATE=+10%

# ── Vision ────────────────────────────────────────────────────────────────────
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# ── GUI ───────────────────────────────────────────────────────────────────────
GUI_THEME=dark           # dark | light
GUI_ALWAYS_ON_TOP=true
GUI_START_MINIMIZED=false

# ── Weather (optional) ────────────────────────────────────────────────────────
WEATHER_API_KEY=
WEATHER_CITY=London
```

---

## Example Conversations

```
You:   "Hey Sarku"
Sarku: "Yes?"
You:   "Open Spotify and set the volume to 60%"
Sarku: "Done — Spotify is launching and I've set the volume to 60%."

You:   "Sarku, search YouTube for lofi hip hop"
Sarku: "Opening that now."

You:   "My PC is running slow"
Sarku: "Your CPU is sitting at 91% — looks like Chrome is the culprit.
        Want me to close it?"

You:   "What's on my screen right now?"
Sarku: "I can see VS Code open with a Python file called main.py..."

You:   "I need to send a message to John on Discord"
Sarku: "Opening Discord Web now. What would you like to say to John?"

You:   "Shutdown the PC"
Sarku: "Are you sure you want to shutdown? Say yes or no."
You:   "Yes"
Sarku: "Shutting down in 0 seconds."

You:   "Goodbye"
Sarku: "Going quiet. Just say my name when you need me."
```

---

## Project Structure

```
sarku/
├── assistant/
│   ├── main.py              Entry point — boots everything, bridges Qt ↔ asyncio
│   ├── config/
│   │   ├── settings.py      All config via pydantic-settings + .env
│   │   └── logging_setup.py Loguru — console (colourised) + rotating file
│   ├── core/
│   │   ├── events.py        Async pub/sub event bus (all modules communicate here)
│   │   └── types.py         Shared types: Message, Role, AssistantState
│   ├── database/
│   │   ├── db.py            Async SQLAlchemy + aiosqlite, WAL mode
│   │   └── models.py        ConversationSession, ChatMessage, UserPreference,
│   │                        CommandHistory, KnowledgeFact
│   ├── system/
│   │   └── health.py        Background CPU/RAM/disk/battery/network monitor
│   ├── plugins/
│   │   └── base.py          Plugin ABC + PluginManager (register/dispatch)
│   ├── audio/
│   │   ├── microphone.py    sounddevice async stream → AudioFrame queue
│   │   └── vad.py           Silero VAD state machine → Utterance events
│   ├── stt/
│   │   └── transcriber.py   faster-whisper, lazy load, thread pool, TRANSCRIPT_READY
│   ├── tts/
│   │   └── speaker.py       edge-tts streaming, sentence split, interrupt-on-speech
│   ├── wakeword/
│   │   └── detector.py      OpenWakeWord (primary) + regex transcript fallback
│   ├── ai/
│   │   ├── brain.py         OpenAI streaming, system prompt, action extraction,
│   │   │                    fact extraction, stub mode (no API key)
│   │   └── conversation.py  State machine: IDLE→LISTEN→THINK→SPEAK→LISTEN
│   ├── memory/
│   │   └── store.py         SQLite (sessions/facts/prefs) + ChromaDB semantic recall
│   ├── automation/
│   │   ├── dispatcher.py    Intent router with dangerous-action confirmation gate
│   │   ├── apps.py          Open/close/kill/switch/minimize/maximize apps
│   │   ├── keyboard.py      Type text, press keys, hotkeys, clipboard
│   │   ├── mouse.py         Click, drag, scroll, screenshot
│   │   ├── system_ctrl.py   Volume, brightness, power, CMD, PowerShell
│   │   └── file_ops.py      Create/delete/move/copy/zip/extract/read docs
│   ├── browser/
│   │   └── controller.py    Playwright async — Chrome/Edge/Firefox,
│   │                        tabs, forms, YouTube, Gmail, Discord
│   ├── vision/
│   │   └── screen.py        Tesseract OCR, text-find-click, GPT-4o vision
│   └── gui/
│       ├── orb.py           PySide6 animated orb (pulse/spin/wave per state)
│       ├── window.py        Frameless floating window, conversation panel, stats
│       └── app.py           Qt ↔ asyncio co-runner via QTimer pump
├── tests/
│   └── unit/                55 tests — all phases covered
├── installer/
│   ├── build.bat            PyInstaller one-file build
│   ├── install.iss          Inno Setup installer script
│   └── create_icon.py       Generates sarku.ico with Pillow
├── data/
│   ├── memory/              SQLite DB + ChromaDB (auto-created at runtime)
│   ├── models/              Wake word ONNX models (auto-downloaded)
│   └── screenshots/         Saved screenshots
├── .env.example             Configuration template
├── requirements.txt         All pinned dependencies
├── setup.bat                One-command installer
└── pyproject.toml           Build config, CLI entry point
```

---

## Architecture Overview

```
Microphone ──► VAD ──► WakeWord ──► STT ──► ConversationLoop
                                                │
                                           AI Brain ◄──► Memory
                                                │
                                         Dispatcher ──► Automation
                                                │        Browser
                                                │        Vision
                                                │
                                             TTS ──► Speaker ──► 🔊
                                                │
                                             GUI (EventBus)
```

All modules communicate through the **EventBus** (async pub/sub). No module imports another's internals directly — everything goes through events or well-defined public APIs.

---

## Adding a Plugin

```python
# assistant/plugins/my_plugin.py
from assistant.plugins.base import Plugin
from typing import Any

class WeatherPlugin(Plugin):
    name = "weather"
    version = "1.0.0"
    handles = ["get_weather"]

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        city = params.get("city", "London")
        # ... fetch weather ...
        return {"response": f"It's 22°C and sunny in {city}."}
```

Register it in `main.py`:

```python
from assistant.plugins.my_plugin import WeatherPlugin
plugin_manager.register(WeatherPlugin())
```

---

## Supported App Aliases

Sarku understands natural names — you don't need to know the `.exe`:

`notepad` · `calculator` · `explorer` · `paint` · `word` · `excel` · `powerpoint`
`chrome` · `firefox` · `edge` · `vscode` · `discord` · `spotify` · `steam`
`cmd` · `powershell` · `terminal` · `obs` · `vlc` · `zoom` · `teams` · `slack`
`task manager` · `control panel` · `settings` · `snipping tool`

---

## Supported Automation Intents

The AI brain emits these intents as JSON blocks after its response. They are stripped from spoken text before TTS.

```
open_app        close_app       kill_process    switch_window
minimize_window maximize_window list_windows
type_text       press_key       hotkey          clipboard_get   clipboard_set
click           double_click    right_click     move_mouse      drag           scroll
take_screenshot
set_volume      mute            set_brightness
shutdown        restart         sleep           lock
run_cmd         run_powershell
create_folder   delete_file     move_file       copy_file       rename_file
search_files    read_file       zip_files       extract_archive empty_recycle_bin
open_url        search_google   new_tab         close_tab       go_back        go_forward
play_youtube    youtube_pause   open_gmail      open_discord    browser_click  get_page_text
click_text      read_screen     describe_screen
```

---

## Running Tests

```bat
.venv\Scripts\activate
pytest tests/ -v
```

Expected output: **55 passed**

---

## Building a Standalone Executable

```bat
:: 1. Generate icon (optional, needs Pillow)
python installer\create_icon.py

:: 2. Build .exe
installer\build.bat

:: Output: dist\Sarku.exe
```

To build a full Windows installer (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```
Compile installer\install.iss → SarkuSetup.exe
```

---

## Dependencies (key packages)

| Purpose | Package |
|---|---|
| AI / LLM | `openai` |
| Speech-to-Text | `faster-whisper` |
| Voice Activity Detection | `silero-vad` (via torch.hub) |
| Wake Word | `openwakeword` |
| Text-to-Speech | `edge-tts` |
| Audio playback | `pygame` |
| Audio capture | `sounddevice` |
| Windows automation | `pyautogui` `pynput` `pygetwindow` `psutil` `pywin32` |
| Volume control | `pycaw` |
| Brightness control | `screen-brightness-control` |
| Browser automation | `playwright` |
| OCR | `pytesseract` `easyocr` |
| Computer vision | `opencv-python` `pillow` |
| Document reading | `pymupdf` `python-docx` `openpyxl` |
| Database | `sqlalchemy[asyncio]` `aiosqlite` |
| Vector memory | `chromadb` `sentence-transformers` |
| GUI | `PySide6` |
| Config | `pydantic-settings` |
| Logging | `loguru` |

Full pinned list: [`requirements.txt`](requirements.txt)

---

## Troubleshooting

**Sarku doesn't hear me**
- Check your default microphone in Windows Sound Settings
- Run `python -c "import sounddevice; print(sounddevice.query_devices())"` to list devices
- Set a specific device index in `.env`: `MICROPHONE_DEVICE=1`

**Speech recognition is slow**
- Set `STT_MODEL=tiny.en` for fastest (less accurate) or `STT_DEVICE=cuda` with a GPU

**No voice output**
- Confirm `edge-tts` is installed: `pip install edge-tts`
- Ensure your speakers/headphones are set as default playback device

**"OpenAI API key not set"**
- Add `OPENAI_API_KEY=sk-...` to your `.env` file
- Sarku still works in stub mode without a key (limited responses)

**Tesseract not found**
- Install from https://github.com/UB-Mannheim/tesseract/wiki
- Update `TESSERACT_PATH` in `.env` to match the install location

**Wake word not triggering**
- OpenWakeWord models download automatically on first run (~50 MB)
- Fallback mode works immediately via transcript matching
- Speak clearly — "Hey Sarku" with a natural pause after

---

## License

MIT — free to use, modify, and distribute.

---

*Built with Python 3.10+, OpenAI, faster-whisper, edge-tts, Silero VAD, PySide6, Playwright, and a lot of asyncio.*

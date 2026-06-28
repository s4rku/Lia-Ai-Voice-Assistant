# Lia — AI Voice Assistant for Windows

> A Jarvis-like desktop AI companion. Listens continuously, understands natural language,
> speaks with a realistic voice, and controls your entire Windows PC.

---

## What Lia Can Do

| Category | Capabilities |
|---|---|
| **Conversation** | Natural fluid dialogue, short-term + long-term memory, context awareness, follow-up questions |
| **Wake Word** | Offline detection — say *"Hey Lia"*, *"Lia"*, or *"Hello Lia"* |
| **Voice** | Microsoft Edge neural TTS, interruptible mid-sentence, streaming playback |
| **Speech Recognition** | faster-whisper (Whisper model), Silero VAD, continuous listening |
| **Apps** | Open, close, kill, switch, minimize, maximize any Windows application |
| **System** | Volume, brightness, shutdown, restart, sleep, lock, CMD, PowerShell |
| **Files** | Create, delete, move, copy, rename, zip, extract, search, read PDFs/Word/Excel |
| **Browser** | Chrome/Edge/Firefox — open URLs, Google search, tabs, YouTube, Gmail, Discord |
| **Vision** | Screenshot, OCR, find & click text on screen, GPT-4o screen description |
| **AI Brain** | OpenAI GPT-4o-mini, streaming responses, context-aware, fact extraction |
| **Memory** | SQLite (sessions, history, facts, preferences) + ChromaDB (semantic recall) |
| **GUI** | Floating animated orb, conversation history, system stats, dark/light theme, tray icon |
| **Safety** | Confirmation required for dangerous actions (delete, shutdown, PowerShell, etc.) |
| **Plugins** | Extensible architecture — add any capability as a plugin |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Windows 10 / 11** | Required |
| **Python 3.10+** | 3.12 recommended — [Download](https://python.org) |
| **OpenAI API Key** | [Get one here](https://platform.openai.com/api-keys) — Lia works in stub mode without it |
| **Tesseract OCR** | For screen reading — [Download](https://github.com/UB-Mannheim/tesseract/wiki) |
| **FFmpeg** | For audio processing — [Download](https://ffmpeg.org/download.html) |
| **Microphone** | Any microphone works |
| **CUDA GPU** | Optional — makes speech recognition 5–10× faster |

---

## Installation

### One-command setup

```bat
setup.bat
```

This creates a virtual environment, installs all dependencies, and copies `.env.example` → `.env`.

### Manual setup

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and add your API key:

```env
OPENAI_API_KEY=sk-...
```

---

## Running Lia

```bat
.venv\Scripts\activate
python -m assistant.main
```

A floating window appears with the animated orb. Say one of the wake words:

- **"Hey Lia"**
- **"Lia"**
- **"Hello Lia"**

To stop listening: say *"Goodbye"*, *"Sleep"*, or *"That's all"*.

---

## Configuration

All settings live in `.env`. No code changes needed.

```env
# ── Identity ──────────────────────────────────────────────────────────────────
ASSISTANT_NAME=Lia
USER_NAME=Boss

# ── Wake words (comma-separated) ──────────────────────────────────────────────
WAKE_WORDS=hey lia,lia,hello lia

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
You:  "Hey Lia"
Lia:  "Yes?"
You:  "Open Spotify and set the volume to 60%"
Lia:  "Done — Spotify is launching and I've set the volume to 60%."

You:  "Lia, search YouTube for lofi hip hop"
Lia:  "Opening that now."

You:  "My PC is running slow"
Lia:  "Your CPU is at 91% — Chrome is the main culprit.
       Want me to close it?"

You:  "What's on my screen right now?"
Lia:  "I can see VS Code open with a Python file called main.py..."

You:  "I need to send a message to John on Discord"
Lia:  "Opening Discord Web now. What would you like to say to John?"

You:  "Shutdown the PC"
Lia:  "Are you sure you want to shutdown? Say yes or no."
You:  "Yes"
Lia:  "Shutting down."

You:  "Goodbye"
Lia:  "Going quiet. Say my name when you need me."
```

---

## Project Structure

```
Lia AI Voice Assistant/
├── assistant/
│   ├── main.py               Entry point — boots everything, bridges Qt ↔ asyncio
│   ├── config/
│   │   ├── settings.py       All config via pydantic-settings + .env
│   │   └── logging_setup.py  Loguru — colourised console + rotating log file
│   ├── core/
│   │   ├── events.py         Async pub/sub event bus (all modules talk through this)
│   │   └── types.py          Shared types: Message, Role, AssistantState
│   ├── database/
│   │   ├── db.py             Async SQLAlchemy + aiosqlite, WAL mode
│   │   └── models.py         ConversationSession, ChatMessage, UserPreference,
│   │                         CommandHistory, KnowledgeFact
│   ├── system/
│   │   └── health.py         Background CPU/RAM/disk/battery/network monitor
│   ├── plugins/
│   │   └── base.py           Plugin ABC + PluginManager (register/dispatch)
│   ├── audio/
│   │   ├── microphone.py     sounddevice async stream → AudioFrame queue
│   │   └── vad.py            Silero VAD state machine → Utterance events
│   ├── stt/
│   │   └── transcriber.py    faster-whisper, lazy load, thread pool
│   ├── tts/
│   │   └── speaker.py        edge-tts streaming, sentence splitting, interrupt-on-speech
│   ├── wakeword/
│   │   └── detector.py       OpenWakeWord (primary) + regex transcript fallback
│   ├── ai/
│   │   ├── brain.py          OpenAI streaming, system prompt, action extraction,
│   │   │                     auto fact extraction, stub mode
│   │   └── conversation.py   State machine: IDLE→LISTEN→THINK→SPEAK→LISTEN
│   ├── memory/
│   │   └── store.py          SQLite (sessions/facts/prefs) + ChromaDB semantic recall
│   ├── automation/
│   │   ├── dispatcher.py     Intent router with dangerous-action confirmation gate
│   │   ├── apps.py           Open/close/kill/switch/minimize/maximize apps
│   │   ├── keyboard.py       Type text, press keys, hotkeys, clipboard
│   │   ├── mouse.py          Click, drag, scroll, screenshot
│   │   ├── system_ctrl.py    Volume, brightness, power controls, CMD, PowerShell
│   │   └── file_ops.py       Create/delete/move/copy/zip/extract, read PDFs/Word/Excel
│   ├── browser/
│   │   └── controller.py     Playwright async — Chrome/Edge/Firefox,
│   │                         tabs, forms, YouTube, Gmail, Discord
│   ├── vision/
│   │   └── screen.py         Tesseract OCR, find-and-click text on screen, GPT-4o vision
│   └── gui/
│       ├── orb.py            PySide6 animated orb (pulse / spin / wave per state)
│       ├── window.py         Frameless floating window, chat history, stats bar
│       └── app.py            Qt ↔ asyncio co-runner via QTimer pump
├── tests/
│   └── unit/                 55 tests — all phases covered, all passing
├── installer/
│   ├── build.bat             PyInstaller one-file .exe build
│   ├── install.iss           Inno Setup installer script
│   └── create_icon.py        Generates lia.ico with Pillow
├── data/
│   ├── memory/               SQLite DB + ChromaDB (auto-created at runtime)
│   ├── models/               Wake word ONNX models (auto-downloaded)
│   └── screenshots/          Saved screenshots from vision/automation
├── .env.example              Configuration template — copy to .env
├── requirements.txt          All pinned dependencies
├── setup.bat                 One-command setup script
└── pyproject.toml            Build config + `lia` CLI entry point
```

---

## Architecture

```
Microphone ──► VAD ──► WakeWord ──► STT ──► ConversationLoop
                                                   │
                                              AI Brain ◄──► Memory
                                                   │         (SQLite + ChromaDB)
                                            Dispatcher
                                           /     |      \
                                     Automation  Browser  Vision
                                           \     |      /
                                              TTS Speaker ──► 🔊
                                                   │
                                             GUI (EventBus)
                                          Animated Orb + Chat Panel
```

Every module communicates through the **async EventBus** — no module imports another's internals directly.

---

## Supported Automation Intents

The AI brain emits these as JSON after its conversational reply (stripped before TTS):

```
open_app        close_app       kill_process    switch_window
minimize_window maximize_window list_windows
type_text       press_key       hotkey
clipboard_get   clipboard_set
click           double_click    right_click     move_mouse      drag        scroll
take_screenshot
set_volume      mute            set_brightness
shutdown        restart         sleep           lock
run_cmd         run_powershell
create_folder   delete_file     move_file       copy_file       rename_file
search_files    read_file       zip_files       extract_archive empty_recycle_bin
open_url        search_google   new_tab         close_tab       go_back     go_forward
play_youtube    youtube_pause   open_gmail      open_discord
browser_click   get_page_text
click_text      read_screen     describe_screen
```

Dangerous intents (`shutdown`, `restart`, `delete_file`, `run_cmd`, `run_powershell`, etc.)
always require a *"yes"* confirmation before executing.

---

## Supported App Aliases

Say the plain name — Lia resolves it to the correct executable:

`notepad` · `calculator` · `explorer` · `paint` · `word` · `excel` · `powerpoint`  
`chrome` · `firefox` · `edge` · `vscode` · `discord` · `spotify` · `steam`  
`cmd` · `powershell` · `terminal` · `obs` · `vlc` · `zoom` · `teams` · `slack`  
`task manager` · `control panel` · `settings` · `snipping tool`

---

## Adding a Plugin

```python
# assistant/plugins/my_plugin.py
from assistant.plugins.base import Plugin
from typing import Any

class SpotifyPlugin(Plugin):
    name = "spotify"
    version = "1.0.0"
    description = "Controls Spotify"
    handles = ["play_track", "pause_music", "next_track"]

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        if intent == "play_track":
            track = params.get("track", "")
            # ... control Spotify via spotipy or subprocess ...
            return {"response": f"Playing {track} on Spotify."}
        return {"response": "Done."}
```

Register it in `main.py` startup:

```python
from assistant.plugins.my_plugin import SpotifyPlugin
plugin_manager.register(SpotifyPlugin())
```

---

## Running Tests

```bat
.venv\Scripts\activate
pytest tests/ -v
```

Expected: **55 passed**

---

## Building a Standalone Executable

```bat
# Generate icon (requires Pillow)
python installer\create_icon.py

# Build Lia.exe
installer\build.bat
# Output: dist\Lia.exe

# Build Windows installer (requires Inno Setup 6)
# Compile: installer\install.iss → LiaSetup.exe
```

---

## Troubleshooting

**Lia doesn't hear me**
- Check your default microphone in Windows Sound Settings
- List devices: `python -c "import sounddevice; print(sounddevice.query_devices())"`

**Speech recognition is slow**
- Use `STT_MODEL=tiny.en` for fastest results, or set `STT_DEVICE=cuda` with an NVIDIA GPU

**No voice output**
- Confirm `edge-tts` installed: `pip install edge-tts`
- Check your default playback device in Windows Sound Settings

**"OpenAI API key not set"**
- Add `OPENAI_API_KEY=sk-...` to `.env`
- Lia still responds in stub mode without a key (time, system stats, basic replies)

**Tesseract not found**
- Install from https://github.com/UB-Mannheim/tesseract/wiki
- Update `TESSERACT_PATH` in `.env` to match your install location

**Wake word not triggering**
- OpenWakeWord models download automatically on first run (~50 MB, requires internet once)
- Fallback transcript matching works immediately without any download
- Speak naturally — *"Hey Lia"* with a brief pause

---

## Dependencies

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
| OCR | `pytesseract` |
| Document reading | `pymupdf` `python-docx` `openpyxl` |
| Database | `sqlalchemy[asyncio]` `aiosqlite` |
| Vector memory | `chromadb` `sentence-transformers` |
| GUI | `PySide6` |
| Config | `pydantic-settings` |
| Logging | `loguru` |

Full pinned list: [`requirements.txt`](requirements.txt)

---

## License

MIT — free to use, modify, and distribute.

---

*Built with Python · OpenAI · faster-whisper · edge-tts · Silero VAD · OpenWakeWord · PySide6 · Playwright · asyncio*

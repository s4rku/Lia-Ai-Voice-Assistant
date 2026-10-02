# Lia - AI Voice Assistant

A personal voice assistant I built for Windows. Kind of like Jarvis but obviously way less cool lol. You can talk to it, it talks back, and it can control your PC — open apps, manage files, browse the web, that sort of thing.

I started this project because I wanted something that actually runs locally (mostly) and doesn't require me to click through a bunch of menus. Still a work in progress but it's usable.

---

## What it can do

- **Wake word** — say "Hey Lia", "Lia", or "Hello Lia" to activate it
- **Talk to it** — it remembers context within a conversation and even across sessions
- **Open/close apps** — "open Spotify", "close Chrome", etc.
- **System controls** — volume, brightness, shutdown, sleep, lock screen
- **File stuff** — create, delete, move, copy files, read PDFs/Word/Excel
- **Browser** — open URLs, Google search, YouTube, Gmail, Discord
- **Screenshot + OCR** — it can see your screen and tell you what's on it
- **Floating GUI** — little animated orb that sits on your desktop, shows conversation history

---

## Requirements

- Windows 10 or 11
- Python 3.10+ (I use 3.12)
- OpenAI API key — it works without one in stub mode but obviously smarter with it
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) if you want screen reading
- [FFmpeg](https://ffmpeg.org/download.html) for audio
- A microphone (anything works)
- CUDA GPU is optional but makes speech recognition a lot faster

---

## Setup

Easiest way:

```bat
setup.bat
```

That handles the venv, installs dependencies, and copies `.env.example` to `.env`. Then just open `.env` and drop in your OpenAI key.

Manual if you prefer:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

---

## Running it

```bat
.venv\Scripts\activate
python -m assistant.main
```

The floating orb should show up. Say "Hey Lia" to start talking. Say "Goodbye" or "Sleep" when you're done.

---

## Config

Everything is in `.env`, no need to touch the code:

```env
ASSISTANT_NAME=Lia
USER_NAME=Boss

WAKE_WORDS=hey lia,lia,hello lia

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# tiny.en is faster, large-v3 is more accurate
STT_MODEL=base.en
STT_DEVICE=cpu   # or cuda

TTS_VOICE=en-US-GuyNeural
TTS_RATE=+10%

TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

GUI_THEME=dark
GUI_ALWAYS_ON_TOP=true
GUI_START_MINIMIZED=false

# optional
WEATHER_API_KEY=
WEATHER_CITY=London
```

---

## Some example interactions

```
You:  "Hey Lia"
Lia:  "Yes?"
You:  "Open Spotify and set volume to 60"
Lia:  "Done."

You:  "Search YouTube for lofi hip hop"
Lia:  "Opening that now."

You:  "What's on my screen?"
Lia:  "Looks like VS Code with a Python file open..."

You:  "Shutdown"
Lia:  "Are you sure? Say yes or no."
You:  "Yes"
Lia:  "Shutting down."

You:  "Goodbye"
Lia:  "Going quiet. Say my name when you need me."
```

---

## Project layout

```
assistant/
├── main.py              boots everything up
├── config/              settings from .env via pydantic
├── core/                event bus + shared types
├── audio/               microphone input + VAD
├── stt/                 faster-whisper speech to text
├── tts/                 edge-tts voice output
├── wakeword/            openwakeword + fallback detection
├── ai/                  gpt brain + conversation state machine
├── memory/              sqlite + chromadb for recall
├── automation/          apps, keyboard, mouse, files, system
├── browser/             playwright for web stuff
├── vision/              tesseract + gpt-4o screen reading
└── gui/                 pyside6 animated orb + chat window
```

---

## Running tests

```bat
.venv\Scripts\activate
pytest tests/ -v
```

Should get 55 passing.

---

## Building an exe

```bat
python installer\create_icon.py
installer\build.bat
```

Output goes to `dist\Lia.exe`. There's also an Inno Setup script in `installer\` if you want a proper installer.

---

## Troubleshooting

**Can't hear me** — check Windows Sound Settings, make sure the right mic is default

**Slow transcription** — switch to `STT_MODEL=tiny.en` or use `STT_DEVICE=cuda` if you have an Nvidia GPU

**No voice** — make sure `edge-tts` is installed and your playback device is set right

**API key error** — add it to `.env`. Stub mode still works without it for basic stuff

**Tesseract not found** — install it and update `TESSERACT_PATH` in `.env`

**Wake word not triggering** — models download on first run (~50 MB), after that should just work. Speak naturally with a small pause after "Hey Lia"

---

## Dependencies

Main ones: `openai`, `faster-whisper`, `edge-tts`, `openwakeword`, `pygame`, `sounddevice`, `pyautogui`, `playwright`, `pytesseract`, `PySide6`, `sqlalchemy`, `chromadb`

Full list in `requirements.txt`.

---

## License

MIT

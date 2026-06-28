# lia – AI Voice Assistant for Windows

> A Jarvis-like desktop AI companion that listens, speaks, and controls your PC.

---

## Quick Start

### Prerequisites
- Python 3.12+
- Windows 10/11
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for vision features)
- [FFmpeg](https://ffmpeg.org/download.html) (for audio processing)
- CUDA-capable GPU (optional, improves STT speed)

### Installation

```bat
setup.bat
```

Or manually:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
:: Edit .env with your API keys
```

### Running

```bat
.venv\Scripts\activate
python -m assistant.main
```

Or after installing in editable mode:

```bat
lia
```

---

## Build Phases

| Phase | Status | Features |
|-------|--------|----------|
| 1 | ✅ Done | Project setup, config, logging, DB, event bus, plugin system |
| 2 | 🔜 Next | Wake word, microphone, STT, TTS, conversation loop |
| 3 | ⏳ | AI brain, memory, streaming responses |
| 4 | ⏳ | Windows automation (keyboard, mouse, files, apps) |
| 5 | ⏳ | Browser automation (Chrome/Edge/Firefox) |
| 6 | ⏳ | Vision – OCR, screen understanding, UI clicking |
| 7 | ⏳ | GUI – animated orb, settings panel |
| 8 | ⏳ | Optimisation, testing, packaging, installer |

---

## Project Structure

```
assistant/
├── config/         Settings, logging
├── core/           Event bus, shared types
├── database/       SQLAlchemy models, async SQLite
├── system/         System health (CPU/RAM/GPU/battery)
├── plugins/        Plugin base class and registry
├── audio/          Phase 2 – mic capture, VAD
├── stt/            Phase 2 – faster-whisper
├── tts/            Phase 2 – edge-tts streaming
├── wakeword/       Phase 2 – OpenWakeWord
├── ai/             Phase 3 – LLM brain
├── memory/         Phase 3 – short/long-term memory
├── automation/     Phase 4 – PC control
├── browser/        Phase 5 – Playwright
├── vision/         Phase 6 – CV/OCR
├── gui/            Phase 7 – PySide6 UI
└── main.py         Entry point
```

---

## Configuration

All settings live in `.env`. Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | – | Required for AI responses |
| `WAKE_WORDS` | `hey lia,lia,hello lia` | Comma-separated wake phrases |
| `TTS_VOICE` | `en-US-GuyNeural` | Edge TTS voice name |
| `STT_MODEL` | `base.en` | Whisper model size |
| `STT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `GUI_THEME` | `dark` | `dark` or `light` |
| `USER_NAME` | `Boss` | How lia addresses you |

---

## Running Tests

```bat
pytest tests/ -v
```

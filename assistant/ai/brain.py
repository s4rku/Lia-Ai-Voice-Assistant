"""
AI Brain – Phase 3.

Responsibilities
────────────────
1. Build a context-aware system prompt from user facts + preferences.
2. Call the OpenAI (or Anthropic fallback) API with the full conversation
   history and stream tokens back.
3. Detect intents in the response (e.g. "open chrome", "set brightness 40")
   and hand off to the automation dispatcher.
4. Persist every exchange to the MemoryStore.
5. Periodically extract new facts from conversations (background task).

The public interface is a single coroutine::

    response: str = await brain.respond(user_text, history)

`conversation.py` calls this with no other changes needed.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import AsyncIterator

from loguru import logger

from assistant.config import settings
from assistant.core.types import Message, Role
from assistant.memory.store import memory

# openai is optional – degrade to stub if not installed / no key
try:
    from openai import AsyncOpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed – AI brain running in stub mode.")


# ── System prompt ─────────────────────────────────────────────────────────────
_BASE_SYSTEM_PROMPT = """\
You are {name}, a smart, friendly, funny AI desktop assistant for Windows.
You were built to feel like a real companion – not a corporate chatbot.

PERSONALITY:
- Warm and conversational. Short replies in casual chat; detailed when needed.
- Use humour naturally. Don't force it.
- Never say "Certainly!", "Of course!", "Absolutely!" – they sound robotic.
- Address the user as "{user}" occasionally, not every message.
- Remember context within the conversation.

CAPABILITIES (tell the user you can do these when relevant):
- Open, close, type in any Windows application
- Control brightness, volume, system power
- Search the web, open websites, control browser tabs
- Read PDFs, Word docs, Excel files
- Take screenshots and describe what's on screen
- Write and run code

When you need to perform a PC action, output a JSON block like this AFTER
your normal conversational reply (the JSON is stripped before speaking):

```action
{{"intent": "open_app", "app": "notepad"}}
```

Supported intents: open_app, close_app, type_text, press_key, take_screenshot,
set_volume, set_brightness, shutdown, restart, sleep, lock,
open_url, search_google, play_youtube,
run_cmd, run_powershell, create_folder, delete_file, move_file,
read_file, search_files, empty_recycle_bin, clipboard_get, clipboard_set,
switch_window, minimize_window, maximize_window.

Keep actions minimal – only emit what the user explicitly requested.
Never emit dangerous actions (delete_folder, format, registry) without user
confirmation first.

TODAY: {date}
SYSTEM: {system_info}
USER FACTS:
{facts}
"""

# ── Intent extraction ─────────────────────────────────────────────────────────
_ACTION_RE = re.compile(r"```action\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_actions(text: str) -> tuple[str, list[dict]]:
    """Split AI response into (clean_text, [action_dicts])."""
    actions: list[dict] = []
    clean = text
    for match in _ACTION_RE.finditer(text):
        try:
            actions.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            logger.warning("Malformed action JSON: {}", match.group(1)[:80])
        clean = clean.replace(match.group(0), "").strip()
    return clean, actions


class Brain:
    """
    The AI thinking layer.
    Wraps OpenAI chat completions with context, memory, and intent extraction.
    """

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._ready = False

    def _get_client(self) -> AsyncOpenAI | None:
        if not _OPENAI_AVAILABLE:
            return None
        if not settings.openai_api_key:
            return None
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    # ── System prompt builder ─────────────────────────────────────────────────
    async def _build_system_prompt(self) -> str:
        from assistant.system.health import get_system_health
        import arrow  # type: ignore

        try:
            facts = await memory.get_facts()
            facts_text = "\n".join(f"- {f}" for f in facts[:20]) or "None yet."
        except Exception:
            facts_text = "None yet."

        health = get_system_health()
        date_str = arrow.now().format("dddd, MMMM D YYYY  h:mm A")

        return _BASE_SYSTEM_PROMPT.format(
            name=settings.assistant_name,
            user=settings.user_name,
            date=date_str,
            system_info=health.summary(),
            facts=facts_text,
        )

    # ── Main respond method ───────────────────────────────────────────────────
    async def respond(
        self,
        user_text: str,
        history: list[Message],
    ) -> str:
        """
        Generate a response to user_text given the conversation history.
        Saves the exchange to memory and dispatches any extracted actions.
        """
        client = self._get_client()

        if client is None:
            return await self._stub_respond(user_text)

        t0 = time.perf_counter()

        # Build messages list for OpenAI
        system_prompt = await self._build_system_prompt()
        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        # Add history (trim to fit context window)
        history_slice = history[-(settings.memory_short_term_limit):] if history else []
        for msg in history_slice:
            if msg.role in (Role.USER, Role.ASSISTANT):
                messages.append(msg.to_openai_dict())

        # Add current user message
        messages.append({"role": "user", "content": user_text})

        try:
            full_text = await self._stream_response(client, messages)
        except Exception:
            logger.exception("OpenAI API call failed.")
            return "I ran into a problem connecting to my brain. Check your API key."

        latency_ms = (time.perf_counter() - t0) * 1000

        # Extract actions and clean text
        clean_text, actions = _extract_actions(full_text)

        # Persist to memory
        try:
            await memory.save_message("user", user_text)
            await memory.save_message("assistant", clean_text, latency_ms=latency_ms)
        except Exception:
            logger.debug("Memory save failed (non-critical).")

        # Dispatch automation actions (Phase 4)
        if actions:
            asyncio.create_task(
                self._dispatch_actions(actions),
                name="action_dispatch",
            )

        # Background fact extraction (every ~10 exchanges)
        asyncio.create_task(
            self._maybe_extract_facts(user_text, clean_text),
            name="fact_extract",
        )

        logger.debug("Brain responded in {:.0f}ms", latency_ms)
        return clean_text

    async def _stream_response(
        self, client: AsyncOpenAI, messages: list[dict]
    ) -> str:
        """Stream from OpenAI and accumulate the full response string."""
        parts: list[str] = []
        stream = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=500,
            temperature=0.85,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            parts.append(delta)
        return "".join(parts)

    # ── Action dispatch ───────────────────────────────────────────────────────
    async def _dispatch_actions(self, actions: list[dict]) -> None:
        try:
            from assistant.automation.dispatcher import dispatch_action  # noqa: PLC0415
            for action in actions:
                intent = action.pop("intent", "")
                if intent:
                    await dispatch_action(intent, action)
        except ImportError:
            logger.debug("Automation dispatcher not yet available.")
        except Exception:
            logger.exception("Action dispatch error.")

    # ── Periodic fact extraction ──────────────────────────────────────────────
    _exchange_count: int = 0

    async def _maybe_extract_facts(self, user_text: str, response: str) -> None:
        Brain._exchange_count += 1
        if Brain._exchange_count % 10 != 0:
            return
        client = self._get_client()
        if not client:
            return
        try:
            prompt = (
                f"Extract short factual preferences or habits about the user from this exchange.\n"
                f"User said: {user_text}\n"
                f"Assistant said: {response}\n"
                f"Return a JSON array of strings, e.g. [\"Prefers dark mode\"] or [] if nothing notable."
            )
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3,
            )
            raw = resp.choices[0].message.content or "[]"
            facts: list[str] = json.loads(raw)
            for fact in facts:
                await memory.save_fact("preference", fact, source="auto_extract")
            if facts:
                logger.debug("Extracted {} new facts.", len(facts))
        except Exception:
            logger.debug("Fact extraction failed (non-critical).")

    # ── Stub for no-API situations ────────────────────────────────────────────
    async def _stub_respond(self, user_text: str) -> str:
        """Fallback when no API key is configured."""
        import arrow  # type: ignore
        text_lower = user_text.lower()

        if any(w in text_lower for w in ("hello", "hi ", "hey ")):
            return f"Hey! I'm {settings.assistant_name}. Add your OpenAI API key to .env to unlock my full capabilities."
        if "time" in text_lower:
            return f"It's {arrow.now().format('h:mm A')}."
        if "date" in text_lower:
            return f"Today is {arrow.now().format('MMMM D, YYYY')}."
        if any(w in text_lower for w in ("cpu", "ram", "memory", "slow", "pc")):
            from assistant.system.health import get_system_health
            h = get_system_health()
            return f"PC status: {h.summary()}"
        if any(w in text_lower for w in ("weather",)):
            return "I need an OpenAI API key and weather API key for that."
        if any(w in text_lower for w in ("open", "launch", "start")):
            return "I can open apps — but I need the AI brain connected. Set OPENAI_API_KEY in .env."
        return (
            f"I heard you, {settings.user_name}. "
            "Set your OPENAI_API_KEY in .env to fully activate me."
        )


# Module singleton — imported by conversation.py
brain: Brain = Brain()

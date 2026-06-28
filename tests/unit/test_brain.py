"""
Unit tests for the AI Brain (stub mode – no real API calls).
"""
import pytest
from assistant.ai.brain import Brain, _extract_actions
from assistant.core.types import Message, Role


def test_extract_actions_none():
    text = "Hello, how can I help you?"
    clean, actions = _extract_actions(text)
    assert clean == text
    assert actions == []


def test_extract_actions_single():
    text = 'Sure! ```action\n{"intent": "open_app", "app": "notepad"}\n``` Opening now.'
    clean, actions = _extract_actions(text)
    assert "```action" not in clean
    assert len(actions) == 1
    assert actions[0]["intent"] == "open_app"
    assert actions[0]["app"] == "notepad"


def test_extract_actions_multiple():
    text = (
        "Done!\n"
        "```action\n{\"intent\": \"set_volume\", \"level\": 50}\n```\n"
        "```action\n{\"intent\": \"open_app\", \"app\": \"spotify\"}\n```"
    )
    clean, actions = _extract_actions(text)
    assert len(actions) == 2
    intents = {a["intent"] for a in actions}
    assert "set_volume" in intents
    assert "open_app" in intents


def test_extract_actions_malformed_json():
    """Malformed JSON should be skipped without raising."""
    text = "```action\n{broken json}\n```"
    clean, actions = _extract_actions(text)
    assert actions == []


@pytest.mark.asyncio
async def test_stub_respond_hello():
    brain = Brain()
    resp = await brain._stub_respond("hello there")
    assert settings_name_in_resp(resp)


@pytest.mark.asyncio
async def test_stub_respond_time():
    brain = Brain()
    resp = await brain._stub_respond("what time is it")
    assert ":" in resp  # time format contains ':'


@pytest.mark.asyncio
async def test_stub_respond_no_key():
    """With no API key, respond() falls back to stub."""
    brain = Brain()
    resp = await brain.respond("hi", history=[])
    assert isinstance(resp, str)
    assert len(resp) > 0


def settings_name_in_resp(resp: str) -> bool:
    from assistant.config import settings
    return settings.assistant_name.lower() in resp.lower() or "api" in resp.lower()

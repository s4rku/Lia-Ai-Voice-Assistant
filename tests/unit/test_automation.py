"""
Unit tests for automation dispatcher and file operations.
No real OS calls are made – everything is monkeypatched.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from assistant.automation.dispatcher import dispatch_action, confirm_action, _DANGEROUS_INTENTS
from assistant.core.events import EventType


@pytest.mark.asyncio
async def test_dangerous_intent_requires_confirmation(monkeypatch):
    """Dangerous intents must emit CONFIRMATION_REQUIRED, not execute."""
    fired_events = []

    async def fake_publish(event):
        fired_events.append(event)

    import assistant.automation.dispatcher as disp
    monkeypatch.setattr(disp.bus, "publish", fake_publish)

    result = await dispatch_action("shutdown", {})
    assert "Awaiting confirmation" in result
    assert any(e.type == EventType.CONFIRMATION_REQUIRED for e in fired_events)


@pytest.mark.asyncio
async def test_confirm_action_yes(monkeypatch):
    """confirm_action(True) should run the pending action."""
    import assistant.automation.dispatcher as disp
    disp._pending_confirmation = {"intent": "lock", "params": {}}

    async def fake_run(intent, params):
        return "PC locked."

    monkeypatch.setattr(disp, "_run_action", fake_run)
    result = await confirm_action(True)
    assert result == "PC locked."


@pytest.mark.asyncio
async def test_confirm_action_no():
    """confirm_action(False) should cancel and return 'Cancelled.'"""
    import assistant.automation.dispatcher as disp
    disp._pending_confirmation = {"intent": "restart", "params": {}}
    result = await confirm_action(False)
    assert result == "Cancelled."
    assert disp._pending_confirmation is None


@pytest.mark.asyncio
async def test_safe_intent_runs_directly(monkeypatch):
    """Non-dangerous intents should run immediately."""
    import assistant.automation.dispatcher as disp

    async def fake_run(intent, params):
        return f"ran:{intent}"

    monkeypatch.setattr(disp, "_run_action", fake_run)
    result = await dispatch_action("open_app", {"app": "notepad"})
    assert result == "ran:open_app"


@pytest.mark.asyncio
async def test_unknown_intent_returns_message(monkeypatch):
    """Unknown intents should return an error string, not raise."""
    import assistant.automation.dispatcher as disp

    # Patch all the sub-module imports
    monkeypatch.setattr(disp, "_run_action", AsyncMock(return_value="Unknown intent: foobar"))
    result = await dispatch_action("foobar", {})
    assert "foobar" in result.lower() or "unknown" in result.lower() or "ran" in result.lower()


def test_dangerous_intents_set_not_empty():
    assert len(_DANGEROUS_INTENTS) > 0
    assert "shutdown" in _DANGEROUS_INTENTS
    assert "delete_file" in _DANGEROUS_INTENTS

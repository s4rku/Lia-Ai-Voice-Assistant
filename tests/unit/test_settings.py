"""
Unit tests for the Settings class.
"""
import pytest
from assistant.config.settings import Settings


def test_default_assistant_name():
    s = Settings()
    assert s.assistant_name == "lia"


def test_default_wake_words():
    s = Settings()
    assert "lia" in s.wake_words


def test_wake_words_parsed_from_string():
    s = Settings(wake_words="hey lia, lia, hello lia")  # type: ignore[arg-type]
    assert s.wake_words == ["hey lia", "lia", "hello lia"]


def test_stt_device_default():
    s = Settings()
    assert s.stt_device == "cpu"


def test_gui_theme_default():
    s = Settings()
    assert s.gui_theme == "dark"

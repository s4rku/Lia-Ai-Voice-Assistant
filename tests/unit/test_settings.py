"""
Unit tests for the Settings class.
"""
import pytest
from assistant.config.settings import Settings


def test_default_assistant_name():
    s = Settings()
    assert s.assistant_name == "Lia"


def test_default_wake_words():
    s = Settings()
    assert "lia" in s.wake_word_list


def test_wake_words_parsed_from_string():
    s = Settings(wake_words="hey lia, lia, hello lia")
    assert s.wake_word_list == ["hey lia", "lia", "hello lia"]


def test_stt_device_default():
    # Device may be overridden by .env; just check it's a valid value
    s = Settings()
    assert s.stt_device in ("cpu", "cuda")


def test_gui_theme_default():
    s = Settings()
    assert s.gui_theme == "dark"

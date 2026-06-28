"""
Shared data-types used across every module.
Keep this file free from third-party imports so it loads instantly.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

if sys.version_info >= (3, 11):
    from enum import auto, StrEnum
else:
    from enum import auto
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: Role
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_dict(self) -> dict[str, str]:
        return {"role": str(self.role), "content": self.content}


class AssistantState(StrEnum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    THINKING = auto()
    SPEAKING = auto()
    EXECUTING = auto()
    WAITING_CONFIRMATION = auto()
    ERROR = auto()

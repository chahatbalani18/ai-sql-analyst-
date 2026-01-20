# src/memory.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class ConversationState:
    last_question: str = ""
    last_sql: str = ""
    last_safe_sql: str = ""
    last_result_columns: Optional[list[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ConversationState":
        return ConversationState(
            last_question=d.get("last_question", ""),
            last_sql=d.get("last_sql", ""),
            last_safe_sql=d.get("last_safe_sql", ""),
            last_result_columns=d.get("last_result_columns", None),
        )

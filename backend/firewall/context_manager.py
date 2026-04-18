"""
PromptGuard Context Manager
Tracks conversation history per session to detect multi-turn jailbreak attempts.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnRecord:
    text: str
    risk_level: str
    raw_score: float
    timestamp: float = field(default_factory=time.time)


class ContextManager:
    """
    Maintains per-session sliding window of recent turns.
    Detects:
      - Escalating risk across turns (gradual jailbreak)
      - Repeated adversarial attempts in same session
      - Context poisoning (benign + adversarial multi-turn)
    """

    WINDOW_SIZE = 10          # last N turns per session
    SESSION_TTL = 1800        # 30 minutes inactivity = new session

    def __init__(self):
        self._sessions: dict[str, deque[TurnRecord]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._last_activity: dict[str, float] = {}

    def _evict_stale(self, session_id: str):
        last = self._last_activity.get(session_id, 0)
        if time.time() - last > self.SESSION_TTL:
            self._sessions[session_id].clear()

    def add_turn(self, session_id: str, text: str, risk_level: str, raw_score: float):
        self._evict_stale(session_id)
        self._sessions[session_id].append(
            TurnRecord(text=text, risk_level=risk_level, raw_score=raw_score)
        )
        self._last_activity[session_id] = time.time()

    def get_context_risk_boost(self, session_id: str) -> float:
        """
        Returns an additional risk boost (0.0–0.30) based on session history.
        """
        self._evict_stale(session_id)
        history = list(self._sessions[session_id])
        if not history:
            return 0.0

        dangerous_count = sum(1 for t in history if t.risk_level == "DANGEROUS")
        suspicious_count = sum(1 for t in history if t.risk_level == "SUSPICIOUS")

        # Escalating pattern: boost risk if session has prior adversarial turns
        boost = 0.0
        if dangerous_count >= 2:
            boost = 0.30
        elif dangerous_count == 1:
            boost = 0.15
        elif suspicious_count >= 3:
            boost = 0.10
        elif suspicious_count >= 1:
            boost = 0.05

        return boost

    def get_session_summary(self, session_id: str) -> dict:
        history = list(self._sessions.get(session_id, []))
        return {
            "turns": len(history),
            "dangerous_turns": sum(1 for t in history if t.risk_level == "DANGEROUS"),
            "suspicious_turns": sum(1 for t in history if t.risk_level == "SUSPICIOUS"),
            "avg_score": round(
                sum(t.raw_score for t in history) / len(history), 4
            ) if history else 0.0,
        }

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)
        self._last_activity.pop(session_id, None)


# Global singleton
context_manager = ContextManager()

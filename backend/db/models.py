"""
PromptGuard ORM Models
"""

from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=True)
    original_prompt: Mapped[str] = mapped_column(Text)
    sanitized_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20))   # SAFE | SUSPICIOUS | DANGEROUS
    action: Mapped[str] = mapped_column(String(20))        # ALLOW | SANITIZE | BLOCK
    raw_score: Mapped[float] = mapped_column(Float)
    ml_score: Mapped[float] = mapped_column(Float)
    rule_score: Mapped[float] = mapped_column(Float)
    attack_category: Mapped[str] = mapped_column(String(60), nullable=True)
    matched_rules: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list
    explanation: Mapped[str] = mapped_column(Text, nullable=True)
    llm_response: Mapped[str] = mapped_column(Text, nullable=True)
    context_boost: Mapped[float] = mapped_column(Float, default=0.0)
    model_used: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "original_prompt": self.original_prompt,
            "sanitized_prompt": self.sanitized_prompt,
            "risk_level": self.risk_level,
            "action": self.action,
            "raw_score": self.raw_score,
            "ml_score": self.ml_score,
            "rule_score": self.rule_score,
            "attack_category": self.attack_category,
            "matched_rules": self.matched_rules,
            "explanation": self.explanation,
            "llm_response": self.llm_response,
            "context_boost": self.context_boost,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

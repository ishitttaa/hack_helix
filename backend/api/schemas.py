"""
PromptGuard Pydantic Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Prompt to analyze")
    session_id: Optional[str] = Field(None, description="Session ID for context tracking")


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None)
    llm_model: Optional[str] = Field("mock", description="LLM model to use: 'mock' or 'openai'")


class FirewallDecision(BaseModel):
    risk_level: str
    action: str
    raw_score: float
    ml_score: float
    rule_score: float
    attack_category: Optional[str]
    matched_rules: list[str]
    explanation: str
    confidence: float
    context_boost: float
    model_used: bool


class AnalyzeResponse(BaseModel):
    original_prompt: str
    sanitized_prompt: Optional[str]
    firewall: FirewallDecision
    was_sanitized: bool
    modifications: list[str]
    request_id: Optional[int]


class ChatResponse(BaseModel):
    original_prompt: str
    processed_prompt: Optional[str]
    firewall: FirewallDecision
    llm_response: Optional[str]
    blocked: bool
    request_id: Optional[int]


class StatsResponse(BaseModel):
    total_requests: int
    blocked: int
    suspicious: int
    safe: int
    block_rate: float
    attack_categories: dict
    recent_risk_scores: list[float]
    model_accuracy_note: str


class LogEntry(BaseModel):
    id: int
    session_id: Optional[str]
    original_prompt: str
    risk_level: str
    action: str
    raw_score: float
    attack_category: Optional[str]
    explanation: Optional[str]
    timestamp: Optional[str]

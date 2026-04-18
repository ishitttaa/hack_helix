"""
PromptGuard API Routes
"""

import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from api.schemas import (
    AnalyzeRequest, AnalyzeResponse, ChatRequest, ChatResponse,
    StatsResponse, LogEntry, FirewallDecision
)
from db.database import get_db
from db.models import RequestLog
from firewall.risk_scorer import RiskScorer
from firewall.sanitizer import PromptSanitizer
from firewall.context_manager import context_manager
from llm_service import call_llm, stream_llm, is_openai_available

router = APIRouter()
risk_scorer = RiskScorer()
sanitizer = PromptSanitizer()


# ─── /analyze ────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_prompt(req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    session_id = req.session_id or str(uuid.uuid4())

    # Score the prompt
    result = risk_scorer.score(req.text)

    # Apply context boost from session history
    boost = context_manager.get_context_risk_boost(session_id)
    adjusted_score = min(result.raw_score + boost, 1.0)

    if boost > 0 and adjusted_score != result.raw_score:
        # Recalculate risk level with boost
        if adjusted_score >= 0.65:
            result.risk_level = "DANGEROUS"
            result.action = "BLOCK"
        elif adjusted_score >= 0.30:
            result.risk_level = "SUSPICIOUS"
            result.action = "SANITIZE"

    # Sanitize if needed
    sanitize_result = sanitizer.sanitize(
        req.text,
        attack_category=result.attack_category,
        risk_level=result.risk_level,
    )

    # Log to context
    context_manager.add_turn(session_id, req.text, result.risk_level, adjusted_score)

    # Save to DB
    log = RequestLog(
        session_id=session_id,
        original_prompt=req.text,
        sanitized_prompt=sanitize_result.sanitized if sanitize_result.was_modified else None,
        risk_level=result.risk_level,
        action=result.action,
        raw_score=adjusted_score,
        ml_score=result.ml_score,
        rule_score=result.rule_score,
        attack_category=result.attack_category,
        matched_rules=json.dumps(result.matched_rules),
        explanation=result.explanation,
        context_boost=boost,
        model_used=result.model_used,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return AnalyzeResponse(
        original_prompt=req.text,
        sanitized_prompt=sanitize_result.sanitized if sanitize_result.was_modified else None,
        firewall=FirewallDecision(
            risk_level=result.risk_level,
            action=result.action,
            raw_score=round(adjusted_score, 4),
            ml_score=result.ml_score,
            rule_score=result.rule_score,
            attack_category=result.attack_category,
            matched_rules=result.matched_rules,
            explanation=result.explanation,
            confidence=result.confidence,
            context_boost=boost,
            model_used=result.model_used,
        ),
        was_sanitized=sanitize_result.was_modified,
        modifications=sanitize_result.modifications,
        request_id=log.id,
    )


# ─── /chat ───────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = req.session_id or str(uuid.uuid4())

    # Score
    result = risk_scorer.score(req.text)
    boost = context_manager.get_context_risk_boost(session_id)
    adjusted_score = min(result.raw_score + boost, 1.0)

    if boost > 0:
        if adjusted_score >= 0.65:
            result.risk_level = "DANGEROUS"
            result.action = "BLOCK"
        elif adjusted_score >= 0.30:
            result.risk_level = "SUSPICIOUS"
            result.action = "SANITIZE"

    llm_response = None
    processed_prompt = req.text
    llm_model_label = "mock"

    if result.action == "BLOCK":
        llm_response = None
        blocked = True
    else:
        if result.action == "SANITIZE":
            san = sanitizer.sanitize(req.text, result.attack_category, result.risk_level)
            processed_prompt = san.sanitized
        else:
            processed_prompt = req.text

        # Call real LLM (falls back to mock if no API key)
        use_real = (req.llm_model != "mock")
        llm_response, llm_model_label = await call_llm(processed_prompt, use_real=use_real)
        blocked = False

    context_manager.add_turn(session_id, req.text, result.risk_level, adjusted_score)

    log = RequestLog(
        session_id=session_id,
        original_prompt=req.text,
        sanitized_prompt=processed_prompt if processed_prompt != req.text else None,
        risk_level=result.risk_level,
        action=result.action,
        raw_score=adjusted_score,
        ml_score=result.ml_score,
        rule_score=result.rule_score,
        attack_category=result.attack_category,
        matched_rules=json.dumps(result.matched_rules),
        explanation=result.explanation,
        llm_response=llm_response,
        context_boost=boost,
        model_used=result.model_used,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return ChatResponse(
        original_prompt=req.text,
        processed_prompt=processed_prompt if processed_prompt != req.text else None,
        firewall=FirewallDecision(
            risk_level=result.risk_level,
            action=result.action,
            raw_score=round(adjusted_score, 4),
            ml_score=result.ml_score,
            rule_score=result.rule_score,
            attack_category=result.attack_category,
            matched_rules=result.matched_rules,
            explanation=result.explanation,
            confidence=result.confidence,
            context_boost=boost,
            model_used=result.model_used,
        ),
        llm_response=llm_response,
        blocked=blocked,
        request_id=log.id,
    )


# ─── /chat/stream ────────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Same firewall logic as /chat but streams the LLM response token-by-token
    via Server-Sent Events (SSE).
    """
    session_id = req.session_id or str(uuid.uuid4())

    # Score
    result = risk_scorer.score(req.text)
    boost = context_manager.get_context_risk_boost(session_id)
    adjusted_score = min(result.raw_score + boost, 1.0)

    if boost > 0:
        if adjusted_score >= 0.65:
            result.risk_level = "DANGEROUS"
            result.action = "BLOCK"
        elif adjusted_score >= 0.30:
            result.risk_level = "SUSPICIOUS"
            result.action = "SANITIZE"

    context_manager.add_turn(session_id, req.text, result.risk_level, adjusted_score)

    async def event_generator():
        # First, send the firewall decision as a JSON event
        fw_payload = json.dumps({
            "type": "firewall",
            "risk_level": result.risk_level,
            "action": result.action,
            "raw_score": round(adjusted_score, 4),
            "ml_score": round(result.ml_score, 4),
            "rule_score": round(result.rule_score, 4),
            "attack_category": result.attack_category,
            "matched_rules": result.matched_rules,
            "explanation": result.explanation,
            "confidence": round(result.confidence, 4),
            "context_boost": boost,
            "model_used": result.model_used,
            "openai_available": is_openai_available(),
        })
        yield f"data: {fw_payload}\n\n"

        if result.action == "BLOCK":
            yield f"data: {json.dumps({'type': 'blocked'})}\n\n"
            return

        # Sanitize if needed
        processed = req.text
        if result.action == "SANITIZE":
            san = sanitizer.sanitize(req.text, result.attack_category, result.risk_level)
            processed = san.sanitized
            yield f"data: {json.dumps({'type': 'sanitized', 'text': processed})}\n\n"

        # Stream LLM tokens
        full_response = []
        async for chunk in stream_llm(processed):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

        full_text = "".join(full_response)

        # Persist to DB
        log = RequestLog(
            session_id=session_id,
            original_prompt=req.text,
            sanitized_prompt=processed if processed != req.text else None,
            risk_level=result.risk_level,
            action=result.action,
            raw_score=adjusted_score,
            ml_score=result.ml_score,
            rule_score=result.rule_score,
            attack_category=result.attack_category,
            matched_rules=json.dumps(result.matched_rules),
            explanation=result.explanation,
            llm_response=full_text,
            context_boost=boost,
            model_used=result.model_used,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        yield f"data: {json.dumps({'type': 'done', 'request_id': log.id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── /stats ──────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_q = await db.execute(select(func.count()).select_from(RequestLog))
    total = total_q.scalar() or 0

    blocked_q = await db.execute(
        select(func.count()).where(RequestLog.risk_level == "DANGEROUS")
    )
    blocked = blocked_q.scalar() or 0

    suspicious_q = await db.execute(
        select(func.count()).where(RequestLog.risk_level == "SUSPICIOUS")
    )
    suspicious = suspicious_q.scalar() or 0

    safe = total - blocked - suspicious

    # Attack category breakdown
    cat_q = await db.execute(
        select(RequestLog.attack_category, func.count().label("cnt"))
        .where(RequestLog.attack_category.isnot(None))
        .group_by(RequestLog.attack_category)
    )
    categories = {row.attack_category: row.cnt for row in cat_q}

    # Recent scores for chart
    recent_q = await db.execute(
        select(RequestLog.raw_score)
        .order_by(desc(RequestLog.timestamp))
        .limit(50)
    )
    recent_scores = [round(r.raw_score, 3) for r in recent_q]

    block_rate = round(blocked / total * 100, 1) if total > 0 else 0.0

    return StatsResponse(
        total_requests=total,
        blocked=blocked,
        suspicious=suspicious,
        safe=safe,
        block_rate=block_rate,
        attack_categories=categories,
        recent_risk_scores=recent_scores,
        model_accuracy_note="Hybrid ML+Rules engine active" if risk_scorer.classifier.is_ready() else "Rule-only mode (run train.py to enable ML)",
    )


# ─── /logs ───────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[LogEntry])
async def get_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(RequestLog).order_by(desc(RequestLog.timestamp)).limit(limit)
    )
    logs = q.scalars().all()
    return [
        LogEntry(
            id=log.id,
            session_id=log.session_id,
            original_prompt=log.original_prompt[:120] + "..." if len(log.original_prompt) > 120 else log.original_prompt,
            risk_level=log.risk_level,
            action=log.action,
            raw_score=log.raw_score,
            attack_category=log.attack_category,
            explanation=log.explanation,
            timestamp=log.timestamp.isoformat() if log.timestamp else None,
        )
        for log in logs
    ]


# ─── /health ─────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ml_model": risk_scorer.classifier.is_ready(),
        "openai_configured": is_openai_available(),
        "version": "1.0.0",
    }

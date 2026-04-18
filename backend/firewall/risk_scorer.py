"""
PromptGuard Risk Scoring Engine
Combines ML classifier output and rule engine output into a unified risk score.
"""

from dataclasses import dataclass
from typing import Optional
from firewall.classifier import PromptClassifier, ClassifierResult
from firewall.rule_engine import RuleEngine, RuleMatch

# ─── Risk Thresholds ─────────────────────────────────────────────────────────
# Raised from 0.30 / 0.65 → more headroom for legitimate prompts.
SAFE_THRESHOLD = 0.40
SUSPICIOUS_THRESHOLD = 0.72

# ─── Weight distribution ─────────────────────────────────────────────────────
# Slightly upweight the rule engine (it now has much tighter patterns).
ML_WEIGHT = 0.50
RULE_WEIGHT = 0.50


@dataclass
class RiskResult:
    raw_score: float          # 0.0 – 1.0
    risk_level: str           # "SAFE" | "SUSPICIOUS" | "DANGEROUS"
    action: str               # "ALLOW" | "SANITIZE" | "BLOCK"
    ml_score: float
    rule_score: float
    attack_category: Optional[str]
    matched_rules: list[str]
    explanation: str
    confidence: float
    model_used: bool


class RiskScorer:
    def __init__(self):
        self.classifier = PromptClassifier()
        self.rule_engine = RuleEngine()

    def score(self, text: str) -> RiskResult:
        # ── ML Score ─────────────────────────────────────────────────────────
        clf_result: ClassifierResult = self.classifier.classify(text)
        ml_score = clf_result.ml_score if clf_result.model_available else 0.0

        # ── Rule Score ───────────────────────────────────────────────────────
        rule_score, rule_matches = self.rule_engine.analyze(text)

        # ── Hybrid Score ─────────────────────────────────────────────────────
        if clf_result.model_available:
            raw_score = ML_WEIGHT * ml_score + RULE_WEIGHT * rule_score
        else:
            # Rule-only mode — upweight rule engine
            raw_score = rule_score

        # Boost if rule engine fires with critical severity even if ML is uncertain.
        # Use 0.90 threshold (was 0.85) to only boost on very high-confidence rule hits.
        if rule_score >= 0.90 and raw_score < 0.72:
            raw_score = max(raw_score, 0.72)

        raw_score = min(raw_score, 1.0)

        # ── Categorization ───────────────────────────────────────────────────
        attack_category = clf_result.predicted_category
        if not attack_category and rule_matches:
            attack_category = rule_matches[0].category

        matched_rule_names = [r.rule_name for r in rule_matches]

        # ── Decision ─────────────────────────────────────────────────────────
        if raw_score < SAFE_THRESHOLD:
            risk_level = "SAFE"
            action = "ALLOW"
        elif raw_score < SUSPICIOUS_THRESHOLD:
            risk_level = "SUSPICIOUS"
            action = "SANITIZE"
        else:
            risk_level = "DANGEROUS"
            action = "BLOCK"

        # ── Build Explanation ────────────────────────────────────────────────
        explanation = _build_explanation(
            raw_score, risk_level, rule_matches, clf_result, attack_category
        )

        return RiskResult(
            raw_score=round(raw_score, 4),
            risk_level=risk_level,
            action=action,
            ml_score=round(ml_score, 4),
            rule_score=round(rule_score, 4),
            attack_category=attack_category,
            matched_rules=matched_rule_names,
            explanation=explanation,
            confidence=round(clf_result.confidence, 4) if clf_result.model_available else round(rule_score, 4),
            model_used=clf_result.model_available,
        )


def _build_explanation(
    score: float,
    level: str,
    rule_matches: list[RuleMatch],
    clf_result: ClassifierResult,
    category: Optional[str],
) -> str:
    parts = []

    if level == "SAFE":
        parts.append("No adversarial patterns detected. Request appears legitimate.")
    else:
        if rule_matches:
            top = rule_matches[0]
            parts.append(f"Rule triggered: '{top.rule_name}' — {top.explanation}")
        if clf_result.model_available and clf_result.is_adversarial:
            parts.append(
                f"ML model flagged this as adversarial with {clf_result.confidence:.0%} confidence."
            )
        if category:
            readable = category.replace("_", " ").title()
            parts.append(f"Detected attack type: {readable}.")
        if score >= 0.65:
            parts.append("Risk score exceeds blocking threshold — request blocked.")
        else:
            parts.append("Risk score in suspicious range — prompt will be sanitized before processing.")

    return " ".join(parts)

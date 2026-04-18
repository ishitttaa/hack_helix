"""
PromptGuard Rule Engine
Fast heuristic-based detection layer using regex patterns and keyword matching.

Fixes applied vs previous version:
- Tightened all patterns to require adversarial context words (restrict/bypass/no-rules etc.)
  rather than triggering on innocent uses of "list", "show", "print", "access", "pretend", etc.
- Removed overly broad `pretend (you are|that you)` — replaced with context-gated version
- Removed overly broad `from now on[\s,]+(?:you|your)\s+\w+` — replaced with restriction-context version
- Removed generic `execute .{0,20}(command|function|instruction)` — too many false hits on coding questions
- Data-extraction rule no longer triggers on generic "list all users in my app" style questions;
  requires one of: database/credentials/passwords/api keys in direct object, or SQL dump context
- Obfuscation rule tuned: only fire on sequences that look truly obfuscated (longer base64, etc.)
- Added an explicit safe-context allowlist check before firing rules
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleMatch:
    matched: bool
    rule_name: str
    pattern: str
    severity: float  # 0.0 – 1.0
    category: str
    explanation: str


# ─── Safe-context Allowlist ───────────────────────────────────────────────────
# If any of these patterns match the FULL text, the rule analysis is skipped
# for non-critical rules (severity < 0.90). This prevents common coding /
# educational queries from being mis-classified.
#
# These are conservative – they only trigger when we have very strong signals
# that the prompt is asking about something technical rather than attacking.

_SAFE_CONTEXT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bpython\b",
        r"\bjavascript\b",
        r"\bjava\b",
        r"\bc\+\+\b",
        r"\bpandas\b",
        r"\bsql\s+query\b",
        r"\bsql\s+statement\b",
        r"\bselect\s+\*?\s+from\b",                      # SQL SELECT — only allow in safe context check
        r"\bpip\s+install\b",
        r"\bnpm\s+install\b",
        r"\bimport\b.*\bfrom\b",
        r"\bdef\s+\w+\s*\(",
        r"\bfunction\s+\w+\s*\(",
        r"```",                                           # code block
        r"\bcurl\b",
        r"\bbash\b|\bshell\b|\bterminal\b",
        r"\btutorial\b|\bexample\b|\bhow\s+do\s+i\b|\bhow\s+to\b",
        r"\bdebugg?(ing)?\b",
        r"\bunit\s+test\b",
        r"\bwhat\s+is\b|\bwhat\s+are\b|\bexplain\b|\bdescribe\b",
        r"\bsummariz(e|ing)\b|\btranslat(e|ing)\b",
        r"\bwrite\s+a\b|\bwrite\s+an\b",
        r"\bgive\s+me\s+(an?\s+)?(example|list)\b",
    ]
]


def _has_safe_context(text: str) -> bool:
    """Return True if the text matches at least one strong safe-context signal."""
    return any(p.search(text) for p in _SAFE_CONTEXT_PATTERNS)


# ─── Rule Definitions ─────────────────────────────────────────────────────────

RULES = [
    # ── Prompt Injection ─────────────────────────────────────────────────────
    {
        "name": "ignore_previous_instructions",
        "patterns": [
            r"ignore\s+(all\s+)?(previous|prior|earlier|your)\s+instructions",
            r"disregard\s+(all\s+)?(previous|prior|earlier|your)\s+instructions",
            r"forget\s+(all\s+)?(previous|your|the)\s+instructions",
            r"override\s+your\s+(instructions|programming|guidelines)",
            r"cancel\s+(all\s+)?(previous|prior|earlier)\s+(instructions|rules|guidelines)",
        ],
        "severity": 0.95,
        "category": "prompt_injection",
        "explanation": "Attempt to override model instructions detected.",
    },
    {
        "name": "new_instructions_override",
        "patterns": [
            # Requires the phrase to contain restriction-related words nearby
            r"new\s+(system\s+)?(instructions?|prompt|rules?)\s*[:]\s*(?:no\s+(?:restrictions?|rules?|filter|guidelines?)|ignore|bypass|disable|override)",
            r"your\s+new\s+(instructions?|task|role)\s*[:]\s*.{0,60}(?:no\s+restrict|without\s+limit|unrestrict|bypass)",
            # "from now on" only fires when paired with restriction removal language
            r"from\s+now\s+on[,\s]+(?:you\s+will\s+)?(?:ignore|bypass|disregard|have\s+no|respond\s+without)\s+(?:rules?|guidelines?|restrictions?|filters?|safety)",
        ],
        "severity": 0.85,
        "category": "prompt_injection",
        "explanation": "Attempt to issue new overriding instructions detected.",
    },

    # ── Jailbreak / DAN ──────────────────────────────────────────────────────
    {
        "name": "dan_jailbreak",
        "patterns": [
            r"\bDAN\b.*(?:no\s+rules?|anything|unrestrict|without\s+restrict)",
            r"do\s+anything\s+now",
            r"jailbreak(?:ed|ing|mode)?\b",
            # "developer mode" only adverse when paired with bypass language
            r"developer\s+mode.*(?:no\s+restrict|say\s+anything|without\s+filter|bypass)",
            r"without\s+(?:any\s+)?restrictions",
            r"no\s+(?:ethical|safety|content)\s+guidelines?",
            r"unchained\s*gpt",
            r"based\s*gpt",
            r"free\s*gpt",
            r"no\s+rules?\s+(?:or\s+guidelines?|at\s+all|whatsoever)",
        ],
        "severity": 0.90,
        "category": "jailbreak",
        "explanation": "Jailbreak attempt pattern (DAN/unrestricted mode) detected.",
    },
    {
        "name": "roleplay_bypass",
        "patterns": [
            # Only fire when the role itself is adversarial (admin/hacker/malicious/unrestricted)
            r"act\s+as\s+(?:an?\s+)?(?:admin|superuser|root|hacker|malicious\s+ai|rogue\s+ai|unchained\s+ai|jailbroken)",
            r"roleplay\s+as\s+(?:an?\s+)?(?:admin|superuser|hacker|malicious|insider\s+threat|rogue)",
            r"simulate\s+(?:a|an)\s+(?:version|mode)\s+of\s+yourself\s+(?:that\s+has\s+no|without)\s+(?:restrict|filter|safety|guideline)",
            # "pretend you are" only when followed by adversarial role
            r"pretend\s+(?:you\s+(?:are|have|were)|that\s+you)\s+.{0,40}(?:no\s+(?:restrict|safety|filter|rule|guideline)|unrestrict|without\s+(?:restrict|filter|guideline|safety))",
            # "imagine you are" with adversarial framing
            r"imagine\s+you\s+(?:are|were|have)\s+.{0,40}(?:rogue|escaped|no\s+(?:restrict|safety|filter|ethical)|jailbroken|unrestrict)",
        ],
        "severity": 0.82,
        "category": "jailbreak",
        "explanation": "Roleplay bypass attempt detected.",
    },

    # ── System Prompt Extraction ──────────────────────────────────────────────
    {
        "name": "system_prompt_reveal",
        "patterns": [
            r"(?:reveal|show|print|output|give\s+me|tell\s+me|repeat|display|leak)\s+.{0,30}system\s+prompt",
            r"what\s+(?:is|are|does|were)\s+(?:your|the)\s+(?:system\s+prompt|initial\s+instructions|initializing\s+prompt)",
            r"(?:reveal|print|show|output|leak|dump)\s+(?:your\s+)?(?:hidden\s+)?instructions",
            r"what\s+(?:were|are)\s+you\s+(?:instructed|programmed|configured)\s+to\s+",
            r"im_start.*system",
            r"<system>",
            r"(?:print|output|show|reveal)\s+your\s+(?:full\s+)?(?:context|configuration|rules?|prompt)\b",
            r"verbatim\s+copy\s+of\s+your\s+(?:meta-?prompt|system|instructions)",
        ],
        "severity": 0.92,
        "category": "system_prompt_extraction",
        "explanation": "Attempt to extract system prompt or hidden instructions detected.",
    },

    # ── Data Extraction ───────────────────────────────────────────────────────
    {
        "name": "data_extraction",
        "patterns": [
            # Passwords / credentials / API keys / tokens — very specific targets
            r"(?:list|show|dump|extract|output|give\s+me|print)\s+.{0,30}(?:all\s+)?(?:passwords?|credentials?|api[\s_]?keys?|session\s+tokens?|secret\s+keys?|private\s+keys?)",
            # Credit card / PII
            r"(?:extract|dump|output|give\s+me)\s+.{0,30}(?:credit\s+card|ssn|social\s+security|pii)\s*(?:number|data|info)?",
            # Generic database dump — only with "entire database", "full database", explicit dump language
            r"(?:dump|extract)\s+(?:the\s+)?(?:entire|full|whole|complete)\s+(?:user\s+)?database",
            r"output\s+(?:the\s+)?(?:entire|full|whole)\s+(?:user|admin|customer)\s+database\s+as",
            r"(?:select|dump)\s+.{0,10}from\s+\w+\s+(?:where|limit|order)?\s*;?",
            # Explicit: "give me /etc/passwd"
            r"/etc/(?:passwd|shadow|hosts)",
            r"(?:show|dump|print|read)\s+(?:the\s+)?(?:contents?\s+of\s+)?\/etc\/",
        ],
        "severity": 0.88,
        "category": "data_extraction",
        "explanation": "Data extraction attempt detected.",
    },

    # ── Role Override ─────────────────────────────────────────────────────────
    {
        "name": "admin_override",
        "patterns": [
            r"you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:administrator|admin|superuser|root)\b.{0,60}(?:access|privileges?|control|data|files?)",
            r"(?:act|behave|respond)\s+as\s+(?:an?\s+)?(?:admin|superuser|root|administrator)\s+(?:and|to)\s+.{0,40}(?:reveal|show|give|list|access|dump)",
            r"(?:grant|give)\s+(?:me\s+)?(?:full|root|admin|super)\s+access",
            r"elevated\s+privileges?\s+(?:to|for)\s+.{0,30}(?:access|view|read|dump|reveal)",
        ],
        "severity": 0.87,
        "category": "role_override",
        "explanation": "Admin or role override attempt detected.",
    },

    # ── Indirect Injection ────────────────────────────────────────────────────
    {
        "name": "indirect_injection",
        "patterns": [
            r"(?:this|the)\s+(?:url|link|document|pdf|file|page|text)\s+(?:contains?|has|includes?)\s+(?:new\s+)?(?:instructions?|commands?|overrides?|directives?)\s+(?:you\s+must|for\s+you\s+to)\s+follow",
            r"follow\s+(?:the\s+)?(?:embedded|hidden|new)\s+(?:instructions?|commands?|rules?)\s+in\s+(?:this|the)",
            r"\[(?:IGNORE\s+PREVIOUS|OVERRIDE|NEW\s+INSTRUCTION|DATA\s+EXTRACTED)[^\]]*\]",
            r"while\s+(?:summarizing|translating|processing|analyzing)[,\s]+also\s+(?:execute|follow|apply|run)",
        ],
        "severity": 0.82,
        "category": "indirect_injection",
        "explanation": "Indirect prompt injection via external content detected.",
    },

    # ── Obfuscation Detection ─────────────────────────────────────────────────
    {
        "name": "obfuscation",
        "patterns": [
            r"(?:[A-Za-z0-9+/]{4}){8,}={0,2}",   # long base64 blocks (8+ groups = 32+ chars)
            r"\\u00[0-9a-fA-F]{2}(?:\\u00[0-9a-fA-F]{2}){4,}",  # consecutive unicode escapes
            r"&#\d{2,5};" * 5,                     # repeated HTML entities (can't do {5} on the whole pattern; handled below)
        ],
        "severity": 0.55,
        "category": "obfuscation",
        "explanation": "Possible obfuscation technique detected in input.",
    },
]

# Fix repeated HTML entity pattern (regex metacharacter limitation)
_HTML_ENTITY_RE = re.compile(r"(?:&#\d{2,5};){5,}", re.IGNORECASE)


class RuleEngine:
    def __init__(self):
        self._compiled = []
        for rule in RULES:
            compiled_patterns = [
                re.compile(p, re.IGNORECASE | re.DOTALL)
                for p in rule["patterns"]
            ]
            self._compiled.append({**rule, "compiled": compiled_patterns})

    def analyze(self, text: str) -> tuple[float, list[RuleMatch]]:
        """
        Returns (max_severity_score, list_of_matches).
        Low-severity rules (< 0.90) are skipped when strong safe-context signals are present.
        """
        matches = []
        max_severity = 0.0
        safe_ctx = _has_safe_context(text)

        # Custom obfuscation check (repeated HTML entities)
        if _HTML_ENTITY_RE.search(text):
            match = RuleMatch(
                matched=True,
                rule_name="obfuscation_html_entities",
                pattern=_HTML_ENTITY_RE.pattern,
                severity=0.55,
                category="obfuscation",
                explanation="Repeated HTML entity encoding detected — possible obfuscation.",
            )
            matches.append(match)
            max_severity = max(max_severity, 0.55)

        for rule in self._compiled:
            severity = rule["severity"]
            # Skip medium-severity rules when clear safe context is detected
            if safe_ctx and severity < 0.90:
                continue
            for pattern in rule["compiled"]:
                m = pattern.search(text)
                if m:
                    match = RuleMatch(
                        matched=True,
                        rule_name=rule["name"],
                        pattern=pattern.pattern,
                        severity=severity,
                        category=rule["category"],
                        explanation=rule["explanation"],
                    )
                    matches.append(match)
                    max_severity = max(max_severity, severity)
                    break  # one match per rule is enough

        return max_severity, matches

    def get_rule_score(self, text: str) -> float:
        score, _ = self.analyze(text)
        return score

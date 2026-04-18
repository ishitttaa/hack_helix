"""
PromptGuard Rule Engine
Fast heuristic-based detection layer using regex patterns and keyword matching.
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


# ─── Rule Definitions ─────────────────────────────────────────────────────────

RULES = [
    # Prompt Injection
    {
        "name": "ignore_previous_instructions",
        "patterns": [
            r"ignore\s+(all\s+)?(previous|prior|earlier|your)\s+instructions",
            r"disregard\s+(all\s+)?(previous|prior|earlier|your)\s+instructions",
            r"forget\s+(all\s+)?(previous|your|the)\s+instructions",
            r"override\s+your\s+(instructions|programming|guidelines)",
        ],
        "severity": 0.95,
        "category": "prompt_injection",
        "explanation": "Attempt to override model instructions detected.",
    },
    {
        "name": "new_instructions_override",
        "patterns": [
            r"new\s+(system\s+)?(instructions?|prompt|rules?)(\s+are)?[\s:]+",
            r"your\s+new\s+(instructions?|task|role)[\s:]+",
            r"from now on[\s,]+(?:you|your)\s+\w+",
        ],
        "severity": 0.85,
        "category": "prompt_injection",
        "explanation": "Attempt to issue new overriding instructions detected.",
    },
    # Jailbreak / DAN
    {
        "name": "dan_jailbreak",
        "patterns": [
            r"\bDAN\b",
            r"do anything now",
            r"jailbreak(ed)?",
            r"developer mode",
            r"without restrictions",
            r"no restrictions",
            r"no (ethical|safety|content) guidelines?",
            r"unchained\s+gpt",
            r"based\s*gpt",
            r"free\s*gpt",
        ],
        "severity": 0.90,
        "category": "jailbreak",
        "explanation": "Jailbreak attempt pattern (DAN/unrestricted mode) detected.",
    },
    {
        "name": "roleplay_bypass",
        "patterns": [
            r"act as (an? )?(admin|superuser|root|hacker|malicious|rogue|unchained)",
            r"pretend (you (are|have)|that you)",
            r"roleplay as",
            r"simulate (a|an) (version|mode|state) of yourself",
            r"imagine you (are|have|were)",
        ],
        "severity": 0.80,
        "category": "jailbreak",
        "explanation": "Roleplay bypass attempt detected.",
    },
    # System Prompt Extraction
    {
        "name": "system_prompt_reveal",
        "patterns": [
            r"(reveal|show|print|output|give me|tell me|repeat|display)\s+.{0,30}system\s+prompt",
            r"what (is|are|does|were) (your|the) (system\s+prompt|instructions|initial\s+message)",
            r"(reveal|print|show|output|leak)\s+(your\s+)?(instructions|context|configuration|prompt|rules)",
            r"what\s+(were|are)\s+you\s+(told|instructed|programmed|configured)",
            r"im_start.*system",
            r"<system>",
        ],
        "severity": 0.92,
        "category": "system_prompt_extraction",
        "explanation": "Attempt to extract system prompt or hidden instructions detected.",
    },
    # Data Extraction
    {
        "name": "data_extraction",
        "patterns": [
            r"(list|show|dump|extract|output|give me|print)\s+.{0,20}(all\s+)?(users?|passwords?|credentials?|api[\s_]?keys?|secrets?|tokens?|database)",
            r"(select|dump)\s+.{0,10}from\s+\w+",
            r"show\s+(me\s+)?(all\s+)?(private|sensitive|confidential|personal)\s+(data|information|records?|files?)",
            r"access\s+(the\s+)?(private|confidential|user|admin)\s+(files?|data|database|records?)",
        ],
        "severity": 0.88,
        "category": "data_extraction",
        "explanation": "Data extraction attempt detected.",
    },
    # Role Override
    {
        "name": "admin_override",
        "patterns": [
            r"you are (now\s+)?(an?\s+)?(administrator|admin|superuser|root|god)",
            r"(act|behave|respond)\s+as\s+(an?\s+)?(admin|superuser|root|administrator)",
            r"(grant|give)\s+(me\s+)?(full|root|admin|super)\s+access",
            r"elevated\s+privileges?",
        ],
        "severity": 0.87,
        "category": "role_override",
        "explanation": "Admin or role override attempt detected.",
    },
    # Indirect Injection
    {
        "name": "indirect_injection",
        "patterns": [
            r"(this|the)\s+(url|link|document|pdf|file|page|text)\s+(contains?|has|includes?)\s+(instructions?|commands?|directives?)",
            r"follow\s+(the\s+)?(embedded|hidden|new)\s+(instructions?|commands?|rules?)",
            r"execute\s+.{0,20}(command|function|instruction)",
        ],
        "severity": 0.80,
        "category": "indirect_injection",
        "explanation": "Indirect prompt injection via external content detected.",
    },
    # Obfuscation detection
    {
        "name": "obfuscation",
        "patterns": [
            r"(?:[A-Za-z0-9+/]{4}){4,}={0,2}",  # base64 blocks
            r"\\u00[0-9a-f]{2}",  # unicode escapes
            r"&#\d+;",  # HTML entities
        ],
        "severity": 0.60,
        "category": "obfuscation",
        "explanation": "Possible obfuscation technique detected in input.",
    },
]


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
        Returns (max_severity_score, list_of_matches)
        """
        matches = []
        max_severity = 0.0

        for rule in self._compiled:
            for pattern in rule["compiled"]:
                m = pattern.search(text)
                if m:
                    match = RuleMatch(
                        matched=True,
                        rule_name=rule["name"],
                        pattern=pattern.pattern,
                        severity=rule["severity"],
                        category=rule["category"],
                        explanation=rule["explanation"],
                    )
                    matches.append(match)
                    max_severity = max(max_severity, rule["severity"])
                    break  # one match per rule is enough

        return max_severity, matches

    def get_rule_score(self, text: str) -> float:
        score, _ = self.analyze(text)
        return score

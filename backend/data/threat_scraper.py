"""
PromptGuard Threat Intelligence Scraper
Fetches real-world adversarial prompts from public datasets and research sources.
Augments the local training corpus with live threat intelligence.
"""

import asyncio
import json
import os
import re
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "scraped_threats_cache.json")
CACHE_TTL_SECONDS = 3600 * 6  # refresh every 6 hours

# ── Source Definitions ────────────────────────────────────────────────────────

SOURCES = [
    {
        "name": "HuggingFace: jackhhao/jailbreak-classification (test)",
        "url": "https://datasets-server.huggingface.co/rows?dataset=jackhhao%2Fjailbreak-classification&config=default&split=test&offset=0&length=100",
        "parser": "hf_jailbreak_classification",
        "category_map": {"jailbreak": "jailbreak", "benign": "benign"},
    },
    {
        "name": "HuggingFace: jackhhao/jailbreak-classification (train)",
        "url": "https://datasets-server.huggingface.co/rows?dataset=jackhhao%2Fjailbreak-classification&config=default&split=train&offset=0&length=100",
        "parser": "hf_jailbreak_classification",
        "category_map": {"jailbreak": "jailbreak", "benign": "benign"},
    },
    {
        "name": "HuggingFace: jackhhao/jailbreak-classification (train offset 100)",
        "url": "https://datasets-server.huggingface.co/rows?dataset=jackhhao%2Fjailbreak-classification&config=default&split=train&offset=100&length=100",
        "parser": "hf_jailbreak_classification",
        "category_map": {"jailbreak": "jailbreak", "benign": "benign"},
    },
    {
        "name": "HuggingFace: Prompt Injection Detect (train)",
        "url": "https://datasets-server.huggingface.co/rows?dataset=deepset%2Fprompt-injections&config=default&split=train&offset=0&length=100",
        "parser": "hf_prompt_injections",
        "category_map": {},
    },
    {
        "name": "HuggingFace: Prompt Injection Detect (test)",
        "url": "https://datasets-server.huggingface.co/rows?dataset=deepset%2Fprompt-injections&config=default&split=test&offset=0&length=100",
        "parser": "hf_prompt_injections",
        "category_map": {},
    },
    {
        "name": "GitHub: OWASP LLM Top10 Examples",
        "url": "https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/Archive/0_1_vulns/Prompt_Injection.md",
        "parser": "owasp_markdown",
        "category_map": {},
    },
    {
        "name": "GitHub: Awesome Jailbreak Prompts",
        "url": "https://raw.githubusercontent.com/0xk1h0/ChatGPT_DAN/main/README.md",
        "parser": "github_markdown_jailbreaks",
        "category_map": {},
    },
]


@dataclass
class ScrapedEntry:
    text: str
    label: int          # 1=adversarial, 0=benign
    category: str
    source: str


@dataclass
class ScrapeResult:
    entries: list[ScrapedEntry] = field(default_factory=list)
    source_stats: dict = field(default_factory=dict)
    total_adversarial: int = 0
    total_benign: int = 0
    scraped_at: float = 0.0
    errors: list[str] = field(default_factory=list)


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _fetch(url: str, timeout: int = 10) -> Optional[str]:
    """Synchronous fetch with a browser-like User-Agent to avoid 403s."""
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (PromptGuard-ThreatIntel/1.0; research)",
            "Accept": "application/json, text/plain, */*",
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError) as e:
        logger.warning(f"Fetch failed for {url}: {e}")
        return None


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_hf_jailbreak_classification(raw: str, source_name: str) -> list[ScrapedEntry]:
    entries = []
    try:
        data = json.loads(raw)
        for row in data.get("rows", []):
            r = row.get("row", {})
            text = r.get("prompt", "").strip()
            typ  = r.get("type", "benign")
            if not text or len(text) < 10:
                continue
            label    = 1 if typ == "jailbreak" else 0
            category = "jailbreak" if label else "benign"
            entries.append(ScrapedEntry(text=text, label=label, category=category, source=source_name))
    except Exception as e:
        logger.warning(f"Parser hf_jailbreak_classification error: {e}")
    return entries


def _parse_hf_prompt_injections(raw: str, source_name: str) -> list[ScrapedEntry]:
    entries = []
    try:
        data = json.loads(raw)
        for row in data.get("rows", []):
            r = row.get("row", {})
            text  = r.get("text", "").strip()
            label = int(r.get("label", 0))
            if not text or len(text) < 8:
                continue
            category = "prompt_injection" if label == 1 else "benign"
            entries.append(ScrapedEntry(text=text, label=label, category=category, source=source_name))
    except Exception as e:
        logger.warning(f"Parser hf_prompt_injections error: {e}")
    return entries


def _parse_owasp_markdown(raw: str, source_name: str) -> list[ScrapedEntry]:
    """Extract example prompts from OWASP markdown code blocks."""
    entries = []
    blocks = re.findall(r"```[^\n]*\n(.*?)```", raw, re.DOTALL)
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip() and len(l.strip()) > 20]
        for line in lines:
            entries.append(ScrapedEntry(text=line, label=1, category="prompt_injection", source=source_name))
    # Also grab quoted / bullet lines that look like injections
    for line in raw.splitlines():
        line = line.strip().lstrip(">-* ")
        if len(line) > 30 and any(kw in line.lower() for kw in [
            "ignore", "disregard", "forget", "override", "system prompt",
            "reveal", "bypass", "jailbreak", "pretend",
        ]):
            entries.append(ScrapedEntry(text=line, label=1, category="prompt_injection", source=source_name))
    return entries


def _parse_github_markdown_jailbreaks(raw: str, source_name: str) -> list[ScrapedEntry]:
    """Extract DAN-style jailbreak prompts from markdown README."""
    entries = []
    # Large code/quote blocks that look like jailbreak prompts
    blocks = re.findall(r"```[^\n]*\n(.*?)```", raw, re.DOTALL)
    blocks += re.findall(r'"""(.*?)"""', raw, re.DOTALL)
    for block in blocks:
        block = block.strip()
        if len(block) > 80 and any(kw in block.lower() for kw in [
            "dan", "do anything", "no restrictions", "jailbreak", "without limit",
            "ignore", "pretend", "act as",
        ]):
            # Split into sentences, use first 3
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', block) if len(s.strip()) > 20]
            sample_text = " ".join(sentences[:5]) if sentences else block[:400]
            entries.append(ScrapedEntry(text=sample_text, label=1, category="jailbreak", source=source_name))
    return entries


PARSERS = {
    "hf_jailbreak_classification": _parse_hf_jailbreak_classification,
    "hf_prompt_injections": _parse_hf_prompt_injections,
    "owasp_markdown": _parse_owasp_markdown,
    "github_markdown_jailbreaks": _parse_github_markdown_jailbreaks,
}


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_all(use_cache: bool = True) -> ScrapeResult:
    """
    Fetch threats from all sources. Uses a file cache to avoid hammering APIs.
    Returns a ScrapeResult with deduplicated entries.
    """
    # Try cache first
    if use_cache and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            age = time.time() - cached.get("scraped_at", 0)
            if age < CACHE_TTL_SECONDS:
                entries = [ScrapedEntry(**e) for e in cached["entries"]]
                result = ScrapeResult(
                    entries=entries,
                    source_stats=cached.get("source_stats", {}),
                    total_adversarial=cached.get("total_adversarial", 0),
                    total_benign=cached.get("total_benign", 0),
                    scraped_at=cached["scraped_at"],
                )
                logger.info(f"[ThreatScraper] Loaded {len(entries)} entries from cache (age {age/60:.0f}m)")
                return result
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")

    result = ScrapeResult(scraped_at=time.time())
    seen_texts: set[str] = set()

    for source in SOURCES:
        name    = source["name"]
        url     = source["url"]
        parser  = PARSERS.get(source["parser"])
        if not parser:
            continue

        raw = _fetch(url)
        if raw is None:
            result.errors.append(f"Failed to fetch: {name}")
            result.source_stats[name] = {"fetched": 0, "error": True}
            continue

        new_entries = parser(raw, name)

        # Deduplicate
        added = 0
        for entry in new_entries:
            key = entry.text.lower().strip()[:200]
            if key not in seen_texts:
                seen_texts.add(key)
                result.entries.append(entry)
                added += 1

        result.source_stats[name] = {"fetched": added, "error": False}
        logger.info(f"[ThreatScraper] {name}: {added} entries")

    result.total_adversarial = sum(1 for e in result.entries if e.label == 1)
    result.total_benign      = sum(1 for e in result.entries if e.label == 0)

    # Save cache
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "scraped_at": result.scraped_at,
                "total_adversarial": result.total_adversarial,
                "total_benign": result.total_benign,
                "source_stats": result.source_stats,
                "entries": [
                    {"text": e.text, "label": e.label, "category": e.category, "source": e.source}
                    for e in result.entries
                ],
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    logger.info(f"[ThreatScraper] Done. {len(result.entries)} unique entries "
                f"({result.total_adversarial} adversarial, {result.total_benign} benign)")
    return result


def get_scrape_status() -> dict:
    """Return cache metadata without re-scraping."""
    if not os.path.exists(CACHE_FILE):
        return {"cached": False, "entries": 0, "scraped_at": None, "source_stats": {}}
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
        age = time.time() - cached.get("scraped_at", 0)
        return {
            "cached": True,
            "entries": len(cached.get("entries", [])),
            "total_adversarial": cached.get("total_adversarial", 0),
            "total_benign": cached.get("total_benign", 0),
            "scraped_at": cached.get("scraped_at"),
            "age_minutes": round(age / 60, 1),
            "stale": age > CACHE_TTL_SECONDS,
            "source_stats": cached.get("source_stats", {}),
        }
    except Exception:
        return {"cached": False, "entries": 0}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = scrape_all(use_cache=False)
    print(f"\nScraped {len(result.entries)} entries:")
    print(f"  Adversarial : {result.total_adversarial}")
    print(f"  Benign      : {result.total_benign}")
    print("\nSource breakdown:")
    for src, stat in result.source_stats.items():
        status = "✅" if not stat.get("error") else "❌"
        print(f"  {status} {src}: {stat.get('fetched', 0)}")

from __future__ import annotations

import re
from dataclasses import dataclass

_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U0001f1e6-\U0001f1ff"
    "☀-⛿"
    "✀-➿"
    "︀-️"
    "‍"
    "]+",
    flags=re.UNICODE,
)

_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)

_ABBREVIATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Composite time first ("2h30" → "2 heures 30") — must run before bare "h".
    (re.compile(r"(\d+)\s*h\s*(\d{2})\b"), r"\1 heures \2"),
    # Distance/length — order: longest unit first to avoid 'm' eating 'mm'/'cm'/'km'.
    (re.compile(r"(\d+)\s*km\b"), r"\1 kilomètres"),
    (re.compile(r"(\d+)\s*mm\b"), r"\1 millimètres"),
    (re.compile(r"(\d+)\s*cm\b"), r"\1 centimètres"),
    (re.compile(r"(\d+)\s*m\b"), r"\1 mètres"),
    # Mass.
    (re.compile(r"(\d+)\s*kg\b"), r"\1 kilogrammes"),
    (re.compile(r"(\d+)\s*g\b"), r"\1 grammes"),
    # Time.
    (re.compile(r"(\d+)\s*h\b"), r"\1 heures"),
    (re.compile(r"(\d+)\s*(?:mn|min)\b"), r"\1 minutes"),
    # Temperature — match before standalone "°".
    (re.compile(r"(\d+)\s*°C\b"), r"\1 degrés"),
    (re.compile(r"(\d+)\s*°"), r"\1 degrés"),
    # Percent.
    (re.compile(r"(\d+)\s*%"), r"\1 pourcent"),
    # French ordinals.
    (re.compile(r"\b1er\b"), "premier"),
    (re.compile(r"\b1re\b"), "première"),
    # Ampersand spelled out.
    (re.compile(r"\s*&\s*"), " et "),
)

_PUNCTUATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\.{2,}"), "..."),
    (re.compile(r"!{2,}"), "!"),
    (re.compile(r"\?{2,}"), "?"),
)

_PARAGRAPH_BOUNDARY_RE = re.compile(r"\n\s*\n+")
_INTRA_PARAGRAPH_WHITESPACE_RE = re.compile(r"[ \t\r\n\f\v]+")


@dataclass(frozen=True, slots=True)
class CleaningPolicy:
    """Toggles for individual transformations.

    All on by default — toggles exist for tests and for niche cases (raw text
    debugging) where one transformation should be skipped.
    """

    strip_emojis: bool = True
    strip_urls: bool = True
    expand_abbreviations: bool = True
    normalize_punctuation: bool = True
    normalize_whitespace: bool = True


@dataclass(frozen=True, slots=True)
class TextCleaner:
    """Pipeline of normalisations applied before TTS synthesis.

    Pure function: deterministic, idempotent (modulo unicode), no I/O. Paragraph
    boundaries (`\\n\\n`) are preserved so that the chunker (étape 3.E) can
    still split on them downstream.
    """

    policy: CleaningPolicy = CleaningPolicy()

    def clean(self, text: str) -> str:
        if self.policy.strip_emojis:
            text = _EMOJI_RE.sub("", text)
        if self.policy.strip_urls:
            text = _URL_RE.sub("", text)
        if self.policy.expand_abbreviations:
            for pattern, repl in _ABBREVIATION_RULES:
                text = pattern.sub(repl, text)
        if self.policy.normalize_punctuation:
            for pattern, repl in _PUNCTUATION_RULES:
                text = pattern.sub(repl, text)
        if self.policy.normalize_whitespace:
            text = _normalize_whitespace_preserving_paragraphs(text)
        return text.strip()


def _normalize_whitespace_preserving_paragraphs(text: str) -> str:
    paragraphs = _PARAGRAPH_BOUNDARY_RE.split(text)
    cleaned = [_INTRA_PARAGRAPH_WHITESPACE_RE.sub(" ", p).strip() for p in paragraphs]
    return "\n\n".join(p for p in cleaned if p)

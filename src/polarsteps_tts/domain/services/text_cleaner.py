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

# List bullets — handled en trois passes :
#   1) bullet précédé d'une ligne déjà terminée par `.!?:` (avec NBSP/space
#      éventuels en queue) → on ne rajoute PAS de point sinon on aurait
#      "passage. . Option" ou "Zapala : . Option" ;
#   2) bullet précédé d'un saut de ligne sans terminateur → ". " (frontière
#      de phrase, sinon Voxtral lit "Option 1 :" comme une partie de la phrase
#      précédente et prononce "deux points" au lieu de marquer une pause) ;
#   3) bullet en tout début de texte → strip simple (pas de frontière à créer).
# Voxtral phonétise un `-` isolé comme la lettre "n" sans cette normalisation.
# `[^\S\n]` = whitespace horizontal (tab, NBSP, etc.) sans avaler le saut de ligne.
_TERMINATED_LIST_MARKER_RE = re.compile(r"([.!?:])[^\S\n]*\n[^\S\n]*[-•*][ \t]+")
_BREAKLINE_LIST_MARKER_RE = re.compile(r"\n[^\S\n]*[-•*][ \t]+")
_LEADING_LIST_MARKER_RE = re.compile(r"^[-•*][ \t]+")

# Standalone dashes used as separators ("BARILOCHE - ZAPALA", "Lima — Cuzco").
# Voxtral les prononce "n" / "tiret", brisant la lecture. Convertis en virgule
# pour préserver le rythme. Le pattern exige un espace **horizontal** des deux
# côtés (donc pas de `\n`) pour deux raisons :
#   1) les composés français (rendez-vous, semble-t-il) n'ont pas d'espace ;
#   2) les puces de liste ("\n- Option") sont gérées par `_LIST_MARKER_RE` —
#      les capter ici aussi convertirait les puces en virgules quand
#      `strip_list_markers` est désactivé.
_INLINE_DASH_RE = re.compile(r"[ \t]+[-–—]+[ \t]+")  # noqa: RUF001 (en-dash intentional)

# Mots tout-en-majuscules (4 lettres ou plus) → title-case.
# Voxtral mis-prononce ces mots ("JOUR" → "Jir", "BARILOCHE" déformé). Le
# seuil de 4 lettres protège les acronymes courts (GR, TMB, PCT, FR, etc.) qui
# ont leur propre prononciation lettre-par-lettre. Pour les "vrais" acronymes
# 4+ chars, le compromis est accepté en V1 (peu fréquents en récit voyage).
_ALL_CAPS_WORD_RE = re.compile(r"\b[A-ZÀ-Ý]{4,}\b")

# "Jour N" → "<ordinal> jour" en début de chunk. Voxtral mis-prononce un chunk
# qui démarre par "Jour 1 :" (token court + nombre, pas de contexte) en "Jir"
# ou "J O U". Convertir en ordinal écrit donne au modèle un mot pleinement
# lexicalisé. Couvre 1-30 (largement suffisant pour un récit voyage).
_DAY_HEADER_RE = re.compile(r"\bJour\s+(\d{1,2})\b", flags=re.IGNORECASE)
_FRENCH_ORDINALS: dict[int, str] = {
    1: "Premier",
    2: "Deuxième",
    3: "Troisième",
    4: "Quatrième",
    5: "Cinquième",
    6: "Sixième",
    7: "Septième",
    8: "Huitième",
    9: "Neuvième",
    10: "Dixième",
    11: "Onzième",
    12: "Douzième",
    13: "Treizième",
    14: "Quatorzième",
    15: "Quinzième",
    16: "Seizième",
    17: "Dix-septième",
    18: "Dix-huitième",
    19: "Dix-neuvième",
    20: "Vingtième",
    21: "Vingt et unième",
    22: "Vingt-deuxième",
    23: "Vingt-troisième",
    24: "Vingt-quatrième",
    25: "Vingt-cinquième",
    26: "Vingt-sixième",
    27: "Vingt-septième",
    28: "Vingt-huitième",
    29: "Vingt-neuvième",
    30: "Trentième",
}


def _expand_day_header(match: re.Match[str]) -> str:
    n = int(match.group(1))
    ordinal = _FRENCH_ORDINALS.get(n)
    if ordinal is None:
        return match.group(0)
    # Mirror the input case: "Jour" / "JOUR" → capitalised ordinal,
    # lowercase "jour" → lowercase ordinal.
    is_capitalised = match.group(0)[0].isupper()
    return f"{ordinal} jour" if is_capitalised else f"{ordinal.lower()} jour"


_ABBREVIATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Composite time first ("2h30" → "2 heures 30") — must run before bare "h".
    (re.compile(r"(\d+)\s*h\s*(\d{2})\b"), r"\1 heures \2"),
    # Speed ("80 km/h") — MUST run before bare "km" otherwise the latter eats
    # "km" and leaves "kilomètres/h" unreadable.
    (re.compile(r"(\d+)\s*km\s*/\s*h\b"), r"\1 kilomètres-heure"),
    # Distance/length — order: longest unit first to avoid 'm' eating 'mm'/'cm'/'km'.
    (re.compile(r"(\d+)\s*km\b"), r"\1 kilomètres"),
    (re.compile(r"(\d+)\s*mm\b"), r"\1 millimètres"),
    (re.compile(r"(\d+)\s*cm\b"), r"\1 centimètres"),
    (re.compile(r"(\d+)\s*m\b"), r"\1 mètres"),
    # Cycling jargon : "D+" = dénivelé positif (ascending altitude gain).
    (re.compile(r"\bD\s*\+"), "dénivelé positif"),
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
    strip_list_markers: bool = True
    normalize_inline_dashes: bool = True
    normalize_all_caps: bool = True
    expand_day_headers: bool = True
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
        if self.policy.strip_list_markers:
            # Order matters: terminator-aware rule first (avoids inserting a
            # second period/colon), then default rule, then leading strip.
            text = _TERMINATED_LIST_MARKER_RE.sub(r"\1 ", text)
            text = _BREAKLINE_LIST_MARKER_RE.sub(". ", text)
            text = _LEADING_LIST_MARKER_RE.sub("", text)
        if self.policy.normalize_inline_dashes:
            text = _INLINE_DASH_RE.sub(", ", text)
        if self.policy.normalize_all_caps:
            text = _ALL_CAPS_WORD_RE.sub(lambda m: m.group().capitalize(), text)
        if self.policy.expand_day_headers:
            text = _DAY_HEADER_RE.sub(_expand_day_header, text)
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

import os
import re
import unicodedata

from django.conf import settings


_CHARACTER_MAP = str.maketrans(
    {
        "@": "a",
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "$": "s",
    }
)


def normalize_text(value):
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    tokens = re.findall(r"[^\W_]+", without_accents.translate(_CHARACTER_MAP))
    return " ".join(re.sub(r"(.)\1{2,}", r"\1\1", token) for token in tokens)


def is_blocked(value, blocked_terms=None):
    """Match configured terms as whole words after basic obfuscation normalization."""
    if blocked_terms is None:
        blocked_terms = getattr(
            settings,
            "COMMUNICATION_BLOCKED_TERMS",
            os.environ.get("CORIDE_BLOCKED_TERMS", ""),
        )

    normalized = f" {normalize_text(value)} "
    if isinstance(blocked_terms, str):
        terms = blocked_terms.split(",")
    else:
        terms = blocked_terms or ()
    return any(
        term and f" {normalize_text(term.strip())} " in normalized
        for term in terms
    )

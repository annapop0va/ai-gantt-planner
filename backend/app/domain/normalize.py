"""Name normalization shared by import parsing, predecessor resolution and
rename validation.

Rule (product-spec + integration brief): trim edges, collapse internal
whitespace runs, casefold, and treat ё/е as equivalent — but the *original*
display value is always kept alongside the normalized key.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(value: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", value.strip())
    folded = collapsed.casefold()
    return folded.replace("ё", "е")

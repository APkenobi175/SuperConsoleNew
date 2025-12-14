from __future__ import annotations
import re

_TAGS_RE = re.compile(r"(\[[^\]]*\]|\([^)]*\))")  # [..] or (..)

def clean_title(name: str) -> str:
    name = _TAGS_RE.sub("", name)
    name = name.replace("_", " ").replace(".", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name.lower()

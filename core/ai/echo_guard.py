from __future__ import annotations

import re


TOKEN_PATTERN = re.compile(r"\b[A-Z0-9_]{12,}\b")


def _sample_substrings(value: str, *, min_len: int = 12, max_samples: int = 5) -> list[str]:
    compact = re.sub(r"\s+", "", value or "")
    if len(compact) < min_len:
        return []
    base_positions = [
        0,
        len(compact) // 4,
        len(compact) // 2,
        (len(compact) * 3) // 4,
        max(0, len(compact) - min_len),
    ]
    samples: list[str] = []
    seen: set[str] = set()
    for pos in base_positions:
        if len(samples) >= max_samples:
            break
        start = max(0, min(pos, len(compact) - min_len))
        token = compact[start : start + min_len]
        if len(token) < min_len or token in seen:
            continue
        seen.add(token)
        samples.append(token)
    return samples


def contains_sensitive_echo(input_text: str, summary: str) -> bool:
    src = input_text or ""
    out = summary or ""

    for token in TOKEN_PATTERN.findall(src):
        if token and token in out:
            return True

    summary_compact = re.sub(r"\s+", "", out)
    for snippet in _sample_substrings(src, min_len=12, max_samples=5):
        if snippet and snippet in summary_compact:
            return True

    return False

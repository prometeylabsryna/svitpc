"""Lightweight mobile/tablet detection for layout decisions."""

from __future__ import annotations

import re

_MOBILE_UA_RE = re.compile(
    r"Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile",
    re.IGNORECASE,
)


def is_mobile_user_agent(user_agent: str) -> bool:
    """True for phones/tablets — used to skip desktop-only layout in HTML."""
    return bool(user_agent and _MOBILE_UA_RE.search(user_agent))

"""Classification levels and user clearance (SEC-02, D-051).

Pure and dependency-free so every layer (schemas, services, routers) can share it. A document is
visible to a user only if the user's clearance reaches the document's classification; anything
that is not a known level, on either side, is the lowest clearance / hidden from everyone
(deny-by-default).

This is application-level access control. It does not encrypt anything and does not protect
against someone with database or storage access (CLAUDE.md #1, #4, #6).
"""

from typing import Any

# Ordered, lowest first. The index is the rank.
LEVELS: tuple[str, ...] = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET")
_RANK = {name: rank for rank, name in enumerate(LEVELS)}

DEFAULT_CLEARANCE = "PUBLIC"
# Starting points for the seed and migration scripts ONLY (never consulted at request time:
# the clearance that counts is the one stored on the user). Nobody gets TOP_SECRET by default.
PROPOSED_ROLE_CLEARANCE: dict[str, str] = {
    "ADMINISTRATOR": "INTERNAL",
    "AUTHORIZED_STAFF": "CONFIDENTIAL",
    "LEGAL_OFFICER": "RESTRICTED",
    "REVIEWING_OFFICER": "RESTRICTED",
    "AUDITOR": "RESTRICTED",
}
# What a stuck-anchor list shows instead of the title of a document the viewer cannot see.
HIDDEN_TITLE = "Restricted document"


def rank_of(level: Any) -> int | None:
    """The rank of a known level, else None (including for non-strings)."""
    return _RANK.get(level) if isinstance(level, str) else None


def effective_clearance(user: dict[str, Any]) -> str:
    """The user's clearance, or PUBLIC if it is missing or not a known level."""
    level = user.get("clearance")
    return level if rank_of(level) is not None else DEFAULT_CLEARANCE


def user_rank(user: dict[str, Any]) -> int:
    return _RANK[effective_clearance(user)]


def visible_classifications(user: dict[str, Any]) -> list[str]:
    """Every level this user may see: the filter list for queries and aggregations."""
    return list(LEVELS[: user_rank(user) + 1])


def can_see(user: dict[str, Any], classification: Any) -> bool:
    """True iff `classification` is a known level at or below the user's clearance."""
    rank = rank_of(classification)
    return rank is not None and rank <= user_rank(user)

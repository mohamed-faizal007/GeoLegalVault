"""audit module service layer.

`record()` is the one call site every lifecycle transition (Phase 6) and
every other security-relevant action uses. It is a no-op placeholder until
Phase 8 implements the real append-only `audit_logs` collection — callers
never change, only this function's body does.
"""

from typing import Any


async def record(
    *,
    actor_id: Any,
    action: str,
    target_type: str,
    target_id: Any,
    result: str = "SUCCESS",
    meta: dict[str, Any] | None = None,
) -> None:
    """Placeholder: implemented in Phase 8 (append-only audit_logs)."""
    return None

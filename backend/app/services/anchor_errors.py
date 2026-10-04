"""Safe error reporting for anchoring (D-020 in DECISIONS.md).

web3/requests errors embed the request URL, and RPC providers such as
Alchemy and Infura put the API key in the URL path. The raw exception text
therefore must never be stored in Mongo or returned by the API (Guardrail
#2). Two helpers:

- `classify_anchor_error` maps any send/RPC failure to a short fixed code —
  the only error value that is stored, audited, or returned to clients.
- `redact_secrets` masks the RPC URL (and anything shaped like a URL path or
  `/v2/<key>`) so the full detail can still be logged server-side without
  moving the leak into the logs.
"""

import re
from urllib.parse import urlparse

from app.core.config import get_settings

RPC_UNREACHABLE = "RPC_UNREACHABLE"
INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
ALREADY_ANCHORED = "ALREADY_ANCHORED"
NOT_AUTHORIZED = "NOT_AUTHORIZED"
REVERTED = "REVERTED"
NOT_CONFIGURED = "NOT_CONFIGURED"
ANCHOR_FAILED = "ANCHOR_FAILED"
# REL-01 (D-038/D-039): set by the retry worker, never by classify_anchor_error.
TX_DROPPED = "TX_DROPPED"
RETRIES_EXHAUSTED = "RETRIES_EXHAUSTED"
STORED_OBJECT_MISSING = "STORED_OBJECT_MISSING"

KNOWN_ERROR_CODES = frozenset(
    {
        RPC_UNREACHABLE,
        INSUFFICIENT_FUNDS,
        ALREADY_ANCHORED,
        NOT_AUTHORIZED,
        REVERTED,
        NOT_CONFIGURED,
        ANCHOR_FAILED,
        TX_DROPPED,
        RETRIES_EXHAUSTED,
        STORED_OBJECT_MISSING,
    }
)

_REDACTED = "<redacted>"
_MIN_SECRET_SEGMENT_LEN = 8


def classify_anchor_error(exc: BaseException) -> str:
    text = str(exc).lower()
    # Contract/chain-level reasons first: they also arrive wrapped in
    # generic "execution reverted" text.
    if "already anchored" in text:
        return ALREADY_ANCHORED
    if "not authorized" in text:
        return NOT_AUTHORIZED
    if "insufficient funds" in text:
        return INSUFFICIENT_FUNDS
    if "revert" in text:
        return REVERTED

    class_names = {cls.__name__ for cls in type(exc).__mro__}
    if "BlockchainNotConfigured" in class_names:
        return NOT_CONFIGURED
    if (
        isinstance(exc, ConnectionError | TimeoutError)
        or class_names & {"ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout"}
        or "max retries exceeded" in text
        or "connection" in text
    ):
        return RPC_UNREACHABLE
    return ANCHOR_FAILED


def public_error(stored: str | None) -> str | None:
    """What an API response may show for a stored anchor `error`. Rows
    written before D-020 hold raw exception text; those collapse to the
    generic code rather than being echoed."""
    if not stored:
        return None
    return stored if stored in KNOWN_ERROR_CODES else ANCHOR_FAILED


def _secret_fragments() -> list[str]:
    settings = get_settings()
    fragments: list[str] = []
    for url in (settings.SEPOLIA_RPC_URL, settings.CHAIN_RPC_URL):
        if not url:
            continue
        fragments.append(url)
        parsed = urlparse(url)
        for segment in parsed.path.split("/"):
            if len(segment) >= _MIN_SECRET_SEGMENT_LEN:
                fragments.append(segment)
        if parsed.query:
            fragments.append(parsed.query)
        if parsed.password:
            fragments.append(parsed.password)
    # Longest first so a full URL is masked before its own substrings.
    return sorted(set(fragments), key=len, reverse=True)


def redact_secrets(text: str) -> str:
    for fragment in _secret_fragments():
        text = text.replace(fragment, _REDACTED)
    text = re.sub(r"(url:\s*)/\S*", rf"\1/{_REDACTED}", text)
    text = re.sub(r"(https?://[^\s/'\"]+)/[^\s'\"]*", rf"\1/{_REDACTED}", text)
    return re.sub(r"/v\d+/[A-Za-z0-9_-]+", f"/v2/{_REDACTED}", text)

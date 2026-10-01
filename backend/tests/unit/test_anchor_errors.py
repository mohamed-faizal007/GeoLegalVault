"""D-020: anchor errors are stored/returned as fixed codes, and the RPC URL's
secret parts are masked before anything is logged."""

import pytest

from app.core.config import get_settings
from app.services import anchor_errors as ae
from app.services.blockchain import BlockchainNotConfigured

_KEY = "SUPERSECRETKEY123456"


@pytest.fixture(autouse=True)
def _rpc_url_with_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SEPOLIA_RPC_URL", f"https://eth-sepolia.g.alchemy.com/v2/{_KEY}")


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (Exception("execution reverted: Error: reverted with reason string 'already anchored'"),
         ae.ALREADY_ANCHORED),
        (Exception("execution reverted: not authorized"), ae.NOT_AUTHORIZED),
        (Exception("insufficient funds for gas * price + value"), ae.INSUFFICIENT_FUNDS),
        (Exception("execution reverted"), ae.REVERTED),
        (BlockchainNotConfigured("SEPOLIA_RPC_URL is not configured"), ae.NOT_CONFIGURED),
        (ConnectionError("boom"), ae.RPC_UNREACHABLE),
        (TimeoutError(), ae.RPC_UNREACHABLE),
        (Exception("HTTPSConnectionPool(host='x', port=443): Max retries exceeded"),
         ae.RPC_UNREACHABLE),
        (ValueError("something unexpected"), ae.ANCHOR_FAILED),
    ],
)
def test_classify_anchor_error(exc, code):
    assert ae.classify_anchor_error(exc) == code


def test_classify_never_echoes_the_exception_text():
    exc = ConnectionError(f"Max retries exceeded with url: /v2/{_KEY}")
    assert _KEY not in ae.classify_anchor_error(exc)


def test_public_error_passes_known_codes_and_collapses_legacy_raw_text():
    assert ae.public_error(None) is None
    assert ae.public_error("") is None
    assert ae.public_error(ae.REVERTED) == ae.REVERTED
    legacy = f"HTTPSConnectionPool(host='h', port=443): Max retries exceeded with url: /v2/{_KEY}"
    assert ae.public_error(legacy) == ae.ANCHOR_FAILED


@pytest.mark.parametrize(
    "raw",
    [
        f"HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com', port=443): "
        f"Max retries exceeded with url: /v2/{_KEY} (Caused by NewConnectionError('x'))",
        f"failed calling https://eth-sepolia.g.alchemy.com/v2/{_KEY}",
        f"bad request to https://other.example.com/rpc/{_KEY}?apikey={_KEY}",
    ],
)
def test_redact_secrets_masks_the_key_but_keeps_the_rest(raw):
    redacted = ae.redact_secrets(raw)
    assert _KEY not in redacted
    assert "<redacted>" in redacted


def test_redact_secrets_keeps_useful_non_secret_context():
    out = ae.redact_secrets(
        "HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com', port=443): "
        f"Max retries exceeded with url: /v2/{_KEY}"
    )
    assert "eth-sepolia.g.alchemy.com" in out
    assert "Max retries exceeded" in out

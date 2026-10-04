"""The retry policy table from D-038, pinned number by number. Pure function: no I/O."""

import pytest

from app.core.config import get_settings
from app.modules.blockchain.retry import next_after_failure
from app.services import anchor_errors as codes

DEFAULTS = {
    "ANCHOR_RETRY_BASE_SEC": 30.0,
    "ANCHOR_RETRY_CAP_SEC": 900.0,
    "ANCHOR_RETRY_MAX_ATTEMPTS": 8,
    "ANCHOR_REVERT_MAX_ATTEMPTS": 2,
    "ANCHOR_FUNDS_RETRY_BASE_SEC": 600.0,
    "ANCHOR_FUNDS_RETRY_CAP_SEC": 3600.0,
}


@pytest.fixture
def settings():
    return get_settings().model_copy(update=DEFAULTS)


@pytest.mark.parametrize("code", [codes.RPC_UNREACHABLE, codes.ANCHOR_FAILED, codes.TX_DROPPED])
def test_transient_codes_back_off_30_to_900_then_exhaust_after_the_8th(settings, code):
    delays = []
    for failures in range(1, 8):
        decision = next_after_failure(code, failures, settings)
        assert decision.permanent is False
        delays.append(decision.delay_sec)
    assert delays == [30, 60, 120, 240, 480, 900, 900]

    last = next_after_failure(code, 8, settings)
    assert last.permanent is True and last.reason == codes.RETRIES_EXHAUSTED


def test_insufficient_funds_has_a_long_backoff_and_its_own_exhaustion(settings):
    delays = [
        next_after_failure(codes.INSUFFICIENT_FUNDS, n, settings).delay_sec for n in range(1, 8)
    ]
    assert delays == [600, 1200, 2400, 3600, 3600, 3600, 3600]
    last = next_after_failure(codes.INSUFFICIENT_FUNDS, 8, settings)
    assert last.permanent is True and last.reason == codes.RETRIES_EXHAUSTED


def test_reverted_gets_two_attempts_then_stays_reverted(settings):
    first = next_after_failure(codes.REVERTED, 1, settings)
    assert first.permanent is False and first.delay_sec == 30
    second = next_after_failure(codes.REVERTED, 2, settings)
    assert second.permanent is True and second.reason == codes.REVERTED


@pytest.mark.parametrize(
    "code", [codes.NOT_AUTHORIZED, codes.NOT_CONFIGURED, codes.STORED_OBJECT_MISSING]
)
def test_unfixable_codes_are_permanent_on_the_first_failure(settings, code):
    decision = next_after_failure(code, 1, settings)
    assert decision.permanent is True and decision.reason == code


def test_already_anchored_is_not_decided_here_the_chain_check_decides(settings):
    decision = next_after_failure(codes.ALREADY_ANCHORED, 1, settings)
    assert decision.permanent is False and decision.delay_sec == 0


def test_new_codes_are_known_so_the_api_passes_them_through():
    for code in (codes.TX_DROPPED, codes.RETRIES_EXHAUSTED, codes.STORED_OBJECT_MISSING):
        assert code in codes.KNOWN_ERROR_CODES
        assert codes.public_error(code) == code
    assert codes.public_error("SEPOLIA_RPC_URL is not configured") == codes.ANCHOR_FAILED


def test_lease_is_longer_than_the_confirmation_timeout_by_default():
    """D-038: 900 s lease > 600 s confirmation timeout. Reads the declared defaults, not
    whatever .env or a test override says."""
    from app.core.config import Settings

    fields = Settings.model_fields
    assert fields["ANCHOR_PENDING_TIMEOUT_SEC"].default == 600
    assert fields["ANCHOR_LEASE_SEC"].default == 900
    assert fields["ANCHOR_LEASE_SEC"].default > fields["ANCHOR_PENDING_TIMEOUT_SEC"].default
    assert fields["ANCHOR_AUTO_RETRY_MAX_AGE_DAYS"].default == 7

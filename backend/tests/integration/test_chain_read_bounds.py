"""REL-04 / D-049: the on-chain read is bounded and its failures map to fixed, secret-free codes.

Chain settings are set explicitly through `chain_env`; no `.env`, no network beyond localhost.
"""

import time

import pytest

from app.services import anchor_errors
from app.services import blockchain as chain
from tests.integration.anchor_helpers import hard_timeout
from tests.integration.chain_outage_helpers import (
    NO_CODE_ADDRESS,
    SECRET,
    blackhole,
    chain_env,  # noqa: F401 (fixture)
    dead_port_url,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@hard_timeout(30)
async def test_the_onchain_read_against_a_stuck_node_is_bounded(chain_env):  # noqa: F811
    with blackhole() as stuck_url:
        chain_env(
            SEPOLIA_RPC_URL=stuck_url,
            CONTRACT_ADDRESS=NO_CODE_ADDRESS,
            CHAIN_ID=31337,
            CHAIN_READ_TIMEOUT_SEC=1,
        )
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await chain.get_onchain_anchor("doc-1", 1)
        elapsed = time.monotonic() - started
    assert elapsed < 6, f"the read took {elapsed:.1f}s with a 1s timeout"


@hard_timeout(30)
async def test_the_onchain_read_against_a_refused_port_fails_fast(chain_env):  # noqa: F811
    chain_env(
        SEPOLIA_RPC_URL=dead_port_url(),
        CONTRACT_ADDRESS=NO_CODE_ADDRESS,
        CHAIN_ID=31337,
        CHAIN_READ_TIMEOUT_SEC=5,
    )
    started = time.monotonic()
    with pytest.raises(Exception) as caught:
        await chain.get_onchain_anchor("doc-1", 1)
    assert time.monotonic() - started < 4  # no 5x retry/backoff
    assert anchor_errors.classify_chain_read_error(caught.value) == "RPC_UNREACHABLE"


def test_read_errors_map_to_fixed_codes_and_never_echo_text():
    classify = anchor_errors.classify_chain_read_error
    leaky = f"HTTPSConnectionPool(host='x', port=443): Max retries exceeded with url: /v2/{SECRET}"

    assert classify(ConnectionError(leaky)) == "RPC_UNREACHABLE"
    assert classify(chain.ChainReadTimeout("read timed out")) == "CHAIN_TIMEOUT"
    assert classify(chain.BlockchainNotConfigured("CONTRACT_ADDRESS is not configured")) == (
        "NOT_CONFIGURED"
    )
    assert classify(chain.ContractNotDeployed("no code")) == "CONTRACT_NOT_DEPLOYED"
    assert classify(ValueError(leaky)) == "CHAIN_READ_FAILED"
    for exc in (ConnectionError(leaky), ValueError(leaky)):
        assert SECRET not in classify(exc)

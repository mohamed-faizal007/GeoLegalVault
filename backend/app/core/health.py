"""Reachability probes for /api/v1/health.

These are liveness checks only (does the endpoint answer?), not functional
checks (correct credentials, deployed contract, etc.) — those land in later
phases alongside the actual storage/blockchain integrations.
"""

import httpx

_TIMEOUT_SEC = 2.0


async def check_storage(endpoint: str) -> bool:
    """True if the S3-compatible endpoint (MinIO/R2) responds at all.

    Any HTTP response (even 403/404 from an unauthenticated request) means
    the server is up; only connection failures count as unreachable.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            response = await client.get(endpoint)
            return response.status_code < 500
    except httpx.HTTPError:
        return False


async def check_chain(rpc_url: str) -> bool:
    """True if the JSON-RPC node at rpc_url answers eth_blockNumber."""
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            response = await client.post(rpc_url, json=payload)
            return response.status_code == 200 and "result" in response.json()
    except (httpx.HTTPError, ValueError):
        return False

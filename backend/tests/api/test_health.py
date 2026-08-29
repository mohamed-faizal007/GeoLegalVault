import httpx
import pytest

from app.main import app


@pytest.mark.asyncio(loop_scope="session")
async def test_health_endpoint_responds_with_expected_shape():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "mongo", "storage", "chain"}
    # Reachability depends on what's actually running locally (MinIO/Hardhat
    # may or may not be up outside docker-compose), so assert shape, not state.
    assert body["mongo"] in {"reachable", "unreachable"}
    assert body["storage"] in {"reachable", "unreachable"}
    assert body["chain"] in {"reachable", "degraded"}

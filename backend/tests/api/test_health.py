import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_responds_with_expected_shape():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "mongo", "storage", "chain"}
    assert body["storage"] == "not_configured"
    assert body["chain"] == "not_configured"

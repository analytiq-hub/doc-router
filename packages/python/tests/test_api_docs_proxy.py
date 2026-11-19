"""Swagger UI must load OpenAPI from the public /fastapi prefix behind proxies."""

from starlette.testclient import TestClient

from app.main import app


def test_swagger_uses_forwarded_prefix_for_openapi_url() -> None:
    client = TestClient(app)
    response = client.get("/docs", headers={"X-Forwarded-Prefix": "/fastapi"})
    assert response.status_code == 200
    assert "/fastapi/openapi.json" in response.text
    assert "url: '/openapi.json'" not in response.text
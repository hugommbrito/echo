"""The OpenAPI schema renders and exposes the multi-language routes."""

import pytest

pytestmark = pytest.mark.django_db


def test_schema_renders_with_language_routes(client_a):
    response = client_a.get("/api/schema/?format=json")
    assert response.status_code == 200, response.content
    paths = response.json()["paths"]
    assert "/api/v1/languages/" in paths
    assert "/api/v1/me/languages/" in paths
    assert "/api/v1/me/languages/{language}/" in paths
    assert "/api/v1/cards/{id}/audio/" in paths
    assert "/api/v1/me/ai-usage/" in paths
    assert len(paths) == 38, sorted(paths)
    stats_level = paths["/api/v1/stats/level/"]["get"]["parameters"]
    assert any(p["name"] == "language" for p in stats_level)
    advanced = {p["name"] for p in paths["/api/v1/stats/advanced/"]["get"]["parameters"]}
    assert {"from", "to", "category", "language"} <= advanced

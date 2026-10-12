"""
Integration tests for RepoScore Web Dashboard serving and static assets.
Adheres strictly to Phase 12 validation requirements.
"""

from fastapi.testclient import TestClient
from backend.api.app import create_app

client = TestClient(create_app())


def test_serve_dashboard_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RepoScore" in response.text
    assert "Autonomous Repository Intelligence" in response.text
    assert 'id="evaluation-submit-form"' in response.text


def test_serve_dashboard_explicit_route():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RepoScore" in response.text


def test_serve_static_css():
    response = client.get("/static/css/dashboard.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert "--bg-canvas" in response.text
    assert "radial-score-meter" in response.text


def test_serve_static_js():
    response = client.get("/static/js/dashboard.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "loadFinalizedResults" in response.text

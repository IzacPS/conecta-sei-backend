"""Testes de health e raiz da API (sem autenticação)."""

import pytest


class TestHealth:
    def test_root_returns_app_info(self, test_client):
        r = test_client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("name") == "AutomaSEI API"
        assert "version" in data
        assert data.get("status") == "running"

    def test_health_returns_ok(self, test_client):
        r = test_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("healthy", "degraded")
        assert "components" in data

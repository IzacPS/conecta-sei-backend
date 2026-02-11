"""Testes de autenticação (modo dev = sem token)."""

import pytest


class TestAuthDevMode:
    """Com AUTH_DEV_MODE=true, endpoints protegidos aceitam request sem Bearer."""

    def test_get_me_returns_dev_user(self, test_client):
        r = test_client.get("/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert "email" in data
        assert data["email"] == "dev@automasei.local"
        assert data.get("role") in ("user", "admin")

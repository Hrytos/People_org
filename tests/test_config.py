"""Tests for core config and validation."""

import pytest


def _reload_config(monkeypatch, **env):
    """Set env and reload src.core.config; return the module."""
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    import importlib
    import src.core.config as cfg
    importlib.reload(cfg)
    return cfg


class TestValidateConfig:
    """Test validate_config() behavior."""

    def test_validate_config_missing_key_fails(self, monkeypatch):
        cfg = _reload_config(
            monkeypatch,
            FULLENRICH_API_KEY="",
            SUPABASE_URL="",
            SUPABASE_SERVICE_KEY="",
        )
        assert cfg.validate_config() is False

    def test_validate_config_placeholder_fails(self, monkeypatch):
        cfg = _reload_config(
            monkeypatch,
            FULLENRICH_API_KEY="your_api_key_here",
            SUPABASE_URL="https://x.supabase.co",
            SUPABASE_SERVICE_KEY="sk",
        )
        assert cfg.validate_config() is False

    def test_validate_config_all_set_passes(self, monkeypatch):
        cfg = _reload_config(
            monkeypatch,
            FULLENRICH_API_KEY="real_key",
            SUPABASE_URL="https://abc.supabase.co",
            SUPABASE_SERVICE_KEY="real_service_key",
        )
        assert cfg.validate_config() is True


    def test_role_check_order_exists(self):
        from src.core.config import ROLE_CHECK_ORDER, ROLE_VALUE_KEYWORDS
        assert len(ROLE_CHECK_ORDER) >= 1
        assert all(k in ROLE_VALUE_KEYWORDS for k in ROLE_CHECK_ORDER)

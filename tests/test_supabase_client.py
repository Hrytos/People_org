"""Tests for Supabase client (unit tests only; no live DB)."""

import pytest


class TestEnsureMetadataDict:
    """Test _ensure_metadata_dict helper (used by _contact_to_row)."""

    def test_dict_passthrough(self):
        from src.db.supabase_client import _ensure_metadata_dict
        d = {"a": 1, "b": "x"}
        assert _ensure_metadata_dict(d) == d

    def test_json_string_parsed(self):
        from src.db.supabase_client import _ensure_metadata_dict
        import json
        d = {"source": "fullenrich"}
        assert _ensure_metadata_dict(json.dumps(d)) == d

    def test_empty_string_returns_empty_dict(self):
        from src.db.supabase_client import _ensure_metadata_dict
        assert _ensure_metadata_dict("") == {}
        assert _ensure_metadata_dict(None) == {}


class TestContactToRow:
    """Test _contact_to_row mapping (no DB). Uses mock so no real Supabase needed."""

    @pytest.fixture
    def db_client(self, monkeypatch):
        """Create SupabaseClient with mocked create_client."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        mock_client = object()
        from unittest.mock import patch
        # create_client is used inside __init__ via "from supabase import create_client"
        with patch("supabase.create_client", return_value=mock_client):
            from src.db.supabase_client import SupabaseClient
            return SupabaseClient()

    def test_contact_to_row_full(self, db_client):
        row = db_client._contact_to_row({
            "email": "test@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "company_name": "Acme",
            "account_id": None,
            "full_name": "Jane Doe",
            "job_title": "CTO",
            "metadata": {"source": "fullenrich"},
        })
        assert row["email"] == "test@example.com"
        assert row["first_name"] == "Jane"
        assert row["company_name"] == "Acme"
        assert row["metadata"] == {"source": "fullenrich"}
        assert "updated_at" in row

    def test_contact_to_row_uses_account_fallback(self, db_client):
        row = db_client._contact_to_row({
            "email": "a@b.com",
            "account": "Fallback Co",
            "metadata": {"k": "v"},
        })
        assert row["email"] == "a@b.com"
        assert row["company_name"] == "Fallback Co"
        assert row["metadata"] == {"k": "v"}

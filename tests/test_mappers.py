"""Tests for FullEnrich mappers."""

import pytest
from src.fullenrich.mappers import CompanyMapper, PeopleMapper, EnrichmentMapper


class TestCompanyMapper:
    """Test CompanyMapper.map_company."""

    def test_map_company_basic(self):
        data = {
            "id": "c1",
            "name": "Anthropic",
            "domain": "anthropic.com",
            "headcount": 150,
            "linkedin_url": "https://linkedin.com/company/anthropic",
        }
        out = CompanyMapper.map_company(data, "Anthropic")
        assert out["name"] == "Anthropic"
        assert out["domain"] == "anthropic.com"
        assert out["fullenrich_company_id"] == "c1"
        assert out["company_name_input"] == "Anthropic"
        assert "id" in out and len(out["id"]) == 36

    def test_map_company_minimal(self):
        data = {"id": "x", "name": "X"}
        out = CompanyMapper.map_company(data, "X")
        assert out["name"] == "X"
        assert out["domain"] == ""
        assert out["employee_count"] is None


class TestPeopleMapper:
    """Test PeopleMapper.map_person."""

    def test_map_person_basic(self):
        data = {
            "id": "p1",
            "full_name": "Jane Doe",
            "first_name": "Jane",
            "last_name": "Doe",
            "current_title": "CTO",
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "location": {"city": "SF", "country": "USA"},
        }
        out = PeopleMapper.map_person(data, "company-uuid-here")
        assert out["full_name"] == "Jane Doe"
        assert out["current_title"] == "CTO"
        assert out["company_id"] == "company-uuid-here"
        assert out["location_city"] == "SF"
        assert out["location_country"] == "USA"
        assert out["enriched"] is False


class TestEnrichmentMapper:
    """Test EnrichmentMapper: role value, _map_contact, map_to_accounts_contacts."""

    def test_role_value_ceo(self):
        m = EnrichmentMapper()
        assert m._get_role_value("CEO") == 1
        assert m._get_role_value("Chief Executive Officer") == 1

    def test_role_value_vp(self):
        m = EnrichmentMapper()
        assert m._get_role_value("VP of Engineering") == 3
        assert m._get_role_value("Director of Sales") == 3

    def test_role_value_manager(self):
        m = EnrichmentMapper()
        assert m._get_role_value("Product Manager") == 2

    def test_role_value_none(self):
        m = EnrichmentMapper()
        assert m._get_role_value("") is None
        assert m._get_role_value("  ") is None

    def test_map_to_accounts_contacts_empty(self):
        m = EnrichmentMapper()
        acc, con = m.map_to_accounts_contacts({})
        assert acc == []
        assert con == []

    def test_map_to_accounts_contacts_empty_datas(self):
        m = EnrichmentMapper()
        acc, con = m.map_to_accounts_contacts({"datas": []})
        assert acc == []
        assert con == []

    def test_map_to_accounts_contacts_one_contact(self):
        m = EnrichmentMapper()
        payload = {
            "datas": [
                {
                    "contact": {
                        "most_probable_email": "jane@acme.com",
                        "firstname": "Jane",
                        "lastname": "Doe",
                        "profile": {
                            "firstname": "Jane",
                            "lastname": "Doe",
                            "linkedin_url": "https://linkedin.com/in/jane",
                            "headline": "CTO at Acme",
                            "location": "San Francisco",
                            "position": {"title": "CTO", "company": {"name": "Acme Inc"}},
                            "company": {"name": "Acme Inc"},
                        },
                    },
                    "custom": {
                        "original_first_name": "Jane",
                        "original_last_name": "Doe",
                        "original_company": "Acme Inc",
                    },
                }
            ]
        }
        accounts, contacts = m.map_to_accounts_contacts(payload)
        assert len(contacts) == 1
        c = contacts[0]
        assert c.get("email") == "jane@acme.com"
        assert c.get("company_name") == "Acme Inc"
        assert c.get("account") == "Acme Inc"
        assert c.get("full_name") == "Jane Doe"
        assert len(accounts) == 1
        assert accounts[0].get("company_name") == "Acme Inc"

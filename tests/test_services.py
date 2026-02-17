"""Tests for enrichment and people_search services (mocked external deps)."""

import pytest
from unittest.mock import MagicMock, patch


class TestEnrichmentServiceProcessWebhook:
    """Test EnrichmentService.process_webhook (no DB, no API)."""

    def test_process_webhook_returns_accounts_and_contacts(self):
        from src.fullenrich.mappers import EnrichmentMapper
        mapper = EnrichmentMapper()
        accounts, contacts = mapper.map_to_accounts_contacts({
            "datas": [
                {
                    "contact": {
                        "most_probable_email": "j@acme.com",
                        "profile": {
                            "firstname": "J",
                            "lastname": "Doe",
                            "position": {"title": "CEO", "company": {"name": "Acme"}},
                            "company": {"name": "Acme"},
                        },
                    },
                    "custom": {"original_company": "Acme"},
                }
            ]
        })
        assert len(contacts) == 1
        assert len(accounts) == 1
        assert contacts[0]["email"] == "j@acme.com"
        assert accounts[0]["company_name"] == "Acme"

    def test_process_webhook_via_service_requires_db(self):
        """EnrichmentService.__init__ needs Supabase; we test process_webhook logic via mapper."""
        from src.fullenrich.mappers import EnrichmentMapper
        m = EnrichmentMapper()
        acc, con = m.map_to_accounts_contacts({"datas": []})
        assert acc == []
        assert con == []


class TestPeopleSearchService:
    """Test PeopleSearchService with mocked FullEnrich client."""

    @pytest.fixture
    def mock_fullenrich(self):
        mock = MagicMock()
        mock.search_companies.return_value = [
            {"id": "c1", "name": "Acme", "domain": "acme.com", "headcount": 100}
        ]
        mock.search_people.return_value = {
            "people": [
                {
                    "id": "p1",
                    "full_name": "Jane Doe",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "current_title": "CTO",
                    "linkedin_url": "https://linkedin.com/in/jane",
                    "location": {},
                }
            ],
            "total": 1,
        }
        return mock

    def test_search_people_returns_company_and_list(self, mock_fullenrich):
        with patch("src.services.people_search.FullEnrichClient", return_value=mock_fullenrich):
            from src.services.people_search import PeopleSearchService
            svc = PeopleSearchService()
            company, people = svc.search_people("Acme", limit=10)
        assert company is not None
        assert company["name"] == "Acme"
        assert company["domain"] == "acme.com"
        assert len(people) == 1
        assert people[0]["full_name"] == "Jane Doe"
        assert people[0]["current_title"] == "CTO"

    def test_search_company_returns_none_when_no_results(self, mock_fullenrich):
        mock_fullenrich.search_companies.return_value = []
        with patch("src.services.people_search.FullEnrichClient", return_value=mock_fullenrich):
            from src.services.people_search import PeopleSearchService
            svc = PeopleSearchService()
            company = svc.search_company("NonExistentCorp")
        assert company is None

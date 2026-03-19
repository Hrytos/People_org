"""Tests for HubSpotSyncService mapping and sync orchestration."""

from unittest.mock import patch


@patch("src.services.hubspot_sync.validate_hubspot_config", return_value=True)
def test_sync_contacts_skips_missing_emails(_mock_cfg):
    from src.services.hubspot_sync import HubSpotSyncService

    svc = HubSpotSyncService(dry_run=True)
    result = svc.sync_contacts([
        {"first_name": "NoEmail"},
        {"email": "a@example.com", "first_name": "A"},
    ])

    assert result["attempted"] == 1
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 1


@patch("src.services.hubspot_sync.validate_hubspot_config", return_value=True)
@patch("src.services.hubspot_sync.HubSpotClient")
def test_sync_contacts_batches_and_reports_partial_failures(mock_client_cls, _mock_cfg):
    from src.services.hubspot_sync import HubSpotSyncService

    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.validate_unique_contact_property.return_value = True
    mock_client.batch_upsert_contacts.return_value = {
        "results": [{"id": "1"}]  # one ack for two inputs => partial
    }

    svc = HubSpotSyncService(dry_run=False)
    result = svc.sync_contacts([
        {"email": "a@example.com", "first_name": "A"},
        {"email": "b@example.com", "first_name": "B"},
    ])

    assert result["attempted"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert len(result["failures"]) >= 1


@patch("src.services.hubspot_sync.validate_hubspot_config", return_value=False)
def test_sync_contacts_requires_hubspot_config(_mock_cfg):
    from src.services.hubspot_sync import HubSpotSyncService

    svc = HubSpotSyncService(dry_run=True)
    try:
        svc.sync_contacts([{"email": "a@example.com"}])
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "HUBSPOT_SERVICE_KEY" in str(exc)

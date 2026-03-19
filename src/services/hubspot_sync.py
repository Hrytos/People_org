"""
HubSpot sync service.

Manually syncs contacts from this app to HubSpot CRM contacts with
batch upsert behavior and resilient partial-failure reporting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.config import (
    HUBSPOT_BATCH_SIZE,
    HUBSPOT_CONTACT_FIELD_MAP,
    HUBSPOT_DRY_RUN,
    HUBSPOT_SUPABASE_ID_PROPERTY,
    validate_hubspot_config,
)
from ..core.logging import setup_logger
from ..integrations.hubspot import HubSpotClient

logger = setup_logger(__name__)


class HubSpotSyncService:
    """Orchestrates contact mapping and batch upsert to HubSpot."""

    def __init__(self, dry_run: bool = HUBSPOT_DRY_RUN):
        self.dry_run = dry_run

    @staticmethod
    def _safe_str(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize property names for tolerant matching."""
        return "".join(ch for ch in str(name).lower() if ch.isalnum())

    def _resolve_property_by_name_or_label(
        self,
        candidate: str,
        available_names: set[str],
        normalized_name_to_name: Dict[str, str],
        normalized_label_to_name: Dict[str, str],
    ) -> str:
        """Resolve a property by exact/normalized internal name or by label."""
        if candidate in available_names:
            return candidate

        normalized_candidate = self._normalize_name(candidate)
        if normalized_candidate in normalized_name_to_name:
            return normalized_name_to_name[normalized_candidate]

        if normalized_candidate in normalized_label_to_name:
            return normalized_label_to_name[normalized_candidate]

        return ""

    @staticmethod
    def _select_available_property(
        available_properties: set[str],
        candidates: List[str],
    ) -> Optional[str]:
        for candidate in candidates:
            if candidate in available_properties:
                return candidate
        return None

    def _build_property_name_map(self, available_properties: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Build source-field to HubSpot property-name mapping using discovered properties.

        Standard properties are preferred first and always included as fallback where safe.
        Custom fields are only mapped when discovered in HubSpot properties.
        """
        mapping: Dict[str, str] = {}
        available_names = {
            str(prop.get("name", ""))
            for prop in available_properties
            if prop.get("name")
        }
        normalized_name_to_name = {
            self._normalize_name(name): name for name in available_names
        }
        normalized_label_to_name = {
            self._normalize_name(str(prop.get("label", ""))): str(prop.get("name", ""))
            for prop in available_properties
            if prop.get("label") and prop.get("name")
        }

        baseline_candidates = {
            "email": ["email"],
            "first_name": ["firstname"],
            "last_name": ["lastname"],
            "phone": ["phone"],
            "company_name": ["company"],
            "job_title": ["jobtitle"],
        }

        for src_field, candidates in baseline_candidates.items():
            selected = ""
            for candidate in candidates:
                selected = self._resolve_property_by_name_or_label(
                    candidate,
                    available_names,
                    normalized_name_to_name,
                    normalized_label_to_name,
                )
                if selected:
                    break
            if selected:
                mapping[src_field] = selected

        custom_candidates = {
            "account_id": ["accountID", "account_id", "accountid"],
            "linkedin_url": ["linkedin_url", "linkedinurl", "linkedin_profile_url"],
            "linkedin_id": ["linkedin_id", "linkedinid"],
            "sales_navigator_id": ["sales_navigator_id", "salesnavigatorid", "sales_nav_id"],
            "summary": ["linkedin_summary", "summary", "about"],
            "job_description": ["linkedin_job_description", "job_description"],
            "job_started_at": ["job_started_at", "job_start_date", "start_date"],
            "job_ended_at": ["job_ended_at", "job_end_date", "end_date"],
            "role_value": ["role_value", "rolevalue"],
            "location": ["street_address", "address", "location"],
            "headline": ["headline"],
        }

        if isinstance(HUBSPOT_CONTACT_FIELD_MAP, dict):
            for src_field, target_field in HUBSPOT_CONTACT_FIELD_MAP.items():
                src = self._safe_str(src_field)
                target = self._safe_str(target_field)
                if not src or not target:
                    continue
                resolved_target = self._resolve_property_by_name_or_label(
                    target,
                    available_names,
                    normalized_name_to_name,
                    normalized_label_to_name,
                )
                if resolved_target:
                    mapping[src] = resolved_target
                else:
                    logger.warning(
                        "Configured HubSpot mapping ignored: %s -> %s (property not found)",
                        src,
                        target,
                    )

        for src_field, candidates in custom_candidates.items():
            if src_field in mapping:
                continue
            selected = ""
            for candidate in candidates:
                selected = self._resolve_property_by_name_or_label(
                    candidate,
                    available_names,
                    normalized_name_to_name,
                    normalized_label_to_name,
                )
                if selected:
                    break
            if selected:
                mapping[src_field] = selected

        return mapping

    def _to_hubspot_properties(
        self,
        contact: Dict[str, Any],
        property_name_map: Dict[str, str],
        trace_property_name: str,
        include_trace_property: bool = True,
    ) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}

        for src, target in property_name_map.items():
            if src == "account_id":
                val = self._safe_str(contact.get("account_id"))
            else:
                val = self._safe_str(contact.get(src))
            if val:
                properties[target] = val

        # Prefer DB-generated id for traceability when available.
        supabase_id = contact.get("id") or contact.get("contact_id")
        if include_trace_property and supabase_id and trace_property_name:
            properties[trace_property_name] = str(supabase_id)

        return properties

    def _to_upsert_input(
        self,
        contact: Dict[str, Any],
        property_name_map: Dict[str, str],
        trace_property_name: str,
        include_trace_property: bool = True,
    ) -> Optional[Dict[str, Any]]:
        email = self._safe_str(contact.get("email"))
        if not email:
            return None

        properties = self._to_hubspot_properties(
            contact,
            property_name_map=property_name_map,
            trace_property_name=trace_property_name,
            include_trace_property=include_trace_property,
        )
        if "email" not in properties:
            properties["email"] = email

        return {
            "idProperty": "email",
            "id": email,
            "properties": properties,
        }

    def discover_contact_property_map(self) -> Dict[str, str]:
        """
        Discover key contact properties from HubSpot.

        Returns:
            Dict mapping normalized property names -> internal HubSpot names.
        """
        if not validate_hubspot_config(required=True):
            raise ValueError("HubSpot config missing: HUBSPOT_SERVICE_KEY")

        with HubSpotClient() as client:
            props = client.get_contact_properties()

        mapping: Dict[str, str] = {}
        for prop in props:
            internal_name = prop.get("name", "")
            if internal_name:
                mapping[internal_name.lower()] = internal_name

        return mapping

    def sync_contacts(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync contacts to HubSpot with batch upsert.

        Returns:
            Summary dict with attempted/succeeded/failed/skipped/failures.
        """
        if not contacts:
            return {
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "failures": [],
                "dry_run": self.dry_run,
            }

        if not validate_hubspot_config(required=True):
            raise ValueError("HubSpot config missing: HUBSPOT_SERVICE_KEY")

        failures: List[Dict[str, Any]] = []
        include_trace_property = True
        trace_property_name = HUBSPOT_SUPABASE_ID_PROPERTY
        property_name_map: Dict[str, str] = {
            "email": "email",
            "first_name": "firstname",
            "last_name": "lastname",
            "phone": "phone",
            "company_name": "company",
            "job_title": "jobtitle",
        }

        if not self.dry_run:
            with HubSpotClient() as client:
                custom_unique = client.validate_unique_contact_property(HUBSPOT_SUPABASE_ID_PROPERTY)
                try:
                    discovered = client.get_contact_properties()
                    discovered_properties = discovered if isinstance(discovered, list) else []
                    discovered_names = {
                        str(p.get("name", ""))
                        for p in discovered_properties
                        if p.get("name")
                    }
                    normalized_names = {
                        self._normalize_name(name): name for name in discovered_names
                    }

                    requested_trace = HUBSPOT_SUPABASE_ID_PROPERTY
                    resolved_trace = normalized_names.get(self._normalize_name(requested_trace), "")
                    if resolved_trace:
                        trace_property_name = resolved_trace
                        include_trace_property = True
                        if not custom_unique:
                            logger.warning(
                                "HubSpot property %s exists but is not unique. Writing trace ID anyway.",
                                trace_property_name,
                            )
                    else:
                        include_trace_property = False
                        logger.warning(
                            "HubSpot property %s not found. Traceability field will be skipped.",
                            requested_trace,
                        )

                    property_name_map = self._build_property_name_map(discovered_properties)
                    logger.info("Resolved HubSpot property mapping: %s", property_name_map)
                except Exception as e:
                    logger.warning(f"HubSpot property discovery failed, using baseline mapping: {e}")

        valid_inputs: List[Dict[str, Any]] = []
        for contact in contacts:
            upsert_input = self._to_upsert_input(
                contact,
                property_name_map=property_name_map,
                trace_property_name=trace_property_name,
                include_trace_property=include_trace_property,
            )
            if upsert_input is None:
                failures.append(
                    {
                        "email": self._safe_str(contact.get("email")),
                        "reason": "Missing email",
                    }
                )
                continue
            valid_inputs.append(upsert_input)

        attempted = len(valid_inputs)
        skipped = len(failures)

        if self.dry_run:
            logger.info("HubSpot dry run: prepared %s contacts", attempted)
            return {
                "attempted": attempted,
                "succeeded": attempted,
                "failed": 0,
                "skipped": skipped,
                "failures": failures,
                "dry_run": True,
            }

        succeeded = 0
        failed = 0

        with HubSpotClient() as client:

            for i in range(0, attempted, HUBSPOT_BATCH_SIZE):
                batch = valid_inputs[i : i + HUBSPOT_BATCH_SIZE]
                try:
                    resp = client.batch_upsert_contacts(batch)
                    results = resp.get("results", [])
                    # HubSpot may return fewer result rows than input rows on partial issues.
                    batch_success = len(results) if isinstance(results, list) else len(batch)
                    succeeded += min(batch_success, len(batch))
                    if batch_success < len(batch):
                        missing = len(batch) - batch_success
                        failed += missing
                        failures.append(
                            {
                                "reason": f"Batch partial response: {missing} records not acknowledged",
                                "batch_start": i,
                            }
                        )
                except Exception as e:
                    failed += len(batch)
                    for item in batch:
                        failures.append(
                            {
                                "email": item.get("id", ""),
                                "reason": str(e),
                            }
                        )

        return {
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "failures": failures,
            "dry_run": False,
        }

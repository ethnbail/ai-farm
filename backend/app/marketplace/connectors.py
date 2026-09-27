"""Swappable, user-initiated acquisition. No HTTP fetches, cookies, or browser sessions."""

import csv
import io
import json
from typing import Protocol

from app.schemas.marketplace import ListingInput, safe_url


class MarketplaceSourceConnector(Protocol):
    supports_refresh: bool
    refresh_interval: int | None
    requires_manual_update: bool

    def rows(self) -> list[dict]: ...


class ManualJSONConnector:
    supports_refresh = False
    refresh_interval = None
    requires_manual_update = True

    def __init__(self, payload):
        if not isinstance(payload, list) or len(payload) > 100:
            raise ValueError("Import requires an array of at most 100 rows")
        if len(json.dumps(payload, default=str).encode()) > 1_000_000:
            raise ValueError("Import exceeds 1 MB")
        self.payload = payload

    def rows(self):
        return self.payload


class CSVConnector(ManualJSONConnector):
    def __init__(self, content: str):
        if len(content.encode()) > 1_000_000:
            raise ValueError("CSV exceeds 1 MB")
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV requires unique named columns")
        rows = []
        for row in reader:
            if len(rows) >= 100:
                raise ValueError("CSV exceeds 100 rows")
            row = {k: v for k, v in row.items() if v not in (None, "")}
            # Complex fields accept JSON inside a quoted CSV cell.
            for key in [
                "comps",
                "demand",
                "item_metadata",
                "image_metadata",
                "seller_profile_metadata",
                "raw_source_metadata",
            ]:
                if key in row:
                    try:
                        row[key] = json.loads(row[key])
                    except (TypeError, ValueError):
                        row[key] = (
                            "Invalid JSON cell"  # Per-row validation error, not whole-batch loss.
                        )
            rows.append(row)
        super().__init__(rows)


class URLReferenceConnector:
    def capture(self, url):
        return {
            "source_url": safe_url(url),
            "extracted": False,
            "requires_manual_details": True,
            "message": (
                "URL saved as a form reference only. No page was fetched. Supply title, "
                "asking price and available evidence to create a listing."
            ),
        }


class PhotoAnalysisProvider(Protocol):
    def analyze(self, image_metadata: list[dict]) -> dict: ...


class UnavailablePhotoAnalysis:
    def analyze(self, image_metadata):
        return {
            "status": "unavailable",
            "findings": [],
            "message": "No vision provider configured; text/metadata analysis remains available",
        }


def capabilities():
    return [
        {
            "id": name,
            "status": "available",
            "supports_refresh": False,
            "refresh_interval": None,
            "requires_manual_update": True,
            "description": description,
        }
        for name, description in [
            ("manual", "User form entry; no external connection"),
            ("url", "URL reference plus manual details; no extraction"),
            ("json", "User-provided normalized JSON/export; partial success and dry-run"),
            ("csv", "User-provided normalized CSV/export; partial success and dry-run"),
            (
                "browser_capture",
                "User pastes selected listing fields; no browser/session automation",
            ),
            ("fixture", "Explicit fictional development records"),
        ]
    ] + [
        {
            "id": "approved_api",
            "status": "not_configured",
            "supports_refresh": False,
            "refresh_interval": None,
            "requires_manual_update": True,
            "description": "Future approved API adapter; no Facebook public API assumed",
        }
    ]


def validate_row(row):
    if not isinstance(row, dict):
        raise ValueError("Each row must be an object")
    return ListingInput.model_validate(row)

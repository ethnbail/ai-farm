"""Explicit local tools; fixture writes require development opt-in."""

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.marketplace.connectors import CSVConnector, ManualJSONConnector
from app.marketplace.fixtures import fixtures
from app.marketplace.pipeline import import_batch, inventory_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["fixture", "import-json", "import-csv", "refresh-inventory"]
    )
    parser.add_argument("--file", type=Path)
    parser.add_argument("--apply", action="store_true", help="Persist changes; default is dry-run")
    args = parser.parse_args()
    if args.action == "fixture" and not get_settings().enable_development_actions:
        parser.error("Fixture requires ENABLE_DEVELOPMENT_ACTIONS=true")
    with Session(get_engine()) as session:
        if args.action == "refresh-inventory":
            result = inventory_data(session, refresh=args.apply)
        else:
            if args.action == "fixture":
                connector = ManualJSONConnector(fixtures())
            else:
                if not args.file or args.file.stat().st_size > 1_000_000:
                    parser.error("Supply --file pointing to at most 1 MB of JSON or CSV")
                text = args.file.read_text(encoding="utf-8-sig")
                connector = (
                    CSVConnector(text)
                    if args.action == "import-csv"
                    else ManualJSONConnector(json.loads(text))
                )
            result = import_batch(session, connector, dry_run=not args.apply)
        print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()

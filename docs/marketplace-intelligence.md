# Marketplace intelligence foundation

`MarketplaceSourceConnector` returns validated `MarketplaceListingInput` records. `ManualJSONConnector` accepts up to 100 supplied records and validates/scores the batch before persistence. Unique source/listing ID makes reimport idempotent; existing records are not silently overwritten. The fixture command imports one explicitly fictional oak desk. URLs are validated and displayed as links, never fetched by the backend. There is no scraper, browser automation, seller messaging or purchase execution.

Listings retain description, price/history, age, location/distance, seller and photo metadata, category, condition, accessories and authenticity information. `MarketplaceScore` explains age priority, observed original-price drop and unverified motivation words. Demand/seasonality, repost detection, seller reliability, sell-through, sale time and calibrated confidence remain unknown/N/A.

Resale low/high must be supplied, not hallucinated. Illustrative economics use the low estimate, 10% fees, $0.70/mile round trip and a $25 target margin. Missing resale or distance means missing net-profit/buy-price estimates. These are editable code assumptions, not appraisals or guaranteed outcomes. The fixture asks $80, estimates $150–$200 resale and $7 travel: conservative net $48 and maximum suggested buy $103 under these assumptions. Authenticity and comparables are unverified.

`record_outcome` persists bought/not bought, actual acquisition/sale/fees/travel, timezone-aware dates, net profit/days to sell and the prediction snapshot. No adaptive model is trained. Reject reversed sale dates and sale-without-purchase. Local Python service usage, from `backend/` after setup:

```python
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.database.session import get_engine
from app.services.marketplace import ManualJSONConnector, import_listings, record_outcome
from app.schemas.intelligence import MarketplaceOutcomeInput

payload = json.loads(Path("/absolute/path/to/manual-listings.json").read_text())
with Session(get_engine()) as session:
    listings = import_listings(session, ManualJSONConnector(payload))
    record_outcome(session, listings[0].id, MarketplaceOutcomeInput(bought=False))
```

Required import fields: listing_id, title, asking_price and direct_url; source defaults manual. Optional fields are documented in `schemas/intelligence.py`. Import services are local developer tools; there is no unauthenticated HTTP purchase/outcome mutation surface. Original Phase 1 ZIP/radius placeholders remain disabled; the new panel lists actual imported/test records separately.

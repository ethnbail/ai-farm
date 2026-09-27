"""Explicitly fictional, repeatable examples. Never external listing or sales claims."""

from datetime import UTC, datetime, timedelta


def fixtures(now=None):
    now = now or datetime.now(UTC)

    def record(
        key,
        title,
        category,
        price,
        value,
        distance=3,
        age=5,
        description="Moving; need gone, pickup today",
        **changes,
    ):
        accessories = {
            "gaming": {"controller": True, "power cable": True, "HDMI cable": True},
            "laptop": {
                "charger": True,
                "battery status": True,
                "storage": True,
                "RAM": True,
                "model/year": True,
            },
            "camera": {"battery": False, "charger": False, "lens": False, "body cap": False},
        }.get(category, {})
        return {
            "source": "fixture",
            "source_listing_id": f"phase5-{key}",
            "source_url": f"https://example.com/ai-farm/{key}",
            "title": title,
            "description": description,
            "category": category,
            "model": f"TEST-{category}",
            "asking_price": str(price),
            "condition": "used",
            "listed_at": (now - timedelta(minutes=age)).isoformat(),
            "zip_code": "94103",
            "location_text": "Fictional local example",
            "distance_miles": str(distance),
            "driving_minutes_round_trip": 20,
            "seller_id": f"test-{key}",
            "seller_rating": "4.8",
            "seller_review_count": 40,
            "item_metadata": {"accessories": accessories, "authenticity_verified": True},
            "comps": [
                {
                    "source": "fictional Phase 5 fixture",
                    "source_url": f"https://example.com/comp/{key}/{i}",
                    "price": str(value + i * 5),
                    "observed_at": (now - timedelta(days=2)).isoformat(),
                    "sold": True,
                    "days_to_sell": 5,
                    "market": "LOCAL",
                    "quality": "fixture",
                    "model": f"TEST-{category}",
                    "category": category,
                    "condition": "used",
                }
                for i in range(5)
            ],
            "demand": [
                {
                    "source": "fictional complete cohort",
                    "observed_at": now.isoformat(),
                    "market": "LOCAL",
                    "cohort_size": 100,
                    "observation_days": 60,
                    "sold_7d": 60,
                    "sold_14d": 75,
                    "sold_30d": 85,
                    "sold_60d": 90,
                    "active_listing_count": 15,
                    "quality": "fixture",
                }
            ],
            **changes,
        }

    console = record("console", "TEST fresh gaming console", "gaming", 170, 300)
    repost = {
        **console,
        "source_listing_id": "phase5-console-repost",
        "source_url": "https://example.com/repost/console",
        "listed_at": now.isoformat(),
    }
    slow = [
        {
            "source": "fictional slow national cohort",
            "observed_at": now.isoformat(),
            "market": "NATIONAL",
            "cohort_size": 100,
            "observation_days": 60,
            "sold_7d": 2,
            "sold_14d": 5,
            "sold_30d": 12,
            "sold_60d": 25,
            "quality": "fixture",
        }
    ]
    return [
        console,
        record("laptop", "TEST overpriced laptop", "laptop", 900, 450),
        record(
            "luxury",
            "TEST suspicious luxury bag",
            "luxury",
            50,
            700,
            description="Replica 1:1 copy; gift card deposit before viewing",
            item_metadata={},
        ),
        repost,
        record(
            "motivated",
            "TEST motivated seller desk",
            "furniture",
            80,
            180,
            age=3000,
            original_price="140",
        ),
        record("camera", "TEST incomplete camera bundle", "camera", 150, 230),
        record("far", "TEST distant bicycle", "bicycle", 100, 220, distance=80),
        record("seasonal", "TEST seasonal heater", "heater", 40, 90),
        record("fast", "TEST fast local console", "gaming", 160, 290),
        record("slow", "TEST slow national collectible", "collectible", 80, 180, demand=slow),
    ]

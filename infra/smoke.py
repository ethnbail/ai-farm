"""Read-only checks of the running stack using only the Python standard library."""

import argparse
import json
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:8000")
args = parser.parse_args()


def get(path):
    with urlopen(f"{args.api}{path}", timeout=10) as response:
        return json.load(response)


health = get("/health")
assert health["status"] == "ok", health
agents = get("/api/agents")
assert {a["name"] for a in agents} == {"Agent A", "Agent B"}, agents
for agent in agents:
    assert get(f"/api/agents/{agent['id']}")["id"] == agent["id"]
    assert isinstance(get(f"/api/agents/{agent['id']}/trades"), list)
    portfolio = get(f"/api/agents/{agent['id']}/portfolio")
    assert portfolio["agent_id"] == agent["id"]
    assert isinstance(get(f"/api/agents/{agent['id']}/positions"), list)
    assert "equity" in get(f"/api/agents/{agent['id']}/performance")
assert get("/api/market/status")["paper_only"] is True
assert isinstance(get("/api/activity"), list)
assert get("/api/market/regime")["regime"] in {
    "BULL_TREND",
    "BEAR_TREND",
    "RANGE_BOUND",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "RISK_OFF",
    "UNKNOWN",
}
assert "effective_provider" in get("/api/market/provider-status")
assert "daily_spend" in get("/api/ai/usage")
assert "mode" in get("/api/ai/status")
assert isinstance(get("/api/research"), list)
assert isinstance(get("/api/marketplace/opportunities"), list)
for agent in agents:
    assert "watchlist" in get(f"/api/agents/{agent['id']}/intelligence")
print("Health, PostgreSQL, Redis, agents, paper trading, intelligence and Marketplace APIs: OK")

with urlopen(f"{args.api}/api/events", timeout=10) as response:
    assert response.headers.get_content_type() == "text/event-stream"
    for raw in response:
        line = raw.decode().strip()
        if line.startswith("data: "):
            event = json.loads(line[6:])
            assert event["event_type"] == "heartbeat", event
            assert event["payload"]["status"] == "alive"
            print("Live SSE heartbeat: OK")
            break
    else:
        raise AssertionError("SSE stream ended without a heartbeat")

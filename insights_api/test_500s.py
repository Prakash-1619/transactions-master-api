from fastapi.testclient import TestClient
import traceback

from market_api import app

client = TestClient(app)
endpoints = [
    '/market/insights/unified/tiles',
    '/market/insights/unified/growth_and_yield',
    '/market/insights/unified/plots/unified_growth',
    '/market/insights/unified/transactions'
]

for ep in endpoints:
    print(f"Testing {ep}...")
    try:
        response = client.get(ep + "?emirate=Dubai")
        print(f"Status: {response.status_code}")
        if response.status_code == 500:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Exception on {ep}:")
        traceback.print_exc()


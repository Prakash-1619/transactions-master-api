import requests
import time

base_url = 'http://127.0.0.1:8003/market/insights/unified'
endpoints = [
    '/tiles',
    '/growth_and_yield',
    '/price_bins',
    '/grouped_distributions',
    '/area_vs_price',
    '/feature_prices',
    '/top_bottom_performers',
    '/plots/unified_growth',
    '/transactions'
]

print("=== API ENDPOINT TEST REPORT ===")
for ep in endpoints:
    url = f"{base_url}{ep}"
    
    # Test 1: No params (defaults to Dubai & current year typically)
    start = time.time()
    try:
        r = requests.get(url, params={'emirate': 'Dubai'})
        end = time.time()
        print(f"[TEST 1] {ep} - Status: {r.status_code} - Time: {end - start:.3f}s")
        if r.status_code != 200:
            print(f"   Error: {r.text[:200]}")
    except Exception as e:
        print(f"[TEST 1] {ep} - FAILED - {e}")

    # Test 2: Rental data with area
    start = time.time()
    try:
        r = requests.get(url, params={'emirate': 'Dubai', 'is_rental': 'true', 'area': 'Downtown Dubai', 'year': 2023})
        end = time.time()
        print(f"[TEST 2] {ep} (Rental, 2023) - Status: {r.status_code} - Time: {end - start:.3f}s")
        if r.status_code != 200:
            print(f"   Error: {r.text[:200]}")
    except Exception as e:
        print(f"[TEST 2] {ep} - FAILED - {e}")
        
    print("-" * 50)

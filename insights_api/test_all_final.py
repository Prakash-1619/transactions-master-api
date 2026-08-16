import requests
import time

base_url = 'http://127.0.0.1:8003/market/insights/unified'
endpoints = [
    '/tiles',
    '/growth_and_yield',
    '/distributions/price_bins',
    '/distributions/grouped',
    '/area_vs_price',
    '/feature_prices',
    '/top_bottom_performers',
    '/plots/unified_growth',
    '/transactions'
]

with open('api_test_report_final.md', 'w') as f:
    f.write("# API Endpoint Test Report\n\n")
    f.write("Testing 9 Unified Macro Insights Endpoints against base URL http://127.0.0.1:8003/market/insights/unified\n\n")
    
    for ep in endpoints:
        url = f"{base_url}{ep}"
        
        # Test 1: Sales defaults
        start = time.time()
        try:
            r = requests.get(url, params={'emirate': 'Dubai'})
            end = time.time()
            res = f"? GET {ep}\n- **Status:** {r.status_code}\n- **Latency:** {end - start:.3f}s\n"
            if r.status_code != 200:
                res += f"- **Error:** {r.text[:200]}\n"
            f.write(res)
        except Exception as e:
            f.write(f"? GET {ep}\n- **FAILED** - {e}\n")

        # Test 2: Rental constraints
        start = time.time()
        try:
            r = requests.get(url, params={'emirate': 'Dubai', 'is_rental': 'true', 'year': 2023})
            end = time.time()
            res2 = f"- **Rental Status (2023):** {r.status_code} ({end - start:.3f}s)\n\n"
            if r.status_code != 200:
                res2 += f"  - **Error:** {r.text[:200]}\n"
            f.write(res2)
        except Exception as e:
            f.write(f"- **Rental FAILED:** {e}\n\n")

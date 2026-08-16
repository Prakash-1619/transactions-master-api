import requests
url = 'http://127.0.0.1:8003/market/insights/unified/feature_prices?emirate=Dubai'
r = requests.get(url)
print(r.status_code)
print(r.text)

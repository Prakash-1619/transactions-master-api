import requests
import time

print('Waiting for API to boot...')
while True:
    try:
        r = requests.get('http://127.0.0.1:8003/')
        if r.status_code == 200:
            print('API is up!')
            break
    except:
        pass
    time.sleep(2)

print('Testing area_vs_price...')
url = 'http://127.0.0.1:8003/market/insights/unified/area_vs_price?emirate=Dubai'
start = time.time()
try:
    response = requests.get(url, timeout=30)
    end = time.time()
    print(f'area_vs_price took {end - start:.4f} seconds (Status: {response.status_code})')
except Exception as e:
    print(f'Error: {e}')

print('Testing tiles...')
url2 = 'http://127.0.0.1:8003/market/insights/unified/tiles?emirate=Dubai'
start = time.time()
try:
    response = requests.get(url2, timeout=30)
    end = time.time()
    print(f'tiles took {end - start:.4f} seconds (Status: {response.status_code})')
except Exception as e:
    print(f'Error: {e}')

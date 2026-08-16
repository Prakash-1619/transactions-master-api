file_path = 'unified_router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('@router.get("/price_bins")', '@router.get("/distributions/price_bins")')
content = content.replace('@router.get("/grouped_distributions")', '@router.get("/distributions/grouped")')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Renamed endpoints")

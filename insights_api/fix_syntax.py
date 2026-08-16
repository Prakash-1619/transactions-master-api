file_path = 'unified_router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

bad_string = "),\n    year: Optional[int] = Query(None, description=\"Year (defaults to current year if no dates given)\")\n):"
good_string = ",\n    year: Optional[int] = Query(None, description=\"Year (defaults to current year if no dates given)\")\n):"

content = content.replace(bad_string, good_string)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Syntax fixed")

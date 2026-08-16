import os
import sys

file_path = 'unified_router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Inject sys.path to find duckdb_setup.py
injection = '''import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
'''
if 'sys.path.append' not in content:
    content = injection + content

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed sys.path for duckdb_setup")

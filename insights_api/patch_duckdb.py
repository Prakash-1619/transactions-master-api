import os
file_path = '../duckdb_setup.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make it use absolute path
new_content = content.replace("DB_FILE = 'transactions_cache.db'", "import os\nDB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transactions_cache.db')")
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Patched duckdb_setup.py to use absolute path")

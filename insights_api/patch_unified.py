import re

file_path = 'unified_router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update filter_data signature
content = content.replace(
    'def filter_data(df: pd.DataFrame, is_rental: bool, emirate: str, lat: float, lon: float, area: str, start_date: str, end_date: str, room_type: str, property_type: str, reg_type: str = None, transaction_type: str = None):',
    'def filter_data(df: pd.DataFrame, is_rental: bool, emirate: str, lat: float, lon: float, area: str, start_date: str, end_date: str, room_type: str, property_type: str, reg_type: str = None, transaction_type: str = None, year: int = None):'
)

# 2. Update filter_data logic to include year logic
old_date_logic = '''    if start_date and date_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[date_col] >= pd.to_datetime(start_date)]
    if end_date and date_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[date_col] <= pd.to_datetime(end_date)]'''

new_date_logic = '''    if start_date and date_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[date_col] >= pd.to_datetime(start_date)]
    if end_date and date_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[date_col] <= pd.to_datetime(end_date)]

    # Default to current year if no dates are provided, or use specific year if provided
    if not start_date and not end_date and date_col in filtered_df.columns:
        from datetime import datetime
        target_year = year if year else datetime.today().year
        filtered_df = filtered_df[pd.to_datetime(filtered_df[date_col]).dt.year == target_year]'''

if old_date_logic in content:
    content = content.replace(old_date_logic, new_date_logic)
else:
    print("Warning: old_date_logic not found")

# 3. Add year parameter to all endpoints
content = re.sub(
    r'(transaction_type: Optional\[str\] = Query\(None\)\n\)):',
    r'\1,\n    year: Optional[int] = Query(None, description="Year (defaults to current year if no dates given)")\n):',
    content
)

# 4. Replace filter_data calls to pass year
content = re.sub(
    r'(filter_data\([^)]+?transaction_type)\)',
    r'\1, year)',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")

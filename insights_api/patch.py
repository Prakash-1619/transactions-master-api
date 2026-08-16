import re

with open('unified_router.py', 'r') as f:
    content = f.read()

# 1. Update filter_data signature
content = re.sub(
    r'def filter_data\(df: pd\.DataFrame, is_rental: bool, emirate: str, lat: float, lon: float, area: str, start_date: str, end_date: str, room_type: str, property_type: str, reg_type: str = None, transaction_type: str = None\):',
    'def filter_data(df: pd.DataFrame, is_rental: bool, emirate: str, lat: float, lon: float, area: str, start_date: str, end_date: str, room_type: str, property_type: str, reg_type: str = None, transaction_type: str = None, year: int = None):',
    content
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
        target_year = year if year else datetime.today().year
        filtered_df = filtered_df[pd.to_datetime(filtered_df[date_col]).dt.year == target_year]'''

content = content.replace(old_date_logic, new_date_logic)

# 3. Add year parameter to all endpoints and pass to filter_data
endpoints = [
    'get_unified_tiles',
    'get_unified_growth_and_yield',
    'get_price_bins',
    'get_area_vs_price',
    'get_feature_prices',
    'get_top_bottom_performers',
    'get_grouped_distributions',
    'plot_unified_growth',
    'get_transactions'
]

# Add year parameter to endpoint definitions
content = re.sub(
    r'(transaction_type: Optional\[str\] = Query\(None\)\n\):)',
    r'\1\n    year: Optional[int] = Query(None, description="Year (defaults to current year if no dates given)")',
    content
)

# Replace filter_data calls to pass year
content = re.sub(
    r'(filter_data\([^)]+?transaction_type)\)',
    r'\1, year)',
    content
)

# Wait, the regex for adding year param to endpoints was flawed because the closing parenthesis is part of the match.
# Let's fix that.
# Actually let's just re-read the file and apply more precise regex.

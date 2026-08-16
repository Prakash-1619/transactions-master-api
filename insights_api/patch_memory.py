import re

file_path = 'unified_router.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update filter_data for Memory Efficiency
# Replace emirate filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\['emirate'\]\.str\.lower\(\) == emirate\.strip\(\)\.lower\(\)\]",
    r"em_target = emirate.strip().lower()\n                valid_em = [e for e in filtered_df['emirate'].dropna().unique() if str(e).lower() == em_target]\n                filtered_df = filtered_df[filtered_df['emirate'].isin(valid_em)]",
    content
)

# Replace area filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\[area_col\]\.str\.lower\(\) == inferred_area\]",
    r"valid_a = [a for a in filtered_df[area_col].dropna().unique() if str(a).lower() == inferred_area]\n        filtered_df = filtered_df[filtered_df[area_col].isin(valid_a)]",
    content
)
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\[area_col\]\.str\.lower\(\) == area\.strip\(\)\.lower\(\)\]",
    r"a_target = area.strip().lower()\n        valid_a2 = [a for a in filtered_df[area_col].dropna().unique() if str(a).lower() == a_target]\n        filtered_df = filtered_df[filtered_df[area_col].isin(valid_a2)]",
    content
)

# Replace room_type filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\[room_col\]\.str\.lower\(\) == room_type\.strip\(\)\.lower\(\)\]",
    r"rt_target = room_type.strip().lower()\n        valid_rt = [rt for rt in filtered_df[room_col].dropna().unique() if str(rt).lower() == rt_target]\n        filtered_df = filtered_df[filtered_df[room_col].isin(valid_rt)]",
    content
)

# Replace property_type filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\[prop_col\]\.str\.lower\(\) == property_type\.strip\(\)\.lower\(\)\]",
    r"pt_target = property_type.strip().lower()\n        valid_pt = [pt for pt in filtered_df[prop_col].dropna().unique() if str(pt).lower() == pt_target]\n        filtered_df = filtered_df[filtered_df[prop_col].isin(valid_pt)]",
    content
)

# Replace reg_type filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\['reg_type'\]\.astype\(str\)\.str\.lower\(\) == reg_type\.strip\(\)\.lower\(\)\]",
    r"rg_target = reg_type.strip().lower()\n        valid_rg = [rg for rg in filtered_df['reg_type'].dropna().unique() if str(rg).lower() == rg_target]\n        filtered_df = filtered_df[filtered_df['reg_type'].isin(valid_rg)]",
    content
)

# Replace transaction_type filter
content = re.sub(
    r"filtered_df = filtered_df\[filtered_df\['transaction_type'\]\.astype\(str\)\.str\.lower\(\) == transaction_type\.strip\(\)\.lower\(\)\]",
    r"tt_target = transaction_type.strip().lower()\n        valid_tt = [tt for tt in filtered_df['transaction_type'].dropna().unique() if str(tt).lower() == tt_target]\n        filtered_df = filtered_df[filtered_df['transaction_type'].isin(valid_tt)]",
    content
)


# 2. Add floor_bin logic to get_feature_prices_df
old_cols = "cols = ['instance_date', 'area_name_en', 'property_usage_en', 'property_sub_type_en', 'rooms_en', \n                    'trans_group_en', 'reg_type_en', 'actual_worth', 'meter_sale_price', 'has_parking', \n                    'floor_bin', 'swimming_pool', 'elevator', 'metro']"
new_cols = "cols = ['instance_date', 'area_name_en', 'property_usage_en', 'property_sub_type_en', 'rooms_en', \n                    'trans_group_en', 'reg_type_en', 'actual_worth', 'meter_sale_price', 'has_parking', \n                    'floor', 'swimming_pool', 'elevator', 'metro']"
content = content.replace(old_cols, new_cols)

binning_logic = '''
            if 'floor' in feature_prices_df.columns:
                feature_prices_df['floor_numeric'] = pd.to_numeric(feature_prices_df['floor'], errors='coerce')
                bins = [0, 10, 20, 30, 40, 50, float('inf')]
                labels = ["1-10", "11-20", "21-30", "31-40", "41-50", "50+"]
                feature_prices_df['floor_bin'] = pd.cut(feature_prices_df['floor_numeric'], bins=bins, labels=labels, right=True).astype(str).replace('nan', 'Unknown')
'''

rename_end = "feature_prices_df = df.rename(columns={"
if rename_end in content:
    parts = content.split("})\n", 1)
    if len(parts) == 2:
        content = parts[0] + "})\n" + binning_logic + parts[1]


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Memory fixes and floor_bin patched successfully")

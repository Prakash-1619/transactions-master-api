import pandas as pd
from latest_rental_data.s3_manager import get_storage_options

storage_opts = get_storage_options()
df = pd.read_parquet('s3://dubai/data/processed/latest_combined_data.parquet', storage_options=storage_opts, columns=['floor_bin'])
print(df['floor_bin'].value_counts(dropna=False).head(20))

try:
    df_f = pd.read_parquet('s3://dubai/data/processed/latest_combined_data.parquet', storage_options=storage_opts, columns=['floor'])
    print("\nFloor column available:")
    print(df_f['floor'].value_counts(dropna=False).head(20))
except Exception as e:
    print("\nFloor column error:", e)

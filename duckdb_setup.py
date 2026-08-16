import duckdb
import pyarrow.dataset as ds
import os
from latest_rental_data.s3_manager import get_s3_fs

import os
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transactions_cache.db')

DUBAI_ROI_URL = 'dubai/data/ROI_data/processed_data.parquet'
ABUDHABI_ROI_URL = 'abudhabi/data/raw/transactions.parquet'
DUBAI_MARKET_URL = 'dubai/data/insights_api/market_data.parquet'
ABUDHABI_MARKET_URL = 'abudhabi/data/insights_api/market_data.parquet'

def get_db_connection(read_only=False):
    return duckdb.connect(DB_FILE, read_only=read_only)

def init_db(force_refresh=False):
    """
    Connects to local DuckDB and creates tables by streaming PyArrow datasets from R2.
    This avoids loading the entire dataset into Pandas RAM, fixing the ArrowMemoryError.
    """
    con = get_db_connection()
    fs = get_s3_fs()
    
    tables_to_sync = [
        ('dubai_roi', DUBAI_ROI_URL),
        ('abudhabi_roi', ABUDHABI_ROI_URL),
        ('dubai_market', DUBAI_MARKET_URL),
        ('abudhabi_market', ABUDHABI_MARKET_URL),
        ('dubai_yield_report', 'dubai/data/ROI_data/dubai_market_yield_report.csv'),
        ('unified_rental', 'c:/Users/pooja/Transactions_api/rental_df.parquet'),
        ('feature_prices', 'dubai/data/processed/latest_combined_data.parquet')
    ]
    
    for table_name, file_path in tables_to_sync:
        # Check if table exists
        exists = con.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone()[0] > 0
        
        if force_refresh or not exists:
            is_local = file_path.startswith('c:/') or file_path.startswith('/')
            
            if is_local:
                if os.path.exists(file_path):
                    print(f"[{table_name}] Loading from local path ({file_path}) into local DuckDB...")
                    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{file_path}')")
                    print(f"[{table_name}] Sync complete.")
                else:
                    print(f"[{table_name}] Local path {file_path} does not exist. Skipping.")
            else:
                if fs.exists(file_path):
                    print(f"[{table_name}] Streaming from R2 ({file_path}) into local DuckDB...")
                    fmt = "csv" if file_path.endswith('.csv') else "parquet"
                    dataset = ds.dataset(file_path, filesystem=fs, format=fmt)
                    
                    # Replace table (streams data via Arrow directly into DuckDB disk format)
                    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM dataset")
                    print(f"[{table_name}] Sync complete.")
                else:
                    print(f"[{table_name}] R2 path {file_path} does not exist. Skipping.")
        else:
            print(f"[{table_name}] Local table already exists. Skipping sync.")
            
    # Create the unified_market view
    view_exists = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'unified_market'").fetchone()[0] > 0
    if force_refresh or not view_exists:
        print("[unified_market] Creating unified view from Dubai and Abu Dhabi market tables...")
        con.execute('''
            CREATE OR REPLACE VIEW unified_market AS 
            SELECT * FROM dubai_market 
            UNION ALL BY NAME 
            SELECT * FROM abudhabi_market
        ''')
        
    print("[unified_feature_prices] Creating view for feature prices...")
    con.execute('''
        CREATE OR REPLACE VIEW unified_feature_prices AS
        SELECT
            instance_date as date,
            area_name_en as area,
            property_usage_en as property_usage,
            property_sub_type_en as property_type,
            rooms_en as room_type,
            trans_group_en as transaction_type,
            reg_type_en as reg_type,
            actual_worth as sale_price,
            meter_sale_price as rate_sqm,
            has_parking,
            floors,
            swimming_pool,
            elevator,
            metro,
            'Dubai' as emirate,
            CAST(TRY_CAST(floors AS FLOAT) AS INTEGER) as floor_numeric,
            CASE 
                WHEN TRY_CAST(floors AS FLOAT) <= 10 THEN '1-10'
                WHEN TRY_CAST(floors AS FLOAT) <= 20 THEN '11-20'
                WHEN TRY_CAST(floors AS FLOAT) <= 30 THEN '21-30'
                WHEN TRY_CAST(floors AS FLOAT) <= 40 THEN '31-40'
                WHEN TRY_CAST(floors AS FLOAT) <= 50 THEN '41-50'
                WHEN TRY_CAST(floors AS FLOAT) > 50 THEN '50+'
                ELSE 'Unknown'
            END as floor_bin
        FROM feature_prices
    ''')
    
    con.close()

if __name__ == "__main__":
    init_db(force_refresh=True)

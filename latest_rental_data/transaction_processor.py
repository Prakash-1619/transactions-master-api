import pandas as pd

def get_processed_transaction_data():
    # Define required columns for the yield calculation
    cols_required = ['actual_worth', 'rooms_en', 'area_name_en', 'instance_date']
    
    # 1. Load Historical
    trans_hist = pd.read_parquet('/home/ubuntu/Working_Space/data/latest_data/unit_res_trans_16.parquet')
    
    # 2. Load and Filter Latest (Excluding Gifts)
    latest_raw = pd.read_csv('/home/ubuntu/Working_Space/data/DLD_DATA/transactions-2026-04-21.csv')
    latest_raw = latest_raw[latest_raw['GROUP_EN'] != 'Gifts'].copy()
    
    # 3. Rename Latest
    trans_mapping = {
        'TRANS_VALUE': 'actual_worth',
        'ROOMS_EN': 'rooms_en',
        'AREA_EN': 'area_name_en',
        'INSTANCE_DATE': 'instance_date'
    }
    latest_renamed = latest_raw.rename(columns=trans_mapping)
    
    # 4. Combine Subsets and create Year
    df_final_trans = pd.concat([trans_hist[cols_required], latest_renamed[cols_required]], ignore_index=True)
    df_final_trans['year'] = pd.to_datetime(df_final_trans['instance_date']).dt.year
    
    return df_final_trans
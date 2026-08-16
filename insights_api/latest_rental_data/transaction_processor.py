import pandas as pd
from .s3_manager import get_storage_options

def process_and_save_transactions():
    """
    Downloads the pre-processed transactions from R2, ensures columns are mapped, 
    and saves to ROI Data in R2.
    """
    input_path = "s3://dubai/data/processed/unit_res_trans_16.parquet"
    output_path = "s3://dubai/data/ROI_data/cleaned_transactions.parquet"
    storage_options = get_storage_options()

    print(f"Reading transaction data from {input_path}...")
    df_trans = pd.read_parquet(input_path, storage_options=storage_options)
    
    cols_required = ['actual_worth', 'rooms_en', 'area_name_en', 'instance_date']
    
    # Map columns to expected standard
    for col in cols_required:
        if col not in df_trans.columns:
            if col.upper() in df_trans.columns:
                df_trans = df_trans.rename(columns={col.upper(): col})
            if col == 'actual_worth' and 'TRANS_VALUE' in df_trans.columns:
                df_trans = df_trans.rename(columns={'TRANS_VALUE': 'actual_worth'})
            if col == 'rooms_en' and 'ROOMS_EN' in df_trans.columns:
                df_trans = df_trans.rename(columns={'ROOMS_EN': 'rooms_en'})
            if col == 'area_name_en' and 'AREA_EN' in df_trans.columns:
                df_trans = df_trans.rename(columns={'AREA_EN': 'area_name_en'})
            if col == 'instance_date' and 'INSTANCE_DATE' in df_trans.columns:
                df_trans = df_trans.rename(columns={'INSTANCE_DATE': 'instance_date'})

    if 'instance_date' in df_trans.columns:
        df_trans['year'] = pd.to_datetime(df_trans['instance_date'], errors='coerce').dt.year
    else:
        df_trans['year'] = 2026

    print(f"Uploading cleaned transaction data to {output_path}...")
    df_trans.to_parquet(output_path, storage_options=storage_options, index=False)
    print("Transaction processing complete.")
    return df_trans


def get_processed_transaction_data():
    """
    Returns the cleaned transactions dataframe. Downloads from cache if exists.
    """
    output_path = "s3://dubai/data/ROI_data/cleaned_transactions.parquet"
    storage_options = get_storage_options()
    
    try:
        return pd.read_parquet(output_path, storage_options=storage_options)
    except Exception as e:
        print(f"Cleaned transactions not found in R2 ({e}). Triggering processor...")
        return process_and_save_transactions()
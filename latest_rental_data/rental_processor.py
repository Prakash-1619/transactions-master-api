import pandas as pd
from .s3_manager import get_storage_options

def process_and_save_rentals():
    """
    Downloads rent contracts, filters for residential units, maps rooms,
    removes outliers (procedure_area, annual_amount), and uploads to R2.
    """
    input_path = "s3://dubai/data/raw/rent_contracts.parquet"
    output_path = "s3://dubai/data/ROI_data/cleaned_rentals.parquet"
    storage_options = get_storage_options()

    print(f"Reading rental data from {input_path}...")
    df = pd.read_parquet(input_path, storage_options=storage_options)

    print("Filtering for Residential Units...")
    if 'property_type_en' in df.columns and 'property_usage_en' in df.columns:
        df = df[(df['property_type_en'].str.lower() == 'unit') & (df['property_usage_en'].str.lower() == 'residential')]
    
    # Ensure year exists
    if 'year' not in df.columns and 'contract_start_date' in df.columns:
        df['year'] = pd.to_datetime(df['contract_start_date'], errors='coerce').dt.year
    
    # Map ejari_property_sub_type_en to room_type
    def map_room(x):
        if pd.isna(x):
            return None
        x_str = str(x).lower()
        if 'studio' in x_str: return 'Studio'
        if '1' in x_str and 'bed' in x_str: return '1 B/R'
        if '2' in x_str and 'bed' in x_str: return '2 B/R'
        if '3' in x_str and 'bed' in x_str: return '3 B/R'
        if '4' in x_str and 'bed' in x_str: return '4 B/R'
        return None
        
    if 'ejari_property_sub_type_en' in df.columns:
        df['room_type'] = df['ejari_property_sub_type_en'].apply(map_room)
    else:
        df['room_type'] = None
        
    df = df.dropna(subset=['room_type', 'area_name_en', 'procedure_area', 'annual_amount'])
    
    # Outlier Removal
    print("Removing Outliers (procedure_area and annual_amount)...")
    cleaned_groups = []
    
    grouped = df.groupby(['area_name_en', 'room_type'])
    for name, group in grouped:
        if len(group) < 10:
            continue # Skip groups that are too small to have meaningful percentiles
            
        area_lower = group['procedure_area'].quantile(0.02)
        area_upper = group['procedure_area'].quantile(0.98)
        
        price_lower = group['annual_amount'].quantile(0.02)
        price_upper = group['annual_amount'].quantile(0.98)
        
        filtered = group[
            (group['procedure_area'] >= area_lower) & (group['procedure_area'] <= area_upper) &
            (group['annual_amount'] >= price_lower) & (group['annual_amount'] <= price_upper)
        ]
        cleaned_groups.append(filtered)
        
    if cleaned_groups:
        df_cleaned = pd.concat(cleaned_groups)
    else:
        df_cleaned = pd.DataFrame(columns=df.columns)

    print(f"Uploading cleaned rental data to {output_path}...")
    df_cleaned.to_parquet(output_path, storage_options=storage_options, index=False)
    print("Rental processing complete.")
    return df_cleaned

def get_processed_rental_data():
    """
    Returns the cleaned rentals dataframe. Downloads from cache if exists.
    """
    output_path = "s3://dubai/data/ROI_data/cleaned_rentals.parquet"
    storage_options = get_storage_options()
    
    try:
        return pd.read_parquet(output_path, storage_options=storage_options)
    except Exception as e:
        print(f"Cleaned rentals not found in R2 ({e}). Triggering processor...")
        return process_and_save_rentals()
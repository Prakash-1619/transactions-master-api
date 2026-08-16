import os
import pandas as pd
from .rental_processor import get_processed_rental_data
from .transaction_processor import get_processed_transaction_data
from .yield_calculator import calculate_yearly_yield
from .s3_manager import get_storage_options, get_s3_fs

def check_missing_coordinates(yield_df):
    """
    Checks if there are any new areas in the processed yield data that are missing 
    from the local Area_co_ordinates_rental_areas.csv file.
    """
    coords_path = "s3://dubai/data/ROI_data/Area_co_ordinates_rental_areas.csv"
    fs = get_s3_fs()
    check_path = coords_path.replace('s3://', '')
    if not fs.exists(check_path):
        print("Missing coordinates file entirely!")
        return

    coords_df = pd.read_csv(coords_path, storage_options=get_storage_options())
    known_areas = set(coords_df['area_name_en'].str.lower().dropna())
    
    current_areas = set(yield_df['area_name_en'].str.lower().dropna())
    
    missing = current_areas - known_areas
    if missing:
        print("\n" + "="*50)
        print("WARNING: MISSING AREA COORDINATES!")
        print("The following areas exist in the data but not in Area_co_ordinates_rental_areas.csv:")
        for area in sorted(missing):
            print(f" - {area}")
        print("Please add them to the CSV for GPS searches to work correctly.")
        print("="*50 + "\n")
    else:
        print("All areas have valid coordinates.")

def refresh_roi_pipeline():
    print("--- Starting ROI Pipeline ---")
    
    print("Processing Rental data (with outliers removed)...")
    df_rent = get_processed_rental_data()
    
    print("Processing Transaction data...")
    df_trans = get_processed_transaction_data()
    
    print("Calculating Yearly Rental Yields...")
    final_report = calculate_yearly_yield(df_rent, df_trans)
    
    check_missing_coordinates(final_report)
    
    # Save to R2
    s3_path = "s3://dubai/data/ROI_data/dubai_market_yield_report.csv"
    print(f"Uploading yield report to {s3_path}...")
    final_report.to_csv(s3_path, storage_options=get_storage_options(), index=False)
    
    print("Pipeline Complete.")
    return final_report

if __name__ == "__main__":
    refresh_roi_pipeline()
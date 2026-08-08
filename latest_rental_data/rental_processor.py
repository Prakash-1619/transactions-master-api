import pandas as pd
import joblib

def get_processed_rental_data():
    # 1. Load Historical Data
    rental_historical = pd.read_parquet('/home/ubuntu/Working_Space/data/rental_data/df_diff_2%.parquet')
    
    # 2. Load 2026 Raw Data
    df_rent_raw = pd.read_csv('/home/ubuntu/Working_Space/data/DLD_DATA/rents-2026-04-21.csv')
    
    # Filter for Flats only to match the ML model's scope
    df_2026 = df_rent_raw[
        (df_rent_raw['PROP_TYPE_EN'] == "Unit") & 
        (df_rent_raw['PROP_SUB_TYPE_EN'] == 'Flat')
    ].copy()
    
    # 3. ML Room Filling
    model = joblib.load('room_classifier_model.joblib')
    encoder = joblib.load('room_type_encoder.joblib')
    
    # Ensure feature names match what the model expects
    X = df_2026[['ACTUAL_AREA', 'ANNUAL_AMOUNT']].fillna(0)
    X.columns = ['actual_area', 'annual_amount']
    
    preds = model.predict(X)
    df_2026['room_type'] = encoder.inverse_transform(preds)
    
    # 4. Rename to match Historical Schema
    mapping = {
        'START_DATE': 'contract_start_date',
        'AREA_EN': 'area_name_en',
        'ANNUAL_AMOUNT': 'annual_amount',
        'ACTUAL_AREA': 'actual_area'
    }
    df_2026 = df_2026.rename(columns=mapping)
    
    # 5. Combine and create Year
    df_combined = pd.concat([rental_historical, df_2026], axis=0, ignore_index=True)
    df_combined['year'] = pd.to_datetime(df_combined['contract_start_date']).dt.year
    
    return df_combined
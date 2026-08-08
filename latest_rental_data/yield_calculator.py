import pandas as pd

def calculate_yearly_yield(df_rent, df_trans):
    # Standardize Room IDs
    room_id_map = {
        'Studio': 0, '1BHK': 1, '1 B/R': 1, 
        '2BHK': 2, '2 B/R': 2, 
        '3BHK': 3, '3 B/R': 3, 
        '4BHK': 4, '4 B/R': 4
    }
    
    df_rent['room_id'] = df_rent['room_type'].map(room_id_map)
    df_trans['room_id'] = df_trans['rooms_en'].map(room_id_map)
    
    # Drop rows that don't match our specific room types (e.g., Offices)
    df_rent = df_rent.dropna(subset=['room_id'])
    df_trans = df_trans.dropna(subset=['room_id'])

    # Aggregate Rental Data
    rent_stats = df_rent.groupby(['year', 'area_name_en', 'room_id'])['annual_amount'].agg(
        median_annual_rent='median', 
        min_annual_rent='min', 
        max_annual_rent='max'
    ).reset_index()
    
    # Aggregate Transaction Data
    trans_stats = df_trans.groupby(['year', 'area_name_en', 'room_id'])['actual_worth'].median().reset_index()
    trans_stats.rename(columns={'actual_worth': 'median_transaction_amount'}, inplace=True)
    
    # Merge on Year, Area, and Room ID
    yield_df = pd.merge(rent_stats, trans_stats, on=['year', 'area_name_en', 'room_id'], how='inner')
    
    # Final Formula
    yield_df['rental_yield_percentage'] = ((yield_df['median_annual_rent'] / yield_df['median_transaction_amount']) * 100).round()
    
    # Add human-readable labels
    id_to_label = {0: 'Studio', 1: '1 BHK', 2: '2 BHK', 3: '3 BHK', 4: '4 BHK'}
    yield_df['rooms_en'] = yield_df['room_id'].map(id_to_label)
    
    # Sort for the final report
    return yield_df.sort_values(by=['year', 'area_name_en', 'room_id'], ascending=[False, True, True])
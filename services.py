import pandas as pd
from schemas import DataFilter

def clean_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans top 1% and bottom 1% outliers grouped by Asset Class 
    for Area, Price, and Rate sequentially.
    """
    cols_to_clean = [
        'Property Sold Area (SQM)', 
        'Property Sale Price (AED)', 
        'Rate (AED per SQM)'
    ]
    
    if 'Asset Class' not in df.columns:
        return df

    def filter_group_outliers(group):
        mask = pd.Series(True, index=group.index)
        for col in cols_to_clean:
            if col in group.columns:
                q_low = group[col].quantile(0.01)
                q_high = group[col].quantile(0.99)
                col_mask = (group[col] >= q_low) & (group[col] <= q_high) | group[col].isna()
                mask = mask & col_mask
        return group[mask]

    return df.groupby('Asset Class', group_keys=False).apply(filter_group_outliers)

import math
import os
import config

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

abudhabi_coords_df = pd.DataFrame()
if os.path.exists(config.ABUDHABI_COORDS_FILE):
    abudhabi_coords_df = pd.read_csv(config.ABUDHABI_COORDS_FILE)
    abudhabi_coords_df = abudhabi_coords_df.rename(columns={'District': 'area_name', 'Latitude': 'latitude', 'Longitude': 'longitude'})

def apply_filters(table_name: str, filters: DataFilter) -> pd.DataFrame:
    from duckdb_setup import get_db_connection
    con = get_db_connection(read_only=True)
    
    where_clauses = []
    params = []
    
    # Coordinate Filtering
    if filters.latitude is not None and filters.longitude is not None and not abudhabi_coords_df.empty:
        temp_coords = abudhabi_coords_df.copy()
        temp_coords['Latitude'] = pd.to_numeric(temp_coords['latitude'], errors='coerce')
        temp_coords['Longitude'] = pd.to_numeric(temp_coords['longitude'], errors='coerce')
        temp_coords = temp_coords.dropna(subset=['Latitude', 'Longitude'])
        
        if not temp_coords.empty:
            temp_coords['dist'] = temp_coords.apply(
                lambda r: calculate_distance(filters.latitude, filters.longitude, r['Latitude'], r['Longitude']), axis=1
            )
            nearest = temp_coords.sort_values('dist').iloc[0]
            radius_threshold = filters.radius if filters.radius is not None else config.DEFAULT_RADIUS_KM
            if nearest['dist'] <= radius_threshold:
                nearest_district = str(nearest['area_name']).strip()
                where_clauses.append("lower(\"District\") = lower(?)")
                params.append(nearest_district)
            else:
                empty_cols = [c for c in con.execute(f"DESCRIBE {table_name}").df()['column_name'].tolist()]
                return pd.DataFrame(columns=empty_cols)
                
    # 1. Timeframe filtering
    if filters.start_date:
        where_clauses.append("\"Sale Application Date\" >= ?")
        params.append(pd.to_datetime(filters.start_date))
    if filters.end_date:
        where_clauses.append("\"Sale Application Date\" <= ?")
        params.append(pd.to_datetime(filters.end_date))
        
    # 2. Categorical filtering with string splitting
    filter_map = {
        'Asset Class': filters.asset_class,
        'Property Type': filters.property_type,
        'Property Layout': filters.property_layout,
        'District': filters.district,
        'Community': filters.community,
        'Project Name': filters.project_name,
        'Sale Sequence': filters.sale_sequence
    }
    
    for col, value_str in filter_map.items():
        if value_str:  
            values_list = [val.strip() for val in value_str.split(',') if val.strip()]
            if values_list:
                placeholders = ', '.join(['?'] * len(values_list))
                where_clauses.append(f'"{col}" IN ({placeholders})')
                params.extend(values_list)
                
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = f"SELECT * FROM {table_name} {where_sql}"
    return con.execute(query, params).df()
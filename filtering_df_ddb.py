# filtering_df.py
import pandas as pd
import numpy as np
import os
import duckdb
from datetime import datetime
from config import (
    ROOM_TO_ID, MIN_AREA_BY_SUBTYPE, RETURN_COLUMNS,
    ALLOWED_TRANS_GROUPS, ALLOWED_PROPERTY_TYPES, ALLOWED_PROPERTY_USAGES,
    BASELINE_START_DATE, COLUMNS_TO_DROP, HARD_MIN_PERCENTILE, HARD_MAX_PERCENTILE,
    GRANULAR_LOWER_PERCENTILE, GRANULAR_UPPER_PERCENTILE, DEFAULT_RADIUS_KM,
    CACHE_FILE
)

def load_and_prep_data(trans_path, proj_path, dev_path, coords_path):
    df = pd.read_csv(trans_path, compression=None, low_memory=False)
    id_cols = [col for col in df.columns if col.endswith('_id')]
    ar_cols = [col for col in df.columns if col.endswith('_ar')]
    df = df.drop(columns=id_cols + ar_cols)
    df = df.drop(columns=[c for c in COLUMNS_TO_DROP if c in df.columns])
    
    df = df[df['trans_group_en'].isin(ALLOWED_TRANS_GROUPS)]
    df = df[df['property_type_en'].isin(ALLOWED_PROPERTY_TYPES)]
    df = df[df['property_usage_en'].isin(ALLOWED_PROPERTY_USAGES)]
    
    df['instance_date'] = pd.to_datetime(df['instance_date'], errors='coerce')
    df = df[df['instance_date'] >= pd.to_datetime(BASELINE_START_DATE)]

    projects = pd.read_csv(proj_path, compression=None, low_memory=False)
    project_cols = ['completion_date', 'master_project_en', 'no_of_lands', 'no_of_buildings', 
                    'no_of_villas', 'no_of_units', 'project_number', 'developer_number', 
                    'project_start_date', 'project_end_date']
    project_df = projects[[c for c in project_cols if c in projects.columns]]

    developers = pd.read_csv(dev_path, compression=None, low_memory=False)
    dev_cols = ['developer_number', 'developer_name_en']
    dev_df = developers[[c for c in dev_cols if c in developers.columns]]

    combined_project_dev = project_df.merge(dev_df, on='developer_number', how='left')
    combined_df = df.merge(combined_project_dev, on='project_number', how='left')
    
    coords_df = pd.read_csv(coords_path)
    coords_df = coords_df.rename(columns={'lat': 'latitude', 'long': 'longitude'})
    combined_df = combined_df.merge(coords_df[['area_name', 'latitude', 'longitude']],
                                    left_on='area_name_en', right_on='area_name', how='left')
    return combined_df.drop(columns=['area_name'])

def clean_area_outliers(df):
    cleaned_list = []
    df_clean = df.copy()
    df_clean['rooms_en'] = df_clean['rooms_en'].fillna('Unknown')
    room_groups = df_clean.groupby('rooms_en')
    for room, group in room_groups:
        room_id = ROOM_TO_ID.get(room, 0)
        if room_id in MIN_AREA_BY_SUBTYPE:
            lower_limit = MIN_AREA_BY_SUBTYPE[room_id]
            upper_limit = group['procedure_area'].quantile(HARD_MAX_PERCENTILE)
        else:
            lower_limit = group['procedure_area'].quantile(HARD_MIN_PERCENTILE)
            upper_limit = group['procedure_area'].quantile(HARD_MAX_PERCENTILE)
        filtered_group = group[(group['procedure_area'] >= lower_limit) & (group['procedure_area'] <= upper_limit)]
        cleaned_list.append(filtered_group)
    return pd.concat(cleaned_list)

def remove_granular_outliers(df, price_col='meter_sale_price'):
    counts = df.groupby(['area_name_en', 'rooms_en'])[price_col].transform('count')
    valid_df = df[counts >= 10]
    invalid_df = df[counts < 10]
    if not valid_df.empty:
        lower = valid_df.groupby(['area_name_en', 'rooms_en'])[price_col].transform(lambda x: x.quantile(GRANULAR_LOWER_PERCENTILE))
        upper = valid_df.groupby(['area_name_en', 'rooms_en'])[price_col].transform(lambda x: x.quantile(GRANULAR_UPPER_PERCENTILE))
        cleaned_valid = valid_df[(valid_df[price_col] >= lower) & (valid_df[price_col] <= upper)]
        return pd.concat([cleaned_valid, invalid_df])
    return df

def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))

def apply_filters(df, filters: dict):
    df_filtered = df.copy()
    
    # --- 1) Emirate Filter ---
    emirate_filter = filters.get('emirate')
    if emirate_filter:
        if emirate_filter.lower() == 'dubai':
            # DLD data is already Dubai, so we pass to allow all other filters to apply normally
            pass 
        else:
            # If expanding to other emirates later, filter by the column
            if 'emirate' in df_filtered.columns:
                df_filtered = df_filtered[df_filtered['emirate'].str.lower() == emirate_filter.lower()]
            else:
                # If a different emirate is requested but no data exists for it, return empty
                return df_filtered.iloc[0:0]

    # --- 2) Date / Time Filters ---
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    time_preset = filters.get('time_preset')
    today = datetime.today()
    
    if start_date and end_date:
        df_filtered = df_filtered[(df_filtered['instance_date'] >= pd.to_datetime(start_date)) & 
                                  (df_filtered['instance_date'] <= pd.to_datetime(end_date))]
    elif time_preset == 'current_month':
        df_filtered = df_filtered[df_filtered['instance_date'] >= today.replace(day=1)]
    elif time_preset == 'current_year':
        df_filtered = df_filtered[df_filtered['instance_date'] >= today.replace(month=1, day=1)]
        
    # --- 3) Radius Filter (Lat / Lon) ---
    target_lat = filters.get('latitude')
    target_lon = filters.get('longitude')
    
    if target_lat is not None and target_lon is not None:
        # Extract dynamic radius from input, default to 3.0 km if not provided
        radius_val = filters.get('radius')
        radius_km = float(radius_val) if radius_val is not None else 3.0

        df_filtered['distance_temp'] = haversine_vectorized(
            target_lat, target_lon, df_filtered['latitude'], df_filtered['longitude']
        )
        
        # Apply the dynamic radius
        in_radius = df_filtered[df_filtered['distance_temp'] <= radius_km].copy()
        
        if not in_radius.empty:
            area_avg_dist = in_radius.groupby('area_name_en')['distance_temp'].mean()
            nearest_area = area_avg_dist.idxmin()
            df_filtered = df_filtered[df_filtered['area_name_en'] == nearest_area]
        else:
            df_filtered = df_filtered.iloc[0:0]

    # --- 4) Categorical Filters ---
    categorical_cols = [
        'trans_group_en', 'property_type_en', 'property_sub_type_en', 
        'property_usage_en', 'reg_type_en', 'area_name_en', 'rooms_en', 'has_parking'
    ]
    
    for col in categorical_cols:
        val = filters.get(col)
        if val:
            df_filtered = df_filtered[df_filtered[col] == val]

    # --- 5) Final Data Formatting & Sorting ---
    if 'has_parking' in df_filtered.columns:
        df_filtered['has_parking'] = df_filtered['has_parking'].replace(
            {1: 'Yes', 0: 'No', 1.0: 'Yes', 0.0: 'No'}
        )
        
    df_filtered = df_filtered.sort_values(by='instance_date', ascending=False)
    df_filtered['instance_date'] = df_filtered['instance_date'].astype(str)
    
    available_cols = [col for col in RETURN_COLUMNS if col in df_filtered.columns]
    
    return df_filtered[available_cols]

def apply_filters_duckdb(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Drop-in replacement for apply_filters() — identical (df, filters) ->
    DataFrame signature and identical filtering semantics, step for step:
    emirate check, date/time_preset filter, radius filter (snap to the
    single nearest area), categorical filters, has_parking mapping,
    sort by instance_date desc, subset to RETURN_COLUMNS.

    The difference is *how* the filtering runs: instead of chaining
    pandas boolean masks over the whole in-memory DataFrame, the
    DataFrame is registered as a zero-copy virtual table in DuckDB
    (via Arrow) and every predicate is pushed down into DuckDB's
    vectorized SQL engine. On larger DataFrames this is significantly
    faster than repeated pandas masking, especially once several
    filters are combined.

    To use this instead of apply_filters(), swap the import in
    dubai_router.py:
        from filtering_df import apply_filters_duckdb as apply_filters
    """
    con = duckdb.connect()
    con.register('raw_df', df)

    where_clauses = []
    params = []

    # --- 1) Emirate Filter (same semantics as apply_filters) ---
    emirate_filter = filters.get('emirate')
    if emirate_filter:
        if emirate_filter.lower() == 'dubai':
            pass  # DLD data is already Dubai
        else:
            if 'emirate' in df.columns:
                where_clauses.append("lower(emirate) = lower(?)")
                params.append(emirate_filter)
            else:
                con.close()
                empty_cols = [c for c in RETURN_COLUMNS if c in df.columns]
                return df.iloc[0:0][empty_cols]

    # --- 2) Date / Time Filters ---
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    time_preset = filters.get('time_preset')
    today = datetime.today()

    if start_date and end_date:
        where_clauses.append('"instance_date" >= ? AND "instance_date" <= ?')
        params.extend([pd.to_datetime(start_date), pd.to_datetime(end_date)])
    elif time_preset == 'current_month':
        where_clauses.append('"instance_date" >= ?')
        params.append(pd.Timestamp(today.replace(day=1)))
    elif time_preset == 'current_year':
        where_clauses.append('"instance_date" >= ?')
        params.append(pd.Timestamp(today.replace(month=1, day=1)))

    # --- 3) Categorical Filters ---
    categorical_cols = [
        'trans_group_en', 'property_type_en', 'property_sub_type_en',
        'property_usage_en', 'reg_type_en', 'area_name_en', 'rooms_en', 'has_parking'
    ]
    for col in categorical_cols:
        val = filters.get(col)
        if val:
            where_clauses.append(f'"{col}" = ?')
            params.append(val)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    base_query = f"SELECT * FROM raw_df {where_sql}"

    # --- 4) Radius Filter — snap to the single nearest area, same as apply_filters ---
    target_lat = filters.get('latitude')
    target_lon = filters.get('longitude')

    if target_lat is not None and target_lon is not None:
        radius_val = filters.get('radius')
        radius_km = float(radius_val) if radius_val is not None else 3.0

        nearest_area_sql = f"""
            WITH in_radius AS (
                SELECT area_name_en,
                    2 * 6371.0 * asin(sqrt(
                        pow(sin(radians(latitude - {target_lat}) / 2), 2) +
                        cos(radians({target_lat})) * cos(radians(latitude)) *
                        pow(sin(radians(longitude - {target_lon}) / 2), 2)
                    )) AS distance_temp
                FROM ({base_query})
            )
            SELECT area_name_en, avg(distance_temp) AS avg_dist
            FROM in_radius
            WHERE distance_temp <= {radius_km}
            GROUP BY area_name_en
            ORDER BY avg_dist ASC
            LIMIT 1
        """
        nearest = con.execute(nearest_area_sql, params).df()

        if nearest.empty:
            con.close()
            empty_cols = [c for c in RETURN_COLUMNS if c in df.columns]
            return df.iloc[0:0][empty_cols]

        nearest_area = nearest.iloc[0]['area_name_en']
        where_clauses.append('"area_name_en" = ?')
        params.append(nearest_area)
        base_query = f"SELECT * FROM raw_df WHERE {' AND '.join(where_clauses)}"

    result_df = con.execute(base_query, params).df()
    con.close()

    if result_df.empty:
        return result_df

    # --- 5) Final Data Formatting & Sorting (identical to apply_filters) ---
    if 'has_parking' in result_df.columns:
        result_df['has_parking'] = result_df['has_parking'].replace(
            {1: 'Yes', 0: 'No', 1.0: 'Yes', 0.0: 'No'}
        )

    result_df = result_df.sort_values(by='instance_date', ascending=False)
    result_df['instance_date'] = result_df['instance_date'].astype(str)

    available_cols = [col for col in RETURN_COLUMNS if col in result_df.columns]
    return result_df[available_cols]

# Logic for caching/processing
def get_processed_df(trans_path, proj_path, dev_path, coords_path):
    if os.path.exists(CACHE_FILE):
        print(f"Loading data from cache: {CACHE_FILE}")
        return pd.read_parquet(CACHE_FILE)
    return reprocess_and_save(trans_path, proj_path, dev_path, coords_path)

def reprocess_and_save(trans_path, proj_path, dev_path, coords_path):
    print("Processing raw data and saving to cache...")
    raw_df = load_and_prep_data(trans_path, proj_path, dev_path, coords_path)
    df_clean1 = clean_area_outliers(raw_df)
    df_final = remove_granular_outliers(df_clean1)
    df_final.to_parquet(CACHE_FILE, index=False)
    print("Data processed and cached successfully.")
    return df_final
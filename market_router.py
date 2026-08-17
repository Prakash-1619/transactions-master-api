from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import pandas as pd
import numpy as np
import os
import math
from latest_rental_data.s3_manager import get_storage_options, get_s3_fs
from config import AREA_COORDS_FILE, ABUDHABI_COORDS_FILE

router = APIRouter()

# Data Paths
DUBAI_DATA_URL = 's3://dubai/data/raw/transactions.parquet'
ABUDHABI_DATA_URL = 's3://abudhabi/data/raw/transactions.parquet'
DUBAI_CACHE_URL = 's3://dubai/data/insights_api/market_data.parquet'
ABUDHABI_CACHE_URL = 's3://abudhabi/data/insights_api/market_data.parquet'

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula to calculate distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def refresh_duckdb_cache():
    from duckdb_setup import init_db
    init_db(force_refresh=True)
    return True

def reprocess_data():
    storage_opts = get_storage_options()
    
    # 1. Load Dubai Data
    print("Loading Dubai Data...")
    df_dubai = pd.read_parquet(DUBAI_DATA_URL, storage_options=storage_opts)
    
    # Map Dubai Columns to Standard
    df_dubai = df_dubai.rename(columns={
        'instance_date': 'date',
        'area_name_en': 'area',
        'property_usage_en': 'property_usage',
        'property_sub_type_en': 'property_type',
        'rooms_en': 'room_type',
        'trans_group_en': 'transaction_type',
        'reg_type_en': 'reg_type',
        'project_name_en': 'project_name',
        'actual_worth': 'sale_price',
        'meter_sale_price': 'rate_sqm',
        'procedure_area': 'area_sqm'
    })
    df_dubai['emirate'] = 'Dubai'
    df_dubai['community'] = None # Dubai does not natively provide 'Community' column in the same way
    
    # 2. Load Abu Dhabi Data
    print("Loading Abu Dhabi Data...")
    df_ad = pd.read_parquet(ABUDHABI_DATA_URL, storage_options=storage_opts)
    
    # Map Abu Dhabi Columns to Standard
    df_ad = df_ad.rename(columns={
        'Sale Application Date': 'date',
        'District': 'area',
        'Community': 'community',
        'Asset Class': 'property_usage',
        'Property Type': 'property_type',
        'Property Layout': 'room_type',
        'Sale Application Type': 'reg_type',
        'Project Name': 'project_name',
        'Property Sale Price (AED)': 'sale_price',
        'Rate (AED per SQM)': 'rate_sqm',
        'Property Sold Area (SQM)': 'area_sqm'
    })
    
    # Terminology Alignment for Abu Dhabi
    df_ad['emirate'] = 'Abu Dhabi'
    df_ad['transaction_type'] = 'Sales' # All AD records in this file are Sales
    
    room_map = {'studio': 'Studio', '1 bed': '1 B/R', '2 beds': '2 B/R', '3 beds': '3 B/R', '4 beds': '4 B/R', '5 beds': '5 B/R'}
    if 'room_type' in df_ad.columns:
        df_ad['room_type'] = df_ad['room_type'].map(room_map).fillna(df_ad['room_type'])
    
    prop_map = {'apartment': 'Flat', 'villa': 'Villa', 'office': 'Office', 'land': 'Land'}
    if 'property_type' in df_ad.columns:
        df_ad['property_type'] = df_ad['property_type'].map(prop_map).fillna(df_ad['property_type'])
        
    reg_map = {'off-plan': 'Off-Plan Properties', 'ready': 'Existing Properties'}
    if 'reg_type' in df_ad.columns:
        df_ad['reg_type'] = df_ad['reg_type'].map(reg_map).fillna(df_ad['reg_type'])
        
    if 'property_usage' in df_ad.columns:
        df_ad['property_usage'] = df_ad['property_usage'].str.title()
        
    common_cols = [
        'date', 'emirate', 'area', 'community', 'property_usage', 'property_type', 
        'room_type', 'transaction_type', 'reg_type', 'project_name', 
        'sale_price', 'rate_sqm', 'area_sqm'
    ]
    
    df_dubai_final = df_dubai[common_cols].copy()
    df_dubai_final['date'] = pd.to_datetime(df_dubai_final['date'], errors='coerce')
    
    df_ad_final = df_ad[common_cols].copy()
    df_ad_final['date'] = pd.to_datetime(df_ad_final['date'], errors='coerce')
    
    # Cache to respective Insights API folders in R2
    print(f"Saving processed Dubai data to {DUBAI_CACHE_URL}...")
    df_dubai_final.to_parquet(DUBAI_CACHE_URL, storage_options=storage_opts, index=False)
    
    print(f"Saving processed Abu Dhabi data to {ABUDHABI_CACHE_URL}...")
    df_ad_final.to_parquet(ABUDHABI_CACHE_URL, storage_options=storage_opts, index=False)
    
    return pd.concat([df_dubai_final, df_ad_final], ignore_index=True)

# Load coordinates globally
coords_list = []
if os.path.exists(AREA_COORDS_FILE):
    df_dubai_coords = pd.read_csv(AREA_COORDS_FILE)
    df_dubai_coords = df_dubai_coords.rename(columns={'area_name_en': 'area_name', 'Latitude': 'latitude', 'Longitude': 'longitude'})
    df_dubai_coords['emirate_source'] = 'Dubai'
    coords_list.append(df_dubai_coords)

if os.path.exists(ABUDHABI_COORDS_FILE):
    df_ad_coords = pd.read_csv(ABUDHABI_COORDS_FILE)
    df_ad_coords = df_ad_coords.rename(columns={'District': 'area_name', 'Latitude': 'latitude', 'Longitude': 'longitude'})
    df_ad_coords['emirate_source'] = 'Abu Dhabi'
    coords_list.append(df_ad_coords)

if coords_list:
    coords_df = pd.concat(coords_list, ignore_index=True)
    coords_df['area_name'] = coords_df['area_name'].astype(str).str.strip().str.lower()
else:
    coords_df = pd.DataFrame()

@router.post("/refresh-data")
def refresh_data():
    try:
        reprocess_data()
        refresh_duckdb_cache()
        return {"status": "success", "message": "Unified market data refreshed from S3 and cached in DuckDB."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights")
@router.get("/insights/unified")
def get_market_insights(
    emirate: Optional[str] = Query(None, description="Dubai or Abu Dhabi"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    lat: Optional[float] = Query(None, description="Latitude for nearest area filtering"),
    lon: Optional[float] = Query(None, description="Longitude for nearest area filtering"),
    page: int = Query(1, ge=1),
    rows_per_page: int = Query(25, ge=0, le=50)
):
    from duckdb_setup import get_db_connection
    con = get_db_connection(read_only=True)
    
    where_clauses = []
    params = []
    
    # Coordinate Filtering (dynamically infers Emirate if found)
    inferred_area = None
    if lat is not None and lon is not None and not coords_df.empty:
        # Find closest area across both emirates
        temp_coords = coords_df.copy()
        temp_coords['Latitude'] = pd.to_numeric(temp_coords['latitude'], errors='coerce')
        temp_coords['Longitude'] = pd.to_numeric(temp_coords['longitude'], errors='coerce')
        temp_coords = temp_coords.dropna(subset=['Latitude', 'Longitude'])
        
        if not temp_coords.empty:
            temp_coords['dist'] = temp_coords.apply(
                lambda r: calculate_distance(lat, lon, r['Latitude'], r['Longitude']), axis=1
            )
            nearest = temp_coords.sort_values('dist').iloc[0]
            from config import DEFAULT_RADIUS_KM
            if nearest['dist'] <= DEFAULT_RADIUS_KM:  # Use config radius threshold
                inferred_area = str(nearest['area_name']).lower()
                # Dynamically set or override emirate based on the nearest coordinates
                emirate = nearest['emirate_source']
            else:
                df = pd.DataFrame(columns=['date', 'emirate', 'area', 'community', 'property_usage', 'property_type', 'room_type', 'transaction_type', 'reg_type', 'project_name', 'sale_price', 'rate_sqm', 'area_sqm', 'latitude', 'longitude'])
                return {"pagination": {"page": page, "rows_per_page": rows_per_page, "total_records": 0, "total_pages": 0}, "distributions": {}, "mapped_coordinates": [], "data": []}

    # Filter by Emirate (either manually provided or inferred)
    if emirate:
        where_clauses.append("lower(emirate) = lower(?)")
        params.append(emirate.strip())
    elif not emirate and (lat is None or lon is None):
        # If no emirate is provided and no coordinates were given, return empty df
        return {"pagination": {"page": page, "rows_per_page": rows_per_page, "total_records": 0, "total_pages": 0}, "distributions": {}, "mapped_coordinates": [], "data": []}
    
    # Apply the area filter if coordinates successfully inferred it
    if inferred_area:
        where_clauses.append("lower(area) = ?")
        params.append(inferred_area)

    # Timeframe filtering
    if start_date:
        where_clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("date <= ?")
        params.append(end_date)
        
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = f"SELECT * FROM unified_market {where_sql}"
    df = con.execute(query, params).df()
        
    # 1. Distributions (rooms, transaction type, reg type, top 10 projects)
    distributions = {}
    
    for col, display_name in [('room_type', 'rooms_en'), ('transaction_type', 'transaction_type'), ('reg_type', 'regtype')]:
        if col in df.columns:
            counts = df[col].value_counts().reset_index()
            counts.columns = [display_name, 'count']
            distributions[display_name] = counts.to_dict(orient='records')
            
    if 'project_name' in df.columns:
        top_projects = df['project_name'].value_counts().head(10).reset_index()
        top_projects.columns = ['project_name', 'count']
        distributions['top_10_projects'] = top_projects.to_dict(orient='records')
        
    # 2. Coordinates Mapping
    areas_in_data = set(df['area'].dropna().unique())
    communities_in_data = set(df['community'].dropna().unique())
    
    mapped_coordinates = []
    
    # Try mapping Dubai areas (using existing coords file)
    if not coords_df.empty:
        for a in areas_in_data:
            match = coords_df[coords_df['area_name'] == str(a).lower()]
            if not match.empty:
                mapped_coordinates.append({
                    "name": a,
                    "type": "area",
                    "latitude": match.iloc[0]['latitude'],
                    "longitude": match.iloc[0]['longitude']
                })
            else:
                # User asked to try to get communities coordinates as well. 
                # If they don't exist in CSV, we return None to satisfy requirements gracefully.
                mapped_coordinates.append({
                    "name": a,
                    "type": "area",
                    "latitude": None,
                    "longitude": None
                })
        
        # Attach communities (mostly for Abu Dhabi where coords are missing, return None for now)
        for c in communities_in_data:
            mapped_coordinates.append({
                "name": c,
                "type": "community",
                "latitude": None,
                "longitude": None
            })
    else:
        # Fallback if no coordinates file at all
        for a in areas_in_data: mapped_coordinates.append({"name": a, "type": "area", "latitude": None, "longitude": None})
        for c in communities_in_data: mapped_coordinates.append({"name": c, "type": "community", "latitude": None, "longitude": None})

    # 3. Pagination and Sorting
    df = df.sort_values('date', ascending=False)
    
    total_records = len(df)
    total_pages = (total_records + rows_per_page - 1) // rows_per_page if rows_per_page > 0 else 1
    
    if rows_per_page > 0:
        start_idx = (page - 1) * rows_per_page
        end_idx = start_idx + rows_per_page
        page_df = df.iloc[start_idx:end_idx].copy()
    else:
        page_df = pd.DataFrame()
        
    if not page_df.empty:
        page_df['date'] = page_df['date'].dt.strftime('%Y-%m-%d')
        
    return {
        "pagination": {
            "page": page,
            "rows_per_page": rows_per_page,
            "total_records": total_records,
            "total_pages": total_pages
        },
        "distributions": distributions,
        "coordinates_mapping": mapped_coordinates,
        "transactions": page_df.replace({np.nan: None}).to_dict(orient="records")
    }
from insights_api.unified_router import filter_data

@router.get("/insights/trends")
def get_market_trends(
    emirate: Optional[str] = Query(None, description="Dubai or Abu Dhabi"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    lat: Optional[float] = Query(None, description="Latitude for nearest area filtering"),
    lon: Optional[float] = Query(None, description="Longitude for nearest area filtering"),
    reg_type: Optional[str] = Query(None, description="Registration type"),
    transaction_type: Optional[str] = Query(None, description="Transaction type"),
    area: Optional[str] = Query(None, description="Area name"),
    room_type: Optional[str] = Query(None, description="Room type"),
    property_type: Optional[str] = Query(None, description="Property type"),
    comparison_type: str = Query("yoy", description="yoy, qoq, or mom. Defaults to yoy."),
    growth_metric: str = Query("median_sale_price", description="Metric to calculate growth on"),
    group_by: Optional[str] = Query(None, description="Column name to break down market trends (e.g. area)")
):
    df = filter_data('unified_market', False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type, None)
    
    shift_period = 12
    if comparison_type.lower() == 'qoq':
        shift_period = 3
    elif comparison_type.lower() == 'mom':
        shift_period = 1
        
    # Aggregation
    market_trend = df.groupby('Month_Year').agg(
        Volume=('sale_price', 'size'),
        Total_Sales_AED=('sale_price', 'sum'),
        Median_Sale_Price=('sale_price', 'median'),
        Median_Rate=('rate_sqm', 'median')
    ).reset_index()
    # We do not have rental actual worth in global_df currently, mock to null
    market_trend['Median_Annual_Rent'] = None
    
    metric_col_map = {
        "volume": "Volume",
        "total_sales": "Total_Sales_AED",
        "median_sale_price": "Median_Sale_Price",
        "median_rate": "Median_Rate",
        "median_annual_rent": "Median_Annual_Rent"
    }
    target_metric_col = metric_col_map.get(growth_metric.lower(), "Median_Sale_Price")
    
    growth_col_name = f"{comparison_type.upper()}_{growth_metric.upper()}_GROWTH"
    
    if target_metric_col in market_trend.columns and market_trend[target_metric_col].notna().any():
        market_trend[growth_col_name] = market_trend[target_metric_col].astype(float).pct_change(periods=shift_period)
    else:
        market_trend[growth_col_name] = None
    
    market_trend['Month_Year'] = market_trend['Month_Year'].astype(str)
    market_trend = market_trend.replace([np.inf, -np.inf], np.nan)
    market_trend = market_trend.astype(object).where(pd.notnull(market_trend), None)
    
    group_insights = {}
    if group_by and group_by in df.columns:
        group_data = df.groupby([group_by, 'Month_Year']).agg(
            Volume=('sale_price', 'size'),
            Total_Sales_AED=('sale_price', 'sum'),
            Median_Sale_Price=('sale_price', 'median'),
            Median_Rate=('rate_sqm', 'median')
        ).reset_index()
        group_data['Median_Annual_Rent'] = None
        
        group_data = group_data.sort_values([group_by, 'Month_Year'])
        
        if target_metric_col in group_data.columns and group_data[target_metric_col].notna().any():
            group_data[growth_col_name] = group_data.groupby(group_by)[target_metric_col].pct_change(periods=shift_period)
        else:
            group_data[growth_col_name] = None
            
        group_data['Month_Year'] = group_data['Month_Year'].astype(str)
        group_data = group_data.replace([np.inf, -np.inf], np.nan)
        group_data = group_data.astype(object).where(pd.notnull(group_data), None)
        
        for group_name, df_group in group_data.groupby(group_by):
            group_insights[str(group_name)] = df_group.tail(1).to_dict(orient="records")[0]
            
    # Include distributions for a quick overview
    distributions = {}
    for col, display_name in [('room_type', 'rooms_en'), ('transaction_type', 'transaction_type'), ('reg_type', 'regtype')]:
        if col in df.columns:
            counts = df[col].value_counts().reset_index()
            counts.columns = [display_name, 'count']
            distributions[display_name] = counts.to_dict(orient='records')
            
    return {
        "analysis_params": {
            "comparison_type": comparison_type.upper(),
            "growth_metric_tracked": growth_metric.upper(),
            "timeframe_analyzed": {
                "start": df['date'].min().strftime('%Y-%m-%d'),
                "end": df['date'].max().strftime('%Y-%m-%d')
            }
        },
        "overall_market_latest": market_trend.iloc[-1].to_dict() if not market_trend.empty else {},
        "overall_market_history": market_trend.to_dict(orient="records"),
        "grouped_breakdown": group_insights if group_insights else "No group_by column specified.",
        "distributions": distributions
    }

@router.get("/insights/rental_trends")
def get_rental_trends(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    lat: Optional[float] = Query(None, description="Latitude for nearest area filtering"),
    lon: Optional[float] = Query(None, description="Longitude for nearest area filtering"),
    area: Optional[str] = Query(None, description="Area name"),
    room_type: Optional[str] = Query(None, description="Room type"),
    property_type: Optional[str] = Query(None, description="Property type"),
    comparison_type: str = Query("yoy", description="yoy, qoq, or mom. Defaults to yoy."),
    growth_metric: str = Query("median_annual_rent", description="Metric to calculate growth on"),
    group_by: Optional[str] = Query(None, description="Column name to break down market trends (e.g. area_name_en)")
):
    df = filter_data('unified_rental', True, emirate, lat, lon, area, start_date, end_date, room_type, property_type, None, None, None)
    if df.empty:
        return {"message": "Rental data is not available."}
    
    shift_period = 12
    if comparison_type.lower() == 'qoq':
        shift_period = 3
    elif comparison_type.lower() == 'mom':
        shift_period = 1
        
    # Aggregation
    market_trend = df.groupby('Month_Year').agg(
        Volume=('annual_amount', 'size'),
        Total_Sales_AED=('annual_amount', 'sum'),
        Median_Annual_Rent=('annual_amount', 'median')
    ).reset_index()
    market_trend['Median_Sale_Price'] = None
    market_trend['Median_Rate'] = None
    
    metric_col_map = {
        "volume": "Volume",
        "total_sales": "Total_Sales_AED",
        "median_annual_rent": "Median_Annual_Rent"
    }
    target_metric_col = metric_col_map.get(growth_metric.lower(), "Median_Annual_Rent")
    
    growth_col_name = f"{comparison_type.upper()}_{growth_metric.upper()}_GROWTH"
    
    if target_metric_col in market_trend.columns and market_trend[target_metric_col].notna().any():
        market_trend[growth_col_name] = market_trend[target_metric_col].astype(float).pct_change(periods=shift_period)
    else:
        market_trend[growth_col_name] = None
    
    market_trend['Month_Year'] = market_trend['Month_Year'].astype(str)
    market_trend = market_trend.replace([np.inf, -np.inf], np.nan)
    market_trend = market_trend.astype(object).where(pd.notnull(market_trend), None)
    
    group_insights = {}
    if group_by and group_by in df.columns:
        group_data = df.groupby([group_by, 'Month_Year']).agg(
            Volume=('annual_amount', 'size'),
            Total_Sales_AED=('annual_amount', 'sum'),
            Median_Annual_Rent=('annual_amount', 'median')
        ).reset_index()
        group_data['Median_Sale_Price'] = None
        group_data['Median_Rate'] = None
        
        group_data = group_data.sort_values([group_by, 'Month_Year'])
        
        if target_metric_col in group_data.columns and group_data[target_metric_col].notna().any():
            group_data[growth_col_name] = group_data.groupby(group_by)[target_metric_col].pct_change(periods=shift_period)
        else:
            group_data[growth_col_name] = None
            
        group_data['Month_Year'] = group_data['Month_Year'].astype(str)
        group_data = group_data.replace([np.inf, -np.inf], np.nan)
        group_data = group_data.astype(object).where(pd.notnull(group_data), None)
        
        for group_name, df_group in group_data.groupby(group_by):
            group_insights[str(group_name)] = df_group.tail(1).to_dict(orient="records")[0]
            
    # Include distributions
    distributions = {}
    for col, display_name in [('ejari_property_sub_type_en', 'room_type'), ('ejari_property_type_en', 'property_type')]:
        if col in df.columns:
            counts = df[col].value_counts().reset_index()
            counts.columns = [display_name, 'count']
            distributions[display_name] = counts.to_dict(orient='records')
            
    return {
        "analysis_params": {
            "comparison_type": comparison_type.upper(),
            "growth_metric_tracked": growth_metric.upper(),
            "timeframe_analyzed": {
                "start": df['contract_start_date'].min().strftime('%Y-%m-%d'),
                "end": df['contract_start_date'].max().strftime('%Y-%m-%d')
            }
        },
        "overall_market_latest": market_trend.iloc[-1].to_dict() if not market_trend.empty else {},
        "overall_market_history": market_trend.to_dict(orient="records"),
        "grouped_breakdown": group_insights if group_insights else "No group_by column specified.",
        "distributions": distributions

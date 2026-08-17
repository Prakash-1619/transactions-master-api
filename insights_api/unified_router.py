import os
from fastapi import APIRouter, Query
from typing import Optional
import duckdb
import pandas as pd
import numpy as np

# Global connection to DuckDB for remote querying
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET enable_object_cache=true;")
con.execute("SET enable_http_metadata_cache=true;")
con.execute("""
CREATE SECRET r2 (
    TYPE S3,
    KEY_ID 'c198c85bd01da0931eae24009fb2100b',
    SECRET '826187ffaee4742816f65ca4ebe149902db75ac52dbb81606bb34fe8bae4a57c',
    ENDPOINT 'ef8eef61229ee8854b4237f6949e50d8.r2.cloudflarestorage.com',
    URL_STYLE 'path'
);
""")

URLS = {
    'unified_market_dubai': 's3://truestates-re-analytics/dubai/data/insights_api/market_data.parquet',
    'unified_market_abudhabi': 's3://truestates-re-analytics/abudhabi/data/insights_api/market_data.parquet',
    'unified_rental_dubai': 'c:/Users/pooja/Transactions_api/rental_df.parquet'
}

router = APIRouter()

def get_base_table(table_name: str, emirate: str):
    if table_name == 'unified_market':
        if emirate and emirate.lower() == 'abu dhabi':
            return f"read_parquet('{URLS['unified_market_abudhabi']}')"
        elif emirate and emirate.lower() == 'dubai':
            return f"read_parquet('{URLS['unified_market_dubai']}')"
        else:
            return f"read_parquet(['{URLS['unified_market_dubai']}', '{URLS['unified_market_abudhabi']}'])"
    elif table_name == 'unified_rental':
        if emirate and emirate.lower() == 'abu dhabi':
            return "(SELECT * FROM (SELECT 1) WHERE 1=0)"
        else:
            return f"read_parquet('{URLS['unified_rental_dubai']}')"
    return ""

def get_filter_clause(is_rental: bool, emirate: str, lat: float, lon: float, area: str, start_date: str, end_date: str, room_type: str, property_type: str, reg_type: str = None, transaction_type: str = None, year: int = None):
    from market_router import coords_df
    where_clauses = []
    
    inferred_area = None
    if lat is not None and lon is not None and not coords_df.empty:
        temp_coords = coords_df.dropna(subset=['latitude', 'longitude']).copy()
        if not temp_coords.empty:
            lats = pd.to_numeric(temp_coords['latitude'], errors='coerce').values
            lons = pd.to_numeric(temp_coords['longitude'], errors='coerce').values
            dlat = np.radians(lats - lat)
            dlon = np.radians(lons - lon)
            a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat)) * np.cos(np.radians(lats)) * np.sin(dlon / 2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
            dists = 6371.0 * c
            min_idx = np.nanargmin(dists)
            min_dist = dists[min_idx]
            from config import DEFAULT_RADIUS_KM
            if min_dist <= DEFAULT_RADIUS_KM:
                nearest = temp_coords.iloc[min_idx]
                inferred_area = str(nearest['area_name']).lower()
                if not emirate:
                    emirate = nearest['emirate_source']
            else:
                return "1=0", emirate
                
    if area and not emirate and not coords_df.empty:
        matched = coords_df[coords_df['area_name'].astype(str).str.lower() == area.strip().lower()]
        if not matched.empty:
            emirate = matched.iloc[0]['emirate_source']

    area_col = 'area_name_en' if is_rental else 'area'
    if inferred_area:
        inferred_area_clean = inferred_area.replace("'", "''")
        where_clauses.append(f"lower({area_col}) = '{inferred_area_clean}'")
    elif area:
        area_clean = area.strip().lower().replace("'", "''")
        where_clauses.append(f"lower({area_col}) = '{area_clean}'")

    date_col = 'contract_start_date' if is_rental else 'date'
    date_expr = f"try_strptime({date_col}, '%d-%m-%Y')" if is_rental else f"try_strptime(cast({date_col} as varchar), '%Y-%m-%d %H:%M:%S')"
    
    if is_rental:
        where_clauses.append(f"{date_expr} <= current_date")
        
    if start_date:
        where_clauses.append(f"{date_expr} >= try_strptime('{start_date}', '%Y-%m-%d')")
    if end_date:
        where_clauses.append(f"{date_expr} <= try_strptime('{end_date}', '%Y-%m-%d')")

    if not start_date and not end_date and year:
        where_clauses.append(f"date_part('year', {date_expr}) = {year}")

    room_col = 'ejari_property_sub_type_en' if is_rental else 'room_type'
    if room_type:
        room_type_clean = room_type.strip().lower().replace("'", "''")
        where_clauses.append(f"lower({room_col}) = '{room_type_clean}'")
        
    prop_col = 'ejari_property_type_en' if is_rental else 'property_type'
    if property_type:
        property_type_clean = property_type.strip().lower().replace("'", "''")
        where_clauses.append(f"lower({prop_col}) = '{property_type_clean}'")

    if not is_rental:
        if reg_type:
            reg_type_clean = reg_type.strip().lower().replace("'", "''")
            where_clauses.append(f"lower(reg_type) = '{reg_type_clean}'")
        if transaction_type:
            transaction_type_clean = transaction_type.strip().lower().replace("'", "''")
            where_clauses.append(f"lower(transaction_type) = '{transaction_type_clean}'")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_sql, emirate

@router.get("/tiles")
def get_unified_tiles(
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    rw, r_emirate = get_filter_clause(True, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    
    s_table = get_base_table('unified_market', s_emirate)
    r_table = get_base_table('unified_rental', r_emirate)

    tiles = {"median_sale_price": 0.0, "total_sales_volume": 0, "total_sales_aed": 0.0, "median_rate_sqm": 0.0, "median_annual_rent": 0.0}
    
    try:
        s_res = con.execute(f"""
            WITH bounds AS (SELECT quantile_cont(sale_price, 0.02) as ql, quantile_cont(sale_price, 0.98) as qh FROM {s_table} WHERE {sw})
            SELECT median(sale_price), count(*), sum(sale_price), median(rate_sqm) 
            FROM {s_table}, bounds 
            WHERE {sw} AND sale_price >= ql AND sale_price <= qh
        """).fetchone()
        if s_res and s_res[1] > 0:
            tiles.update({"median_sale_price": s_res[0] or 0.0, "total_sales_volume": s_res[1] or 0, "total_sales_aed": s_res[2] or 0.0, "median_rate_sqm": s_res[3] or 0.0})
            
        r_res = con.execute(f"""
            WITH bounds AS (SELECT quantile_cont(annual_amount, 0.02) as ql, quantile_cont(annual_amount, 0.98) as qh FROM {r_table} WHERE {rw})
            SELECT median(annual_amount) FROM {r_table}, bounds WHERE {rw} AND annual_amount >= ql AND annual_amount <= qh
        """).fetchone()
        if r_res and r_res[0]:
            tiles.update({"median_annual_rent": r_res[0]})
    except Exception as e:
        print("Error in tiles:", e)

    return {"status": "success", "tiles": tiles}

@router.get("/growth_and_yield")
def get_unified_growth_and_yield(
    metric: str = Query("median_price"), comparison_type: str = Query("yoy"),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    rw, r_emirate = get_filter_clause(True, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    
    s_table = get_base_table('unified_market', s_emirate)
    r_table = get_base_table('unified_rental', r_emirate)
    
    trunc = 'year' if comparison_type == 'yoy' else ('quarter' if comparison_type == 'qoq' else 'month')
    
    s_agg = "median(sale_price)"
    if metric == "volume": s_agg = "count(*)"
    elif metric == "total_price": s_agg = "sum(sale_price)"
    elif metric == "median_rate": s_agg = "median(rate_sqm)"
    
    r_agg = "median(annual_amount)"
    if metric == "volume": r_agg = "count(*)"
    elif metric == "total_price": r_agg = "sum(annual_amount)"
    elif metric == "median_rate": r_agg = "0"
    
    try:
        s_query = f"""
            WITH bounds AS (SELECT quantile_cont(sale_price, 0.02) as ql, quantile_cont(sale_price, 0.98) as qh FROM {s_table} WHERE {sw})
            SELECT cast(date_trunc('{trunc}', try_strptime(cast(date as varchar), '%Y-%m-%d %H:%M:%S')) as varchar) as Period, {s_agg} as Sales_Value
            FROM {s_table}, bounds WHERE {sw} AND sale_price >= ql AND sale_price <= qh
            GROUP BY Period
        """
        s_df = con.execute(s_query).df()
        
        r_query = f"""
            WITH bounds AS (SELECT quantile_cont(annual_amount, 0.02) as ql, quantile_cont(annual_amount, 0.98) as qh FROM {r_table} WHERE {rw})
            SELECT cast(date_trunc('{trunc}', try_strptime(contract_start_date, '%d-%m-%Y')) as varchar) as Period, {r_agg} as Rental_Value
            FROM {r_table}, bounds WHERE {rw} AND annual_amount >= ql AND annual_amount <= qh
            GROUP BY Period
        """
        r_df = con.execute(r_query).df()
    except Exception as e:
        print("Error in growth:", e)
        s_df = pd.DataFrame(columns=['Period', 'Sales_Value'])
        r_df = pd.DataFrame(columns=['Period', 'Rental_Value'])

    s_df['Sales_Growth'] = s_df['Sales_Value'].pct_change() if not s_df.empty else None
    r_df['Rental_Growth'] = r_df['Rental_Value'].pct_change() if not r_df.empty else None
    
    if s_df.empty and r_df.empty:
        return {"status": "success", "data": []}
        
    combined = pd.merge(s_df, r_df, on='Period', how='outer').sort_values('Period')
    if metric == "median_price":
        combined['Gross_Rental_Yield'] = np.where(combined['Sales_Value'] > 0, (combined['Rental_Value'] / combined['Sales_Value']) * 100, np.nan)
        combined['Yield_Growth'] = combined['Gross_Rental_Yield'].pct_change()
        
    res_data = []
    for row in combined.to_dict(orient="records"):
        res_data.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    return {"status": "success", "data": res_data}

@router.get("/distributions/price_bins")
def get_price_bins(
    metric: str = Query("volume"), is_rental: bool = Query(False),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(is_rental, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    table = get_base_table('unified_rental' if is_rental else 'unified_market', s_emirate)
    val_col = 'annual_amount' if is_rental else 'sale_price'
    
    agg = f"median({val_col})" if metric == "median_price" else ("count(*)" if metric == "volume" else f"sum({val_col})")
    if metric == "median_rate" and not is_rental: agg = "median(rate_sqm)"
    
    try:
        query = f"""
            WITH bounds AS (SELECT quantile_cont({val_col}, 0.02) as ql, quantile_cont({val_col}, 0.98) as qh FROM {table} WHERE {sw})
            SELECT 
                CASE 
                    WHEN {val_col} < 500000 THEN 'Budget Friendly (< 500k)'
                    WHEN {val_col} < 1500000 THEN 'Mid-Market (500k-1.5M)'
                    WHEN {val_col} < 5000000 THEN 'Premium (1.5M-5M)'
                    ELSE 'Ultra Premium (5M+)'
                END as Price_Bin,
                {agg} as Value
            FROM {table}, bounds WHERE {sw} AND {val_col} >= ql AND {val_col} <= qh
            GROUP BY 1
        """
        df = con.execute(query).df()
    except Exception as e:
        print("Error in price_bins:", e)
        df = pd.DataFrame(columns=['Price_Bin', 'Value'])
        
    res_data = []
    for row in df.to_dict(orient="records"):
        res_data.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    return {"status": "success", "data": res_data}

@router.get("/distributions/grouped")
def get_grouped_distribution(
    metric: str = Query("volume"), group_by: str = Query("room_type"), is_rental: bool = Query(False),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(is_rental, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    table = get_base_table('unified_rental' if is_rental else 'unified_market', s_emirate)
    val_col = 'annual_amount' if is_rental else 'sale_price'
    
    agg = f"median({val_col})" if metric == "median_price" else ("count(*)" if metric == "volume" else f"sum({val_col})")
    if metric == "median_rate" and not is_rental: agg = "median(rate_sqm)"
    
    if is_rental and group_by == "room_type": group_by = "ejari_property_sub_type_en"
    if is_rental and group_by == "property_type": group_by = "ejari_property_type_en"
    
    try:
        query = f"""
            WITH bounds AS (SELECT quantile_cont({val_col}, 0.02) as ql, quantile_cont({val_col}, 0.98) as qh FROM {table} WHERE {sw})
            SELECT {group_by} as Group_Category, {agg} as Value
            FROM {table}, bounds WHERE {sw} AND {val_col} >= ql AND {val_col} <= qh AND {group_by} IS NOT NULL
            GROUP BY 1
        """
        df = con.execute(query).df()
    except Exception as e:
        print("Error in grouped:", e)
        df = pd.DataFrame(columns=['Group_Category', 'Value'])
        
    res_data = []
    for row in df.to_dict(orient="records"):
        res_data.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    return {"status": "success", "data": res_data}

@router.get("/area_vs_price")
def get_area_vs_price(
    metric: str = Query("median_rate"),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None),
    year: int = Query(2026), limit: int = Query(300)
):
    sw, s_emirate = get_filter_clause(False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type, year)
    s_table = get_base_table('unified_market', s_emirate)
    
    agg = "median(rate_sqm)" if metric == "median_rate" else ("count(*)" if metric == "volume" else ("sum(sale_price)" if metric == "total_price" else "median(sale_price)"))
    
    try:
        bin_query = f"""
            WITH bounds AS (SELECT quantile_cont(sale_price, 0.02) as ql, quantile_cont(sale_price, 0.98) as qh FROM {s_table} WHERE {sw})
            SELECT 
                CASE 
                    WHEN area_sqm < 50 THEN '0-50 sqm'
                    WHEN area_sqm < 100 THEN '50-100 sqm'
                    WHEN area_sqm < 150 THEN '100-150 sqm'
                    WHEN area_sqm < 200 THEN '150-200 sqm'
                    WHEN area_sqm < 500 THEN '200-500 sqm'
                    ELSE '500+ sqm'
                END as Area_SQM_Bin,
                {agg} as Value
            FROM {s_table}, bounds 
            WHERE {sw} AND sale_price >= ql AND sale_price <= qh AND area_sqm IS NOT NULL
            GROUP BY 1
        """
        binned = con.execute(bin_query).df()
        
        scatter_query = f"""
            WITH bounds AS (SELECT quantile_cont(sale_price, 0.02) as ql, quantile_cont(sale_price, 0.98) as qh FROM {s_table} WHERE {sw})
            SELECT round(area_sqm, 0) as area_sqm, room_type, {agg} as Value
            FROM {s_table}, bounds 
            WHERE {sw} AND sale_price >= ql AND sale_price <= qh AND area_sqm IS NOT NULL
            GROUP BY 1, 2
            LIMIT {limit}
        """
        scatter = con.execute(scatter_query).df()
    except Exception as e:
        print("Error in area_vs_price:", e)
        binned = pd.DataFrame(columns=['Area_SQM_Bin', 'Value'])
        scatter = pd.DataFrame(columns=['area_sqm', 'room_type', 'Value'])
        
    binned_res = []
    for row in binned.to_dict(orient="records"):
        binned_res.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    
    scatter_res = []
    for row in scatter.to_dict(orient="records"):
        scatter_res.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
        
    return {
        "binned_data": binned_res,
        "scatter_data": scatter_res
    }

@router.get("/transactions")
def get_transactions(
    page: int = Query(1, ge=1), rows_per_page: int = Query(50, ge=1, le=100),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    s_table = get_base_table('unified_market', s_emirate)
    offset = (page - 1) * rows_per_page
    
    try:
        q = f"SELECT * FROM {s_table} WHERE {sw} ORDER BY date DESC LIMIT {rows_per_page} OFFSET {offset}"
        df = con.execute(q).df()
        cnt_q = f"SELECT count(*) FROM {s_table} WHERE {sw}"
        cnt = con.execute(cnt_q).fetchone()[0]
    except Exception as e:
        print("Error in transactions:", e)
        df = pd.DataFrame()
        cnt = 0
        
    return {
        "status": "success",
        "pagination": {"page": page, "rows_per_page": rows_per_page, "total_records": cnt},
        "data": df.replace({np.nan: None}).to_dict(orient="records")
    }

@router.get("/feature_prices")
def get_feature_prices(
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    try:
        table = "read_parquet('s3://truestates-re-analytics/dubai/data/processed/latest_combined_data.parquet')"
        
        # Build where clause manually for raw data since names differ slightly
        where_clauses = ["actual_worth > 0"]
        if area: where_clauses.append(f"lower(area_name_en) = '{area.lower().replace(chr(39), chr(39)+chr(39))}'")
        if start_date: where_clauses.append(f"try_strptime(instance_date, '%d-%m-%Y %H:%M:%S') >= try_strptime('{start_date}', '%Y-%m-%d')")
        if end_date: where_clauses.append(f"try_strptime(instance_date, '%d-%m-%Y %H:%M:%S') <= try_strptime('{end_date}', '%Y-%m-%d')")
        if property_type: where_clauses.append(f"lower(property_type_en) = '{property_type.lower()}'")
        if room_type: where_clauses.append(f"lower(rooms_en) = '{room_type.lower()}'")
        if reg_type: where_clauses.append(f"lower(reg_type_en) = '{reg_type.lower()}'")
        
        sw = " AND ".join(where_clauses)
        
        features = {
            "Metro": "metro",
            "Balcony": "balcony",
            "Elevator": "elevator",
            "Swimming Pool": "swimming_pool"
        }
        
        data = {}
        for label, col in features.items():
            query_with = f"SELECT median(actual_worth) FROM {table} WHERE {sw} AND {col} = 1"
            query_without = f"SELECT median(actual_worth) FROM {table} WHERE {sw} AND ({col} IS NULL OR {col} = 0)"
            
            p_with = con.execute(query_with).fetchone()[0] or 0
            p_without = con.execute(query_without).fetchone()[0] or 0
            
            data[label] = {
                "With": round(p_with, 2),
                "Without": round(p_without, 2),
                "premium_pct": round(((p_with - p_without) / p_without * 100), 1) if p_without > 0 else 0
            }
            
        # Floor Bin Distribution
        query_floor = f"""
            SELECT 
                CASE 
                    WHEN try_cast(floors as int) IS NULL THEN 'Unknown/Below 1st Floor'
                    WHEN floors < 1 THEN 'Unknown/Below 1st Floor'
                    WHEN floors >= 1 AND floors <= 10 THEN '1 to 10'
                    WHEN floors > 10 AND floors <= 20 THEN '11 to 20'
                    WHEN floors > 20 AND floors <= 30 THEN '21 to 30'
                    WHEN floors > 30 AND floors <= 40 THEN '31 to 40'
                    WHEN floors > 40 AND floors <= 50 THEN '41 to 50'
                    WHEN floors > 50 AND floors <= 60 THEN '51 to 60'
                    WHEN floors > 60 AND floors <= 70 THEN '61 to 70'
                    WHEN floors > 70 AND floors <= 80 THEN '71 to 80'
                    WHEN floors > 80 THEN '81+'
                    ELSE 'Unknown/Below 1st Floor'
                END as Name, 
                median(actual_worth) as Median_Price 
            FROM {table} 
            WHERE {sw}
            GROUP BY 1
        """
        floor_df = con.execute(query_floor).df()
        data["Floor_Distribution"] = floor_df.to_dict(orient="records")
        
        return {"status": "success", "data": data}
    except Exception as e:
        print("Error in feature_prices:", e)
        return {"status": "error", "message": str(e)}

@router.get("/top_bottom_performers")
def get_top_bottom(
    metric: str = Query("volume"), group_by: str = Query("area"),
    emirate: Optional[str] = Query(None), start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None), lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None), area: Optional[str] = Query(None),
    room_type: Optional[str] = Query(None), property_type: Optional[str] = Query(None),
    reg_type: Optional[str] = Query(None), transaction_type: Optional[str] = Query(None)
):
    sw, s_emirate = get_filter_clause(False, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type)
    table = get_base_table('unified_market', s_emirate)
    
    if metric == "volume": agg = "count(*)"
    elif metric == "total_sales": agg = "sum(sale_price)"
    elif metric == "median_sale_price": agg = "median(sale_price)"
    elif metric == "median_meter_sale_price": agg = "median(rate_sqm)"
    else: agg = "median(sale_price)"
    
    gb = "project_name" if group_by == "project_name" else "area"
    
    try:
        query = f"""
            SELECT {gb} as name, {agg} as val
            FROM {table}
            WHERE {sw} AND {gb} IS NOT NULL AND {gb} != ''
            GROUP BY 1
        """
        df = con.execute(query).df()
        
        if df.empty:
            return {"status": "success", "data": {"top": [], "bottom": []}}
            
        df = df.dropna()
        df = df.sort_values('val', ascending=False)
        
        top = df.head(10)
        bot = df.tail(10)
        
        return {
            "status": "success",
            "data": {
                "top": [{"name": r['name'], "value": r['val']} for _, r in top.iterrows()],
                "bottom": [{"name": r['name'], "value": r['val']} for _, r in bot.iterrows()]
            }
        }
    except Exception as e:
        print("Error in top_bottom:", e)
        return {"status": "error", "message": str(e)}

def filter_data(table_name, is_rental, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type, year):
    sw, s_emirate = get_filter_clause(is_rental, emirate, lat, lon, area, start_date, end_date, room_type, property_type, reg_type, transaction_type, year)
    s_table = get_base_table(table_name, s_emirate)
    if s_table == "(SELECT * FROM (SELECT 1) WHERE 1=0)" or not s_table:
        return pd.DataFrame()
    try:
        q = f"SELECT * FROM {s_table} WHERE {sw}"
        df = con.execute(q).df()
        if not df.empty:
            date_col = 'contract_start_date' if is_rental else 'date'
            if is_rental:
                df['date_parsed'] = pd.to_datetime(df[date_col], format='%d-%m-%Y', errors='coerce')
            else:
                df['date_parsed'] = pd.to_datetime(df[date_col], errors='coerce')
            df['Month_Year'] = df['date_parsed'].dt.to_period('M')
        return df
    except Exception as e:
        print("Error in filter_data:", e)
        return pd.DataFrame()

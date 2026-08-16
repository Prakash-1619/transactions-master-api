# dubai_router.py
# Same logic as the original api.py — only change is FastAPI -> APIRouter
# so this can be mounted under /api/v1/dubai in the master app.

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import numpy as np
import pandas as pd
import math
import json
from config import (
    TRANSACTIONS_FILE, PROJECTS_FILE, DEVELOPERS_FILE, AREA_COORDS_FILE,
    DEFAULT_PAGE_SIZE,
)
from filtering_df import get_processed_df, apply_filters, reprocess_and_save
from schemas import ComparisonType, GrowthMetric
#from filtering_df import apply_filters_duckdb as apply_filters
router = APIRouter()

# Initialize global dataframe on import (same behavior as original api.py)
raw_df = get_processed_df(TRANSACTIONS_FILE, AREA_COORDS_FILE)

def get_group_stats(df, col):
    if col not in df.columns or df.empty: return []
    stats = df.groupby(col).agg(
        count=(col, 'count'), 
        median_worth=('actual_worth', 'median'), 
        median_price=('meter_sale_price', 'median')
    ).reset_index()
    return stats.replace([np.inf, -np.inf, np.nan], None).to_dict(orient="records")

@router.post("/refresh-data")
def refresh_data():
    """Manually trigger the data cleaning pipeline and update the cache."""
    global raw_df 
    try:
        new_df = reprocess_and_save(TRANSACTIONS_FILE, AREA_COORDS_FILE)
        raw_df = new_df
        return {"status": "success", "message": "Data reprocessed and cache updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh data: {str(e)}")

@router.get("/filter-data")
def get_filtered_data(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    time_preset: Optional[str] = Query(None),
    trans_group_en: Optional[str] = Query(None),
    property_type_en: Optional[str] = Query(None),
    property_sub_type_en: Optional[str] = Query(None),
    property_usage_en: Optional[str] = Query(None),
    reg_type_en: Optional[str] = Query(None),
    area_name_en: Optional[str] = Query(None),
    rooms_en: Optional[str] = Query(None),
    has_parking: Optional[str] = Query(None),
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    emirate: Optional[str] = Query(None),         # <-- NEW: Emirate filter
    radius: Optional[float] = Query(None),        # <-- NEW: Radius filter (in km)
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=50)
):
    if raw_df.empty: 
        raise HTTPException(status_code=500, detail="Data load error")

    filter_dict = {
        k: v for k, v in {
            "start_date": start_date, "end_date": end_date, "time_preset": time_preset,
            "trans_group_en": trans_group_en, "property_type_en": property_type_en,
            "property_sub_type_en": property_sub_type_en, "property_usage_en": property_usage_en,
            "reg_type_en": reg_type_en, "area_name_en": area_name_en, "rooms_en": rooms_en,
            "has_parking": has_parking, "latitude": latitude, "longitude": longitude,
            "emirate": emirate, "radius": radius
        }.items() if v is not None
    }

    final_df = apply_filters(raw_df, filter_dict)
    
    summary = {
        "total_transactions": len(final_df),
        "median_actual_worth": final_df['actual_worth'].median() if not final_df.empty else None,
        "median_meter_sale_price": final_df['meter_sale_price'].median() if not final_df.empty else None,
        "stats_by_property_type": get_group_stats(final_df, 'property_type_en'),
        "stats_by_rooms": get_group_stats(final_df, 'rooms_en'),
        "stats_by_reg_type": get_group_stats(final_df, 'reg_type_en')
    }
    
    total_pages = math.ceil(len(final_df) / page_size)
    paginated_df = final_df.iloc[(page-1)*page_size : page*page_size]
        
    safe_records = json.loads(paginated_df.replace([np.inf, -np.inf], np.nan).to_json(orient="records", date_format="iso", default_handler=str))
    
    return {
        "metadata": {
            "total_records": len(final_df), 
            "current_page": page, 
            "total_pages": total_pages, 
            "page_size": page_size
        }, 
        "summary": summary, 
        "data": safe_records
    }

@router.get("/insights/growth")
def get_dubai_growth_insights(
    # --- Same filter inputs as /filter-data, unchanged filtering logic ---
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    time_preset: Optional[str] = Query(None),
    trans_group_en: Optional[str] = Query(None),
    property_type_en: Optional[str] = Query(None),
    property_sub_type_en: Optional[str] = Query(None),
    property_usage_en: Optional[str] = Query(None),
    reg_type_en: Optional[str] = Query(None),
    area_name_en: Optional[str] = Query(None),
    rooms_en: Optional[str] = Query(None),
    has_parking: Optional[str] = Query(None),
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    emirate: Optional[str] = Query(None),
    radius: Optional[float] = Query(None),
    # --- Growth-specific params (same enums/shift logic as Abu Dhabi) ---
    comparison_type: ComparisonType = Query(ComparisonType.yoy, description="yoy, qoq, or mom. Defaults to yoy."),
    growth_metric: GrowthMetric = Query(GrowthMetric.median_rate, description="Metric to calculate growth on"),
    group_by: Optional[str] = Query(None, description="Column name to break down market trends (e.g., area_name_en)")
):
    if raw_df.empty:
        raise HTTPException(status_code=500, detail="Data load error")

    # 1) Reuse the exact same filter_dict + apply_filters used by /filter-data
    filter_dict = {
        k: v for k, v in {
            "start_date": start_date, "end_date": end_date, "time_preset": time_preset,
            "trans_group_en": trans_group_en, "property_type_en": property_type_en,
            "property_sub_type_en": property_sub_type_en, "property_usage_en": property_usage_en,
            "reg_type_en": reg_type_en, "area_name_en": area_name_en, "rooms_en": rooms_en,
            "has_parking": has_parking, "latitude": latitude, "longitude": longitude,
            "emirate": emirate, "radius": radius
        }.items() if v is not None
    }

    df_filtered = apply_filters(raw_df, filter_dict)

    if df_filtered.empty:
        return {"message": "Empty data context frame matches returned across criteria filters."}

    # apply_filters() returns instance_date as a string (astype(str)) —
    # convert back to datetime here for monthly period grouping.
    df_filtered = df_filtered.copy()
    df_filtered['instance_date'] = pd.to_datetime(df_filtered['instance_date'], errors='coerce')

    # 2) Same growth-calculation logic as Abu Dhabi's insights/growth,
    #    mapped onto Dubai's own price/rate columns:
    #      Rate (AED per SQM)        -> meter_sale_price
    #      Property Sale Price (AED) -> actual_worth
    periods_map = {ComparisonType.mom: 1, ComparisonType.qoq: 3, ComparisonType.yoy: 12}
    shift_period = periods_map[comparison_type]

    metric_col_map = {
        GrowthMetric.volume: 'Volume',
        GrowthMetric.total_sales: 'Total_Sales_AED',
        GrowthMetric.median_rate: 'Median_Rate'
    }
    target_metric_col = metric_col_map[growth_metric]

    df_filtered['Month_Year'] = df_filtered['instance_date'].dt.to_period('M')
    market_trend = df_filtered.groupby('Month_Year').agg(
        Median_Rate=('meter_sale_price', 'median'),
        Total_Sales_AED=('actual_worth', 'sum'),
        Volume=('actual_worth', 'count')
    ).reset_index()

    growth_col_name = f"{comparison_type.value.upper()}_{growth_metric.value.upper()}_GROWTH"
    market_trend[growth_col_name] = market_trend[target_metric_col].pct_change(periods=shift_period)

    market_trend['Month_Year'] = market_trend['Month_Year'].astype(str)
    market_trend.replace([np.inf, -np.inf], 0, inplace=True)

    group_insights = {}
    if group_by and group_by in df_filtered.columns:
        group_data = df_filtered.groupby([group_by, 'Month_Year']).agg(
            Median_Rate=('meter_sale_price', 'median'),
            Total_Sales_AED=('actual_worth', 'sum'),
            Volume=('actual_worth', 'count')
        ).reset_index()

        group_data = group_data.sort_values([group_by, 'Month_Year'])
        group_data[growth_col_name] = group_data.groupby(group_by)[target_metric_col].pct_change(periods=shift_period)

        group_data['Month_Year'] = group_data['Month_Year'].astype(str)
        group_data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)

        for group_name, df_group in group_data.groupby(group_by):
            group_insights[group_name] = df_group.tail(1).to_dict(orient="records")[0]

    actual_start = df_filtered['instance_date'].min().strftime('%Y-%m-%d')
    actual_end = df_filtered['instance_date'].max().strftime('%Y-%m-%d')

    return {
        "analysis_params": {
            "comparison_type": comparison_type.value.upper(),
            "growth_metric_tracked": growth_metric.value.upper(),
            "timeframe_analyzed": {
                "start": actual_start,
                "end": actual_end
            }
        },
        "overall_market_latest": market_trend.iloc[-1].fillna(0).to_dict() if not market_trend.empty else {},
        "overall_market_history": market_trend.fillna(0).to_dict(orient="records"),
        "grouped_breakdown": group_insights if group_insights else "No group_by column specified."
    }

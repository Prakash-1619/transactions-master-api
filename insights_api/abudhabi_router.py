# abudhabi_router.py
# Same logic as the original main.py — only change is FastAPI -> APIRouter
# so this can be mounted under /api/v1/abudhabi in the master app.
# load_data() is unchanged; it's now called from the master app's startup
# event (see master_api.py) instead of its own local @app.on_event.

from fastapi import APIRouter, Depends
import pandas as pd
import numpy as np
from latest_rental_data.s3_manager import get_storage_options
from schemas import (
    DataFilter,
    GrowthRequest,
    DistributionRequest,
    TransactionsRequest,
    ComparisonType,
    RankType,
    RankMetric,
    GrowthMetric
)
from services import clean_outliers, apply_filters

import config 

router = APIRouter()
df_main = pd.DataFrame()

def load_data():
    """Loads Abu Dhabi data using the central config file path."""
    global df_main
    try:
        # 2. Reference the path variable from config.py
        file_path = config.abudhabi_transactions
        
        print(f"Loading Abu Dhabi data from: {file_path}")
        df_main = pd.read_parquet(file_path, storage_options=get_storage_options())
        
        if 'Sale Application Date' in df_main.columns:
            df_main['Sale Application Date'] = pd.to_datetime(df_main['Sale Application Date'])
            
        df_main = clean_outliers(df_main)
        print("Data loaded, cleaned, and initialized successfully.")
    except Exception as e:
        print(f"Startup data loading failure: {e}")

@router.get("/transactions")
def get_transactions(req: TransactionsRequest = Depends()):
    df_filtered = apply_filters(df_main, req)

    if df_filtered.empty:
        return {
            "message": "No records matched the specified filters.",
            "pagination": {
                "page": req.page,
                "rows_per_page": req.rows_per_page,
                "total_records": 0,
                "total_pages": 0
            },
            "transactions": []
        }

    df_filtered = df_filtered.sort_values(
        by="Sale Application Date",
        ascending=False
    ).copy()

    total_records = len(df_filtered)
    total_pages = (total_records + req.rows_per_page - 1) // req.rows_per_page

    start_idx = (req.page - 1) * req.rows_per_page
    end_idx = start_idx + req.rows_per_page

    page_df = df_filtered.iloc[start_idx:end_idx].copy()

    if "Sale Application Date" in page_df.columns:
        page_df["Sale Application Date"] = page_df["Sale Application Date"].dt.strftime("%Y-%m-%d")

    actual_start = df_filtered["Sale Application Date"].min().strftime("%Y-%m-%d")
    actual_end = df_filtered["Sale Application Date"].max().strftime("%Y-%m-%d")

    return {
        "timeframe_analyzed": {
            "start": actual_start,
            "end": actual_end
        },
        "pagination": {
            "page": req.page,
            "rows_per_page": req.rows_per_page,
            "total_records": total_records,
            "total_pages": total_pages
        },
        "transactions": page_df.replace({np.nan: None}).to_dict(orient="records")
    }

@router.get("/insights/growth")
def get_growth_insights(req: GrowthRequest = Depends()):
    df_filtered = apply_filters(df_main, req)
    if df_filtered.empty:
        return {"message": "Empty data context frame matches returned across criteria filters."}

    periods_map = {ComparisonType.mom: 1, ComparisonType.qoq: 3, ComparisonType.yoy: 12}
    shift_period = periods_map[req.comparison_type]

    metric_col_map = {
        GrowthMetric.volume: 'Volume',
        GrowthMetric.total_sales: 'Total_Sales_AED',
        GrowthMetric.median_rate: 'Median_Rate'
    }
    target_metric_col = metric_col_map[req.growth_metric]

    df_filtered['Month_Year'] = df_filtered['Sale Application Date'].dt.to_period('M')
    market_trend = df_filtered.groupby('Month_Year').agg(
        Median_Rate=('Rate (AED per SQM)', 'median'),
        Total_Sales_AED=('Property Sale Price (AED)', 'sum'),
        Volume=('Property Sale Price (AED)', 'count')
    ).reset_index()

    growth_col_name = f"{req.comparison_type.value.upper()}_{req.growth_metric.value.upper()}_GROWTH"
    market_trend[growth_col_name] = market_trend[target_metric_col].pct_change(periods=shift_period)

    market_trend['Month_Year'] = market_trend['Month_Year'].astype(str)
    market_trend.replace([np.inf, -np.inf], 0, inplace=True)

    group_insights = {}
    if req.group_by and req.group_by in df_filtered.columns:
        group_data = df_filtered.groupby([req.group_by, 'Month_Year']).agg(
            Median_Rate=('Rate (AED per SQM)', 'median'),
            Total_Sales_AED=('Property Sale Price (AED)', 'sum'),
            Volume=('Property Sale Price (AED)', 'count')
        ).reset_index()

        group_data = group_data.sort_values([req.group_by, 'Month_Year'])
        group_data[growth_col_name] = group_data.groupby(req.group_by)[target_metric_col].pct_change(periods=shift_period)

        group_data['Month_Year'] = group_data['Month_Year'].astype(str)
        group_data.replace([np.inf, -np.inf, np.nan], 0, inplace=True)

        for group_name, df_group in group_data.groupby(req.group_by):
            group_insights[group_name] = df_group.tail(1).to_dict(orient="records")[0]

    actual_start = df_filtered['Sale Application Date'].min().strftime('%Y-%m-%d')
    actual_end = df_filtered['Sale Application Date'].max().strftime('%Y-%m-%d')

    return {
        "analysis_params": {
            "comparison_type": req.comparison_type.value.upper(),
            "growth_metric_tracked": req.growth_metric.value.upper(),
            "timeframe_analyzed": {
                "start": actual_start,
                "end": actual_end
            }
        },
        "overall_market_latest": market_trend.iloc[-1].fillna(0).to_dict() if not market_trend.empty else {},
        "overall_market_history": market_trend.fillna(0).to_dict(orient="records"),
        "grouped_breakdown": group_insights if group_insights else "No group_by column specified."
    }

@router.get("/insights/distribution")
def get_comprehensive_distribution(req: DistributionRequest = Depends()):
    df_filtered = apply_filters(df_main, req)
    if df_filtered.empty:
        return {"message": "No records matched the specified filters."}

    metric_map = {
        RankMetric.volume: 'Volume',
        RankMetric.total_sales: 'Total_Sales_AED',
        RankMetric.median_rate: 'Median_Rate_SQM'
    }
    sort_column = metric_map[req.rank_metric]
    is_ascending = True if req.rank_type == RankType.bottom else False

    performers_summary = {}
    cat_columns = [
        'Asset Class', 'Property Type', 'Property Layout',
        'District', 'Community', 'Project Name', 'Sale Sequence'
    ]

    for col in cat_columns:
        if col in df_filtered.columns and df_filtered[col].nunique() > 0:
            dist = df_filtered.groupby(col).agg(
                Volume=('Property Sale Price (AED)', 'count'),
                Total_Sales_AED=('Property Sale Price (AED)', 'sum'),
                Median_Rate_SQM=('Rate (AED per SQM)', 'median')
            )

            dist = dist.sort_values(by=sort_column, ascending=is_ascending).head(req.rank_limit)
            performers_summary[col] = dist.fillna(0).to_dict('index')

    timelines = {}
    for time_col in ['Project Name', 'Community']:
        if time_col in df_filtered.columns:
            timeline_df = df_filtered.groupby(time_col).agg(
                First_Transaction_Date=('Sale Application Date', 'min'),
                Total_Volume=('Property Sale Price (AED)', 'count')
            ).reset_index()

            timeline_df = timeline_df.sort_values(by='First_Transaction_Date', ascending=False)
            timeline_df['First_Transaction_Date'] = timeline_df['First_Transaction_Date'].astype(str)
            timelines[time_col] = timeline_df.head(20).to_dict('records')

    actual_start = df_filtered['Sale Application Date'].min().strftime('%Y-%m-%d')
    actual_end = df_filtered['Sale Application Date'].max().strftime('%Y-%m-%d')

    return {
        "ranking_applied": f"{req.rank_type.value.upper()} {req.rank_limit} by {req.rank_metric.value.upper()}",
        "timeframe_analyzed": {
            "start": actual_start,
            "end": actual_end
        },
        "performers_summary": performers_summary,
        "chronological_timelines_newest_first": timelines
    }

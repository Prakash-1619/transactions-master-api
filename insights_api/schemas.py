from typing import Optional
from fastapi import Query
from enum import Enum
from dataclasses import dataclass

class ComparisonType(str, Enum):
    yoy = "yoy"
    qoq = "qoq"
    mom = "mom"

class RankType(str, Enum):
    top = "top"
    bottom = "bottom"

class RankMetric(str, Enum):
    volume = "volume"
    total_sales = "total_sales"
    median_rate = "median_rate"

class GrowthMetric(str, Enum):
    volume = "volume"
    total_sales = "total_sales"
    median_rate = "median_rate"
    median_sale_price = "median_sale_price"
    median_annual_rent = "median_annual_rent"

@dataclass
class DataFilter:
    start_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD")
    end_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD")
    asset_class: Optional[str] = Query(None, description="Comma-separated values")
    property_type: Optional[str] = Query(None, description="Comma-separated values")
    property_layout: Optional[str] = Query(None, description="Comma-separated values")
    district: Optional[str] = Query(None, description="Comma-separated values")
    community: Optional[str] = Query(None, description="Comma-separated values")
    project_name: Optional[str] = Query(None, description="Comma-separated values")
    sale_sequence: Optional[str] = Query(None, description="Comma-separated values")
    latitude: Optional[float] = Query(None, description="Latitude for nearest area filtering")
    longitude: Optional[float] = Query(None, description="Longitude for nearest area filtering")
    radius: Optional[float] = Query(None, description="Radius in km for nearest area filtering")

@dataclass
class TransactionsRequest(DataFilter):
    page: int = Query(1, ge=1, description="Page number, starting from 1")
    rows_per_page: int = Query(25, ge=1, le=50, description="Rows per page, allowed range: 1 to 50")

@dataclass
class GrowthRequest(DataFilter):
    comparison_type: ComparisonType = Query(ComparisonType.yoy, description="yoy, qoq, or mom. Defaults to yoy.")
    growth_metric: GrowthMetric = Query(GrowthMetric.median_rate, description="Metric to calculate growth on")
    group_by: Optional[str] = Query(None, description="Column name to break down market trends (e.g., District)")

@dataclass
class DistributionRequest(DataFilter):
    rank_type: RankType = Query(RankType.top, description="Sort by top or bottom performers")
    rank_metric: RankMetric = Query(RankMetric.volume, description="Metric to rank by: volume, total_sales, median_rate")
    rank_limit: int = Query(5, description="Number of performers to return (e.g., 5, 10)")
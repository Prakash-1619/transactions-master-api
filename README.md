# Real Estate Insights API Documentation

This document provides a comprehensive guide on the architecture, data processing, algorithms, and detailed specifications for all endpoints within the Real Estate Master API.

## 1. Architecture & Processing Logic

### Design & Processing Pipeline
1. **Data Source (S3/R2)**: All market transactions (Sales and Rentals) are aggregated, cleaned, and exported as Parquet files into a Cloudflare R2 bucket (`s3://truestates-re-analytics/`).
2. **Execution Engine (DuckDB)**: The API utilizes DuckDB as an in-process OLAP execution engine. Instead of downloading heavy gigabytes of data into RAM, DuckDB uses the `httpfs` extension to stream only the required columnar data directly from S3/R2.
3. **Unified Router Pattern**: 
   - Historically, Dubai and Abu Dhabi were maintained as separate APIs. 
   - The `/market/insights/unified` endpoints merge the logic. Both emirates exist in the same Parquet format. DuckDB executes a `UNION` or dynamically loads the correct Parquet file depending on the `emirate` filter passed in the API. 
4. **Serialization Safety**: 
   - Data scientists often face 500 Server Errors in APIs due to Pandas returning `NaN` or `Infinity`, which are invalid JSON. The API incorporates a custom iterative serialization algorithm to strip out `NaN` values and safely map them to JSON `null` before issuing the API response.

### Location / GPS Matching (Haversine Formula)
Endpoints like `/calculate_roi` and unified endpoints natively support `lat` and `lon` parameters instead of requiring users to spell area names exactly right. 
- **Algorithm**: The API pulls an internal dataset (`Area_co_ordinates_rental_areas.csv`). It maps the user's `(lat, lon)` using the spherical **Haversine Formula** to find the geographic distance between two points on the Earth. 
- **Threshold**: It finds the nearest coordinate match and infers the area string (e.g. "Al Barsha First"). If the closest point is > 5km away, it throws a `404 Not Found` error to prevent returning irrelevant data for rural GPS coordinates.

---

## 2. API Endpoints Reference

### 1. Unified KPI Tiles
Provides top-level aggregate numbers for a filtered subset of data.

* **Endpoint**: `GET /market/insights/unified/tiles`
* **Inputs/Values**:
  - `emirate` (str): e.g., "Dubai", "Abu Dhabi". If omitted, searches both.
  - `lat`, `lon` (float): Geographic coordinates to auto-detect area.
  - `area` (str): Exact area name (e.g., "Marina").
  - `start_date`, `end_date` (YYYY-MM-DD): Time range.
  - `room_type` (str): e.g., "1 B/R", "Studio".
  - `property_type` (str): e.g., "Apartment", "Villa".
  - `reg_type`, `transaction_type` (str): Transaction qualifiers (e.g. Off-plan vs Secondary).
* **Output**:
  ```json
  {
    "status": "success",
    "tiles": {
      "median_sale_price": 1200000.0,
      "total_sales_volume": 450,
      "total_sales_aed": 540000000.0,
      "median_rate_sqm": 12500.5,
      "median_annual_rent": 85000.0
    }
  }
  ```
* **Frontend Plot / Visualization**: **KPI Cards (Stat Tiles)**. 
  - *How to use*: Render these numbers in large font sizes at the top of a dashboard. No charts needed. Use up/down arrows if comparing against past periods.

---

### 2. Market Growth & Yield (Time Series)
Analyzes metric performance across specific time boundaries (Month, Quarter, Year).

* **Endpoint**: `GET /market/insights/unified/growth_and_yield`
* **Inputs/Values**:
  - `metric` (str): One of `volume`, `median_price`, `total_price`, `median_rate`. Default: `median_price`.
  - `comparison_type` (str): One of `yoy` (Year-over-Year), `qoq` (Quarter-over-Quarter), `mom` (Month-over-Month).
  - *...and all standard geographic/property filters from above.*
* **Output**:
  ```json
  {
    "status": "success",
    "data": [
      {
        "Period": "2023-01-01",
        "Sales_Value": 1200000.0,
        "Rental_Value": 85000.0,
        "Sales_Growth": 0.05,
        "Rental_Growth": 0.02,
        "Gross_Rental_Yield": 7.08,
        "Yield_Growth": 0.01
      }
    ]
  }
  ```
* **Frontend Plot / Visualization**: **Multi-axis Line & Bar Chart**. 
  - *How to use*: X-axis is `Period`. Primary Y-axis uses a Bar Chart to represent `Sales_Value`. Secondary Y-axis uses a Line Chart overlay to represent `Gross_Rental_Yield` percentages tracking over time. 

---

### 3. Price Distributions (Binned)
Groups overall market segments into standard qualitative brackets to analyze market weight (e.g. Budget vs Luxury).

* **Endpoint**: `GET /market/insights/unified/distributions/price_bins`
* **Inputs/Values**:
  - `metric` (str): Metric to aggregate (`volume`, `median_price`, `total_price`).
  - `is_rental` (bool): Defaults to `false`. Set to `true` to use rental bands instead of sales bands.
  - *...and all standard geographic/property filters from above.*
* **Output**:
  ```json
  {
    "status": "success",
    "data": [
      {"Price_Bin": "Budget Friendly (< 500k)", "Value": 120},
      {"Price_Bin": "Premium (1.5M-5M)", "Value": 350}
    ]
  }
  ```
* **Frontend Plot / Visualization**: **Vertical Bar Chart / Histogram**. 
  - *How to use*: X-axis is `Price_Bin`. Y-axis is `Value`. Useful for displaying market saturation and determining where the highest volume of liquidity sits.

---

### 4. Grouped Distributions
Shows market share divided by discrete categories like Room Type or Property Type.

* **Endpoint**: `GET /market/insights/unified/distributions/grouped`
* **Inputs/Values**:
  - `group_by` (str): Target classification column. Allowed: `room_type`, `property_type`.
  - `metric` (str): Aggregation target (`volume`, `median_price`, `total_price`).
  - `is_rental` (bool): `false` for Sales, `true` for Rental categories.
  - *...and all standard geographic/property filters from above.*
* **Output**:
  ```json
  {
    "status": "success",
    "data": [
      {"Group_Category": "1 B/R", "Value": 250},
      {"Group_Category": "Studio", "Value": 180}
    ]
  }
  ```
* **Frontend Plot / Visualization**: **Donut Chart or Pie Chart**. 
  - *How to use*: Represents the slice of the market pie that each property or room type controls based on volume or valuation.

---

### 5. Area vs Price (Scatter Analysis)
Correlates property square footage to valuation, highlighting anomalies or exact pricing clustering.

* **Endpoint**: `GET /market/insights/unified/area_vs_price`
* **Inputs/Values**:
  - `metric` (str): Defaults to `median_rate` per SQM.
  - `year` (int): Year filter. Defaults to `2026`.
  - `limit` (int): Limits the number of scatter points returned to prevent browser DOM lag. Defaults to `300`.
  - *...and all standard geographic/property filters from above.*
* **Output**: Returns two datasets concurrently: Binned aggregate summary and raw scatter plots.
  ```json
  {
    "binned_data": [
      {"Area_SQM_Bin": "50-100 sqm", "Value": 12500}
    ],
    "scatter_data": [
      {"area_sqm": 85, "room_type": "1 B/R", "Value": 1200000.0}
    ]
  }
  ```
* **Frontend Plot / Visualization**: **Scatter Plot**. 
  - *How to use*: X-axis is `area_sqm`. Y-axis is `Value`. The points should be colored dynamically based on the `room_type`. Hover tooltips should show the exact price and size.

---

### 6. ROI & Rental Yield Calculator
Provides exact expected yield for an investor targeting a specific sub-community and property type.

* **Endpoint**: `GET /api/v1/roi/calculate_roi`
* **Inputs/Values**:
  - `area_name` (str): Optional if lat/lon provided.
  - `lat`, `lon` (float): Optional if area_name provided. GPS fallback.
  - `room_id` (int): Required. Property sub-type mapping (0: Studio, 1: 1BHK, 2: 2BHK, etc.).
  - `year` (int): The transaction baseline year (default 2026).
  - `custom_annual_rent` (float): Optional. Overrides median rent for calculating specific yields.
  - `custom_transaction_amount` (float): Optional. Overrides median sale price.
* **Logic Output**: Yield is calculated algorithmically via: `(Median Annual Rent / Median Sale Price) * 100`.
* **Output**:
  ```json
  {
    "status": "Success",
    "search_method": "Nearest Area Found via GPS: Jumeirah Village Circle",
    "area": "Jumeirah Village Circle",
    "rooms": "1 B/R",
    "year": 2026,
    "roi_yield_percentage": 7.45,
    "market_reference": {
      "median_rent": 75000.0,
      "median_price": 1006711.40,
      "rent_range": {"min": 50000.0, "max": 120000.0}
    }
  }
  ```
* **Frontend Plot / Visualization**: **Gauge Chart (Speedometer) or Bullet Chart**. 
  - *How to use*: Plot a semi-circle dial from 0% to 15% with color banding (Red: 0-4%, Yellow: 4-7%, Green: 7%+). Display the `roi_yield_percentage` centrally. Underneath, use a bullet chart (slider) to visually display where the median rent falls inside the min/max `rent_range`.

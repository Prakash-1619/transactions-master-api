from fastapi import FastAPI, HTTPException, Query
import pandas as pd
import os
import math

app = FastAPI(title="Dubai Real Estate Smart ROI API")

DATA_FILE = 'dubai_market_yield_report.csv'
COORDS_FILE = 'Area_co_ordinates_rental_areas.csv'

# --- Utility Functions ---

def load_data(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    return pd.read_csv(file_path)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula to calculate distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_closest_area(lat, lon):
    """Finds the nearest area name within 5km from the coordinates file."""
    coords_df = load_data(COORDS_FILE)
    if coords_df.empty:
        return None, "Coordinates data missing."
    
    # Clean coordinate columns
    coords_df['Latitude'] = pd.to_numeric(coords_df['Latitude'], errors='coerce')
    coords_df['Longitude'] = pd.to_numeric(coords_df['Longitude'], errors='coerce')
    coords_df = coords_df.dropna(subset=['Latitude', 'Longitude'])

    coords_df['dist'] = coords_df.apply(lambda r: calculate_distance(lat, lon, r['Latitude'], r['Longitude']), axis=1)
    nearest = coords_df.sort_values('dist').iloc[0]

    if nearest['dist'] > 5.0:
        return None, f"Nearest area ({nearest['area_name_en']}) is too far ({round(nearest['dist'], 2)}km)."
    
    return nearest['area_name_en'], None

# --- API Endpoints ---

@app.get("/calculate_roi")
async def get_roi(
    area_name: str = Query(None, description="Name of the area, e.g., 'Al Barsha First'"),
    lat: float = Query(None, description="Latitude for location-based search"),
    lon: float = Query(None, description="Longitude for location-based search"),
    room_id: int = Query(..., description="Room ID (0: Studio, 1: 1BHK, etc.)"),
    year: int = Query(2026, description="The analysis year"),
    custom_annual_rent: float = Query(None, description="Optional override for annual rent"),
    custom_transaction_amount: float = Query(None, description="Optional override for purchase price")
):
    """
    Calculates ROI/Yield. Provide EITHER area_name OR (lat and lon).
    """
    # 1. Resolve Area Name
    target_area = area_name
    location_msg = "Direct Area Match"

    if lat is not None and lon is not None:
        target_area, error = find_closest_area(lat, lon)
        if error:
            raise HTTPException(status_code=404, detail=error)
        location_msg = f"Nearest Area Found via GPS: {target_area}"
    
    if not target_area:
        raise HTTPException(status_code=400, detail="Must provide either area_name or both lat and lon.")

    # 2. Load Market Data
    df = load_data(DATA_FILE)
    if df.empty:
        raise HTTPException(status_code=503, detail="Market data file not found.")
    
    # 3. Locate market row
    match = df[
        (df['area_name_en'].str.lower() == target_area.lower()) & 
        (df['room_id'] == room_id) & 
        (df['year'] == year)
    ]

    if match.empty:
        raise HTTPException(status_code=404, detail=f"No market data found for {target_area} in {year}.")

    row = match.iloc[0]
    
    # 4. Calculation Logic
    final_price = custom_transaction_amount if custom_transaction_amount is not None else row['median_transaction_amount']
    final_rent = custom_annual_rent if custom_annual_rent is not None else row['median_annual_rent']
    
    if final_price <= 0:
        raise HTTPException(status_code=400, detail="Transaction amount must be greater than zero.")
        
    calculated_yield = (final_rent / final_price) * 100

    return {
        "status": "Success",
        "search_method": location_msg,
        "area": row['area_name_en'],
        "rooms": row['rooms_en'],
        "year": int(row['year']),
        "roi_yield_percentage": round(calculated_yield, 2),
        "market_reference": {
            "median_rent": row['median_annual_rent'],
            "median_price": row['median_transaction_amount'],
            "rent_range": {"min": row['min_annual_rent'], "max": row['max_annual_rent']}
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
import os

app = FastAPI(title="Dubai Real Estate Yield API")

DATA_FILE = 'dubai_market_yield_report.csv'

def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    return pd.read_csv(DATA_FILE)

@app.get("/calculate_roi")
async def get_roi(
    area_name: str = Query(..., description="Name of the area, e.g., 'Al Barsha First'"),
    room_id: int = Query(..., description="Room ID (0: Studio, 1: 1BHK, etc.)"),
    year: int = Query(2026, description="The analysis year"),
    custom_annual_rent: float = Query(None, description="Optional override for annual rent"),
    custom_transaction_amount: float = Query(None, description="Optional override for purchase price")
):
    """
    Calculates ROI/Yield using GET query parameters.
    Example: /calculate_roi?area_name=Al%20Barsha%20First&room_id=1&custom_annual_rent=75000
    """
    df = load_data()
    if df.empty:
        raise HTTPException(status_code=503, detail="Data file not found. Run main.py first.")
    
    # Locate specific market row (Case-insensitive match)
    match = df[
        (df['area_name_en'].str.lower() == area_name.lower()) & 
        (df['room_id'] == room_id) & 
        (df['year'] == year)
    ]

    if match.empty:
        raise HTTPException(status_code=404, detail="No market data found for this area/room combo.")

    row = match.iloc[0]
    
    # Determine Transaction Amount (Purchase Price)
    # Uses custom input if provided, otherwise defaults to market median
    final_price = custom_transaction_amount if custom_transaction_amount is not None else row['median_transaction_amount']
    
    # Determine Annual Rent
    # Uses custom input if provided, otherwise defaults to market median
    final_rent = custom_annual_rent if custom_annual_rent is not None else row['median_annual_rent']
    
    if final_price <= 0:
        raise HTTPException(status_code=400, detail="Transaction amount must be greater than zero.")
        
    # Calculate Yield (ROI)
    calculated_yield = (final_rent / final_price) * 100

    return {
        "area": row['area_name_en'],
        "rooms": row['rooms_en'],
        "year": int(row['year']),
        "calculation_basis": {
            "annual_rent": {
                "value": final_rent,
                "source": "Custom Input" if custom_annual_rent else "Market Median"
            },
            "transaction_amount": {
                "value": final_price,
                "source": "Custom Input" if custom_transaction_amount else "Market Median"
            }
        },
        "roi_yield_percentage": round(calculated_yield, 2),
        "market_reference": {
            "median_rent": row['median_annual_rent'],
            "median_price": row['median_transaction_amount'],
            "rent_range": {
                "min": row['min_annual_rent'],
                "max": row['max_annual_rent']
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from roi_router import router as roi_router, init_roi_data
from dubai_router import router as dubai_router
from abudhabi_router import router as abudhabi_router
from market_router import router as market_router
from duckdb_setup import init_db

app = FastAPI(title="Real Estate Insights — Master API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    # Initialize ROI cache if missing
    init_roi_data()
    # Initialize DuckDB tables from R2
    # init_db()  # Removed local caching per user request

@app.get("/")
def root():
    return {
        "message": "Welcome to the Real Estate Insights Master API. Navigate to /docs for interactive documentation.",
        "endpoints": {
            "roi": {
                "refresh_data": "POST /api/v1/roi/refresh-data",
                "calculate_roi": "GET /api/v1/roi/calculate_roi"
            },
            "dubai": {
                "refresh_data": "POST /api/v1/dubai/refresh-data",
                "filter_data": "GET /api/v1/dubai/filter-data",
                "growth_insights": "GET /api/v1/dubai/insights/growth"
            },
            "abu_dhabi": {
                "transactions": "GET /api/v1/abudhabi/transactions",
                "growth_insights": "GET /api/v1/abudhabi/insights/growth",
                "distribution_insights": "GET /api/v1/abudhabi/insights/distribution"
            },
            "unified_market": {
                "refresh_data": "POST /market/refresh-data",
                "insights": "GET /market/insights"
            }
        }
    }

# Mount all routers
app.include_router(roi_router, prefix="/api/v1/roi", tags=["ROI Calculator"])
app.include_router(dubai_router, prefix="/api/v1/dubai", tags=["Dubai"])
app.include_router(abudhabi_router, prefix="/api/v1/abudhabi", tags=["Abu Dhabi"])
app.include_router(market_router, prefix="/market", tags=["Unified Market API"])

from insights_api.unified_router import router as unified_router
app.include_router(unified_router, prefix="/market/insights/unified", tags=["Unified Macro Insights"])

# If you run `python master_api.py`, this starts uvicorn locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("master_api:app", host="0.0.0.0", port=8003, reload=True)

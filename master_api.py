from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

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
    pass
    # Initialize DuckDB tables from R2
    # init_db()  # Removed local caching per user request

@app.get("/")
def root():
    return {
        "message": "Welcome to the Real Estate Insights Master API. Navigate to /docs for interactive documentation.",
        "endpoints": {
            "unified_market": {
                "refresh_data": "POST /market/refresh-data",
                "insights": "GET /market/insights"
            }
        }
    }

# Mount routers
app.include_router(market_router, prefix="/market", tags=["Unified Market API"])

from insights_api.unified_router import router as unified_router
app.include_router(unified_router, prefix="/market/insights/unified", tags=["Unified Macro Insights"])

# If you run `python master_api.py`, this starts uvicorn locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("master_api:app", host="0.0.0.0", port=8003, reload=True)

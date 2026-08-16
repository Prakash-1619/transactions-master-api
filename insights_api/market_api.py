from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from market_router import router as market_router

app = FastAPI(title="Real Estate Insights — Market API (Dubai & Abu Dhabi)")

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

@app.get("/")
def root():
    return {
        "message": "Welcome to the Market API (Dubai & Abu Dhabi). Navigate to /docs for interactive documentation.",
        "endpoints": {
            "market": {
                "filter_data": "GET /market/filter-data",
                "growth_insights": "GET /market/insights/growth",
                "refresh_data": "POST /market/refresh-data"
            }
        }
    }

# Mount the unified market router
app.include_router(market_router, prefix="/market", tags=["Unified Market API"])

from unified_router import router as unified_router
app.include_router(unified_router, prefix="/market/insights/unified", tags=["Unified Macro Insights"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("market_api:app", host="127.0.0.1", port=8003, reload=True)

# master_api.py
# Single entrypoint that mounts the Dubai and Abu Dhabi routers.
# No filtering/cleaning/aggregation logic lives here — it's all
# untouched in filtering_df.py (Dubai) and services.py (Abu Dhabi).
#
# Run with: uvicorn master_api:app --reload

from fastapi import FastAPI

from dubai_router import router as dubai_router
from abudhabi_router import router as abudhabi_router, load_data as load_abudhabi_data

app = FastAPI(title="Real Estate Insights — Master API")

# Dubai endpoints:
#   POST /api/v1/dubai/refresh-data      (unchanged logic from api.py)
#   GET  /api/v1/dubai/filter-data       (unchanged logic from api.py)
#   GET  /api/v1/dubai/insights/growth   (new — reuses filter-data's filtering,
#                                          mirrors Abu Dhabi's growth calc)
app.include_router(dubai_router, prefix="/api/v1/dubai", tags=["Dubai"])

# Abu Dhabi endpoints (unchanged logic from main.py), matching the
# paths documented in readme.md:
#   GET /api/v1/abudhabi/transactions
#   GET /api/v1/abudhabi/insights/growth
#   GET /api/v1/abudhabi/insights/distribution
app.include_router(abudhabi_router, prefix="/api/v1/abudhabi", tags=["Abu Dhabi"])


@app.on_event("startup")
def startup_event():
    # Dubai's raw_df is loaded at import time inside dubai_router.py
    # (same behavior as the original api.py). Abu Dhabi's df_main is
    # loaded here, same load_data() body as the original main.py.
    load_abudhabi_data()


@app.get("/")
def root():
    return {
        "message": "Real Estate Insights Master API",
        "cities": {
            "dubai": {
                "refresh_data": "POST /api/v1/dubai/refresh-data",
                "filter_data": "GET /api/v1/dubai/filter-data",
                "growth_insights": "GET /api/v1/dubai/insights/growth"
            },
            "abu_dhabi": {
                "transactions": "GET /api/v1/abudhabi/transactions",
                "growth_insights": "GET /api/v1/abudhabi/insights/growth",
                "distribution_insights": "GET /api/v1/abudhabi/insights/distribution"
            }
        }
    }

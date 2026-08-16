# API Endpoint Test Report

Testing 9 Unified Macro Insights Endpoints against base URL http://127.0.0.1:8003/market/insights/unified

? GET /tiles
- **Status:** 200
- **Latency:** 3.809s
- **Rental Status (2023):** 200 (57.807s)

? GET /growth_and_yield
- **Status:** 200
- **Latency:** 2.603s
- **Rental Status (2023):** 200 (11.288s)

? GET /distributions/price_bins
- **Status:** 200
- **Latency:** 0.604s
- **Rental Status (2023):** 200 (9.377s)

? GET /distributions/grouped
- **Status:** 422
- **Latency:** 0.080s
- **Error:** {"detail":[{"type":"missing","loc":["query","group_by"],"msg":"Field required","input":null}]}
- **Rental Status (2023):** 422 (0.006s)

  - **Error:** {"detail":[{"type":"missing","loc":["query","group_by"],"msg":"Field required","input":null}]}
? GET /area_vs_price
- **Status:** 200
- **Latency:** 0.553s
- **Rental Status (2023):** 200 (0.583s)

? GET /feature_prices
- **Status:** 200
- **Latency:** 0.431s
- **Rental Status (2023):** 200 (0.379s)

? GET /top_bottom_performers
- **Status:** 200
- **Latency:** 0.508s
- **Rental Status (2023):** 200 (0.543s)

? GET /plots/unified_growth
- **Status:** 200
- **Latency:** 1.507s
- **Rental Status (2023):** 200 (10.930s)

? GET /transactions
- **Status:** 200
- **Latency:** 0.726s
- **Rental Status (2023):** 200 (16.213s)


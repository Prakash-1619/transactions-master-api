This documentation provides a comprehensive, deep-dive into each Python module within the **Dubai Real Estate ROI & Yield Engine**. It details the logic, specific pandas operations, and error-handling strategies used to maintain data integrity across the pipeline.

---

### **1. `rental_processor.py`**
**Core Function:** Standardizes multi-year rental data and performs ML-based feature enrichment.

* **Data Ingestion & Filtering:** * Loads historical records from a **2023–2025 Parquet file** to leverage high-speed I/O.
    * Filters raw 2026 CSV data where `PROP_TYPE_EN == 'Unit'` and `PROP_SUB_TYPE_EN == 'Flat'`. This ensures the ML model only predicts for comparable residential assets.
* **The ML Inference Pipeline:**
    * **Preprocessing:** Extracts `ACTUAL_AREA` and `ANNUAL_AMOUNT` as features. It applies a `.fillna(0)` to prevent the **Random Forest** model from crashing on null inputs.
    * **Inference:** Uses `joblib` to load the `room_classifier_model` and `room_type_encoder`. 
    * **Decoding:** Converts numeric model outputs (0, 1, 2) back into human-readable labels (Studio, 1BHK, 2BHK) using the `inverse_transform` method.
* **Column Standardization:** * Uses a hardcoded mapping dictionary to align the 2026 raw DLD headers with the 2023 schema. 
    * **Critical Step:** Converts `contract_start_date` to a **datetime object** and extracts `.dt.year` to facilitate time-series aggregation.

---

### **2. `transaction_processor.py`**
**Core Function:** Prepares a clean purchase price baseline from sales records.

* **Transaction Scrubbing:** * Filters out **"Gifts"** from the `trans_group_en` column. Gift transactions often have a "0" or nominal value, which would artificially inflate the rental yield calculation.
* **Memory Optimization:** * Instead of keeping all 39 columns from the DLD dataset, it subsets only **5 mandatory fields**: `actual_worth`, `rooms_en`, `area_name_en`, `instance_date`, and `year`. 
    * This reduces the DataFrame memory footprint by roughly **85%**, allowing the script to run on standard cloud instances.
* **Temporal Alignment:** * Standardizes `instance_date` to ensure that transaction "years" perfectly align with rental "years" during the final merge.

---

### **3. `yield_calculator.py`**
**Core Function:** The join engine and statistical aggregator.

* **Room ID Normalization:** * Creates a `room_id` column (0 for Studio, 1 for 1BHK, etc.). This solves the **"naming mismatch"** problem where one dataset uses "1BHK" and the other uses "1 B/R".
* **Multi-Metric Aggregation:** * For each **Area + Room + Year** bucket, it calculates:
        * `median_annual_rent`: The stable average for yield.
        * `min_annual_rent` & `max_annual_rent`: To provide market "floors" and "ceilings."
        * `median_transaction_amount`: The average acquisition cost.
* **Financial Computation:** * Applies the vectorized formula: `(median_rent / median_price) * 100`. 
    * Uses `.round()` to provide clean, user-friendly percentages.

---

### **4. `main.py`**
**Core Function:** Orchestrates the ETL (Extract, Transform, Load) workflow.

* **Execution Flow:** Calls `get_processed_rental_data()` $\rightarrow$ `get_processed_transaction_data()` $\rightarrow$ `calculate_yearly_yield()`.
* **Persistence Layer:** * Writes the final result to `dubai_market_yield_report.csv`. 
    * This CSV acts as a **Flat-File Database** that the API reads, ensuring the API doesn't have to re-calculate heavy ML or grouping logic on every request.

---

### **5. `api.py`**
**Core Function:** High-concurrency service layer for end-user interaction.

* **FastAPI Framework:** * Uses **Pydantic-style Query Parameters** for input validation.
    * Includes a `load_data()` function with `os.path.exists` checks to ensure the API doesn't crash if the `main.py` hasn't generated the report yet.
* **Logic Hierarchy (The Calculator):** * **Case-Insensitive Matching:** Converts user-input `area_name` to lowercase to ensure "Dubai Marina" and "dubai marina" both work.
    * **Dynamic Override:** The code uses a conditional check: `final_price = custom_price if custom_price else market_median`. This allows for **personalized ROI** (if you know your exact price) or **market ROI** (if you are just researching).



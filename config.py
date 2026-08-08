# config.py
import os

# --- Base Directory ---
BASE_DIR = "/home/ubuntu/Working_Space/data/DLD_DATA/Transactions_api"
processed_file = os.path.join(BASE_DIR,'Latest_data')
# --- File Paths ---
TRANSACTIONS_FILE = os.path.join(BASE_DIR, 'transactions_2026-05-21_02-13-21_1.csv.gz')
PROJECTS_FILE = os.path.join(BASE_DIR, 'projects_2026-05-21_02-07-22_1.csv.gz')
DEVELOPERS_FILE = os.path.join(BASE_DIR, 'developers_2026-04-29_13-38-06_1.csv.gz')
AREA_COORDS_FILE = os.path.join(BASE_DIR, 'area_coords_df.csv')
CACHE_FILE = os.path.join(processed_file, 'processed_data.parquet')


# Add this line to your config.py
abudhabi_transactions =  os.path.join(processed_file, "Abu_dhabi_sales.csv")
# --- Base Data Cleaning Rules ---
BASELINE_START_DATE = '2020-01-01'
ALLOWED_TRANS_GROUPS = ['Sales', 'Mortgages']
ALLOWED_PROPERTY_TYPES = ['Unit', 'Villa']
ALLOWED_PROPERTY_USAGES = ['Residential', 'Commercial']

COLUMNS_TO_DROP = [
    'procedure_name_en', 'rent_value', 'meter_rent_price', 
    'no_of_parties_role_1', 'no_of_parties_role_2', 
    'no_of_parties_role_3', 'load_timestamp'
]

# --- Outlier Thresholds ---
HARD_MIN_PERCENTILE = 0.05  
HARD_MAX_PERCENTILE = 0.95  
GRANULAR_LOWER_PERCENTILE = 0.01 
GRANULAR_UPPER_PERCENTILE = 0.99 

# --- API & Pagination Defaults ---
DEFAULT_RADIUS_KM = 5.0
DEFAULT_PAGE_SIZE = 25
ALLOWED_PAGE_SIZES = [25, 50, 100]

# --- Mappings & Lookups ---
ROOM_TO_ID = {
    'Studio': 1, '1 B/R': 2, '2 B/R': 3, '3 B/R': 4,
    '4 B/R': 5, '5 B/R': 6, '6 B/R': 7, '7 B/R': 8, '8 B/R': 9
}

MIN_AREA_BY_SUBTYPE = {
    1: 25, 2: 50, 3: 80, 4: 100, 5: 140,
    6: 170, 7: 200, 8: 250, 9: 300, 10: 330, 621: 80
}

RETURN_COLUMNS = [
    'trans_group_en', 'instance_date', 'year_month', 'property_type_en',
    'property_sub_type_en', 'property_usage_en', 'reg_type_en',
    'area_name_en', 'building_name_en', 'project_number', 'project_name_en',
    'master_project_en_x', 'nearest_landmark_en', 'nearest_metro_en',
    'nearest_mall_en', 'rooms_en', 'has_parking', 'procedure_area',
    'actual_worth', 'meter_sale_price', 'project_start_date', 'developer_name_en'
]
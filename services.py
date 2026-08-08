import pandas as pd
from schemas import DataFilter

def clean_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans top 1% and bottom 1% outliers grouped by Asset Class 
    for Area, Price, and Rate sequentially.
    """
    cols_to_clean = [
        'Property Sold Area (SQM)', 
        'Property Sale Price (AED)', 
        'Rate (AED per SQM)'
    ]
    
    if 'Asset Class' not in df.columns:
        return df

    def filter_group_outliers(group):
        mask = pd.Series(True, index=group.index)
        for col in cols_to_clean:
            if col in group.columns:
                q_low = group[col].quantile(0.01)
                q_high = group[col].quantile(0.99)
                col_mask = (group[col] >= q_low) & (group[col] <= q_high) | group[col].isna()
                mask = mask & col_mask
        return group[mask]

    return df.groupby('Asset Class', group_keys=False).apply(filter_group_outliers)

def apply_filters(df: pd.DataFrame, filters: DataFilter) -> pd.DataFrame:
    filtered_df = df.copy()
    
    # 1. Timeframe filtering
    if filters.start_date:
        filtered_df = filtered_df[filtered_df['Sale Application Date'] >= pd.to_datetime(filters.start_date)]
    if filters.end_date:
        filtered_df = filtered_df[filtered_df['Sale Application Date'] <= pd.to_datetime(filters.end_date)]
        
    # 2. Categorical filtering with string splitting
    filter_map = {
        'Asset Class': filters.asset_class,
        'Property Type': filters.property_type,
        'Property Layout': filters.property_layout,
        'District': filters.district,
        'Community': filters.community,
        'Project Name': filters.project_name,
        'Sale Sequence': filters.sale_sequence
    }
    
    for col, value_str in filter_map.items():
        # If the parameter is missing or empty, it skips this block completely 
        # and leaves all rows selected by default.
        if value_str:  
            # Split the comma-separated string and strip whitespace from values
            values_list = [val.strip() for val in value_str.split(',') if val.strip()]
            if values_list:
                filtered_df = filtered_df[filtered_df[col].isin(values_list)]
            
    return filtered_df
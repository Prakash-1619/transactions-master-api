import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuration
st.set_page_config(page_title="Real Estate Insights", page_icon="🏢", layout="wide")
API_BASE_URL = "http://localhost:8003"

# Custom CSS for Golden & Dark Theme Enhancements
st.markdown("""
<style>
    /* Premium Title Styling */
    h1 {
        color: #D4AF37 !important;
        font-weight: 300 !important;
        letter-spacing: 1px;
    }
    h2, h3 {
        color: #C5B358 !important;
        font-weight: 400 !important;
    }
    
    /* Subtle glow on metric containers */
    [data-testid="stMetricValue"] {
        color: #D4AF37 !important;
        font-weight: bold;
    }
    [data-testid="stMetricDelta"] {
        color: #E0E0E0 !important;
    }
    
    /* Adjusting container styling for a slick look */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent !important;
        border-radius: 4px;
        color: #E0E0E0 !important;
        font-size: 16px;
    }
    .stTabs [aria-selected="true"] {
        color: #D4AF37 !important;
        border-bottom: 2px solid #D4AF37 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 Premium Real Estate Dashboard")
st.markdown("*A unified, high-performance view of Dubai and Abu Dhabi real estate markets.*")

# Sidebar global filters
st.sidebar.header("Global Filters")
emirate = st.sidebar.selectbox("Emirate", ["Dubai", "Abu Dhabi", "Both (Unified)"], index=2)
emirate_val = None if emirate == "Both (Unified)" else emirate

area = st.sidebar.text_input("Area Name (Optional)", "")
room_type = st.sidebar.text_input("Room Type (Optional)", "")
property_type = st.sidebar.text_input("Property Type (Optional)", "")
start_date = st.sidebar.date_input("Start Date", value=None)
end_date = st.sidebar.date_input("End Date", value=None)

def build_params(extra=None):
    p = {}
    if emirate_val: p['emirate'] = emirate_val
    if area: p['area'] = area
    if room_type: p['room_type'] = room_type
    if property_type: p['property_type'] = property_type
    if start_date: p['start_date'] = start_date.strftime("%Y-%m-%d")
    if end_date: p['end_date'] = end_date.strftime("%Y-%m-%d")
    if extra:
        p.update(extra)
    return {k: v for k, v in p.items() if v}

# Plotly Theme Setup
PLOTLY_TEMPLATE = "plotly_dark"
GOLD_PRIMARY = "#D4AF37"
GOLD_SECONDARY = "#C5B358"
GOLD_TERTIARY = "#FFDF00"
DARK_ACCENT = "#2C2C2C"

tab1, tab2 = st.tabs(["📊 Market Overview & Growth", "🔍 Advanced Insights & ROI"])

with tab1:
    st.header("Market Overview")
    
    # 1. Tiles
    try:
        tiles_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/tiles", params=build_params()).json()
        if tiles_resp.get("status") == "success":
            tiles = tiles_resp["tiles"]
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Median Sale Price", f"AED {tiles.get('median_sale_price', 0):,.0f}")
            col2.metric("Total Volume", f"{tiles.get('total_sales_volume', 0):,}")
            col3.metric("Total Sales Value", f"AED {tiles.get('total_sales_aed', 0):,.0f}")
            col4.metric("Median Rate/SQM", f"AED {tiles.get('median_rate_sqm', 0):,.0f}")
            col5.metric("Median Annual Rent", f"AED {tiles.get('median_annual_rent', 0):,.0f}")
    except Exception as e:
        st.error(f"Could not load KPI tiles: {e}")
        
    st.markdown("---")
    
    # 2. Growth and Yield
    st.subheader("Market Growth & Yield Trends")
    metric = st.selectbox("Select Metric for Trend", ["median_price", "volume", "total_price", "median_rate"])
    comp_type = st.selectbox("Comparison Interval", ["yoy", "qoq", "mom"])
    
    try:
        growth_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/growth_and_yield", params=build_params({"metric": metric, "comparison_type": comp_type})).json()
        if growth_resp.get("status") == "success" and growth_resp.get("data"):
            df_growth = pd.DataFrame(growth_resp["data"])
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_growth['Period'], y=df_growth['Sales_Value'], name="Sales Value", marker_color=GOLD_PRIMARY))
            if 'Rental_Value' in df_growth.columns:
                fig.add_trace(go.Bar(x=df_growth['Period'], y=df_growth['Rental_Value'], name="Rental Value", marker_color=DARK_ACCENT))
            
            if 'Gross_Rental_Yield' in df_growth.columns:
                fig.add_trace(go.Scatter(x=df_growth['Period'], y=df_growth['Gross_Rental_Yield'], name="Gross Yield %", yaxis="y2", line=dict(color=GOLD_TERTIARY, width=3, dash='dot')))
                
            fig.update_layout(
                template=PLOTLY_TEMPLATE,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                title="Market Trends Over Time",
                xaxis_title="Period",
                yaxis_title="Value",
                yaxis2=dict(title="Yield %", overlaying="y", side="right", range=[0, 15]),
                barmode='group',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No growth data available for current filters.")
    except Exception as e:
        st.error(f"Could not load Growth & Yield: {e}")
        
    st.markdown("---")
        
    # 3. Grouped Distribution (Donut Chart)
    st.subheader("Market Distribution")
    dist_metric = st.selectbox("Metric for Distribution", ["volume", "median_price", "total_price"])
    colA, colB = st.columns(2)
    
    gold_color_sequence = [GOLD_PRIMARY, GOLD_SECONDARY, GOLD_TERTIARY, '#9E8231', '#F5D76E', '#C0A040', '#E5C158', '#403816']
    
    with colA:
        try:
            grp_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/distributions/grouped", params=build_params({"metric": dist_metric, "group_by": "property_type"})).json()
            if grp_resp.get("status") == "success" and grp_resp.get("data"):
                df_grp = pd.DataFrame(grp_resp["data"])
                fig_pie = px.pie(df_grp, values='Value', names='Group_Category', hole=0.5, title="By Property Type", color_discrete_sequence=gold_color_sequence)
                fig_pie.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No property type distribution data.")
        except Exception as e:
            st.error(f"Error loading grouped distribution: {e}")
            
    with colB:
        try:
            grp_resp2 = requests.get(f"{API_BASE_URL}/market/insights/unified/distributions/grouped", params=build_params({"metric": dist_metric, "group_by": "room_type"})).json()
            if grp_resp2.get("status") == "success" and grp_resp2.get("data"):
                df_grp2 = pd.DataFrame(grp_resp2["data"])
                fig_pie2 = px.pie(df_grp2, values='Value', names='Group_Category', hole=0.5, title="By Room Type", color_discrete_sequence=gold_color_sequence)
                fig_pie2.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pie2, use_container_width=True)
            else:
                st.info("No room type distribution data.")
        except Exception as e:
            st.error(f"Error loading grouped distribution: {e}")


with tab2:
    st.header("Advanced Insights & ROI")
    
    # 1. Price Bins
    st.subheader("Liquidity Distribution (Price Bins)")
    try:
        bin_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/distributions/price_bins", params=build_params({"metric": "volume"})).json()
        if bin_resp.get("status") == "success" and bin_resp.get("data"):
            df_bins = pd.DataFrame(bin_resp["data"])
            fig_bar = px.bar(df_bins, x="Price_Bin", y="Value", title="Transaction Volume by Price Band", color="Price_Bin", color_discrete_sequence=gold_color_sequence)
            fig_bar.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No price bin data available.")
    except Exception as e:
        st.error(f"Error loading price bins: {e}")
        
    st.markdown("---")
        
    # 2. Area vs Price Scatter
    st.subheader("Area vs Price Valuation")
    try:
        ap_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/area_vs_price", params=build_params({"limit": 500})).json()
        if ap_resp.get("scatter_data"):
            df_ap = pd.DataFrame(ap_resp["scatter_data"])
            fig_scatter = px.scatter(df_ap, x="area_sqm", y="Value", color="room_type", title="Property Valuation vs Square Meters (Max 500 samples)", opacity=0.8, color_discrete_sequence=gold_color_sequence)
            fig_scatter.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("No area vs price data available.")
    except Exception as e:
        st.error(f"Error loading area vs price: {e}")
        
    st.markdown("---")
        
    # 3. Features
    st.subheader("Feature Premiums (Beta)")
    try:
        f_resp = requests.get(f"{API_BASE_URL}/market/insights/unified/feature_prices").json()
        if f_resp.get("status") == "success":
            st.json(f_resp["data"])
    except:
        pass

    st.markdown("---")
        
    # 4. ROI Calculator & Map
    st.subheader("ROI & Yield Calculator")
    st.markdown("Use the inputs below to calculate expected Gross Rental Yield for a specific community.")
    
    col_input, col_map = st.columns([1, 2])
    
    with col_input:
        roi_area = st.text_input("Area Name (e.g. Marina)", value="Marina")
        room_id = st.number_input("Room ID (0=Studio, 1=1BHK)", min_value=0, max_value=10, value=1)
        roi_year = st.number_input("Analysis Year", min_value=2010, max_value=2030, value=2026)
        
        custom_rent = st.number_input("Custom Annual Rent (Optional)", min_value=0, value=0)
        custom_price = st.number_input("Custom Transaction Amount (Optional)", min_value=0, value=0)
        
        calc_btn = st.button("Calculate Yield", type="primary")
        
    with col_map:
        st.markdown("**Area Coordinates Reference**")
        # Base map view centering
        if emirate_val == "Abu Dhabi":
            df_map = pd.DataFrame({'lat': [24.4539], 'lon': [54.3773], 'name': ['Abu Dhabi Center'], 'color': [GOLD_PRIMARY]})
        else:
            df_map = pd.DataFrame({'lat': [25.2048], 'lon': [55.2708], 'name': ['Dubai Center'], 'color': [GOLD_PRIMARY]})
        
        # Use pydeck for custom colors
        import pydeck as pdk
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v10',
            initial_view_state=pdk.ViewState(
                latitude=df_map['lat'].iloc[0],
                longitude=df_map['lon'].iloc[0],
                zoom=10,
                pitch=0,
            ),
            layers=[
                pdk.Layer(
                    'ScatterplotLayer',
                    data=df_map,
                    get_position='[lon, lat]',
                    get_color='[212, 175, 55, 200]', # Gold color [R, G, B, A]
                    get_radius=1000,
                ),
            ],
        ))
        
    if calc_btn:
        roi_params = {
            "area_name": roi_area,
            "room_id": room_id,
            "year": roi_year
        }
        if custom_rent > 0: roi_params["custom_annual_rent"] = custom_rent
        if custom_price > 0: roi_params["custom_transaction_amount"] = custom_price
        
        try:
            roi_resp = requests.get(f"{API_BASE_URL}/api/v1/roi/calculate_roi", params=roi_params)
            if roi_resp.status_code == 200:
                data = roi_resp.json()
                yield_pct = data.get("roi_yield_percentage", 0)
                
                # Gauge Chart
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = yield_pct,
                    title = {'text': f"Expected Yield % - {data.get('area')} ({data.get('rooms')})", 'font': {'color': GOLD_PRIMARY}},
                    number = {'font': {'color': GOLD_PRIMARY}},
                    gauge = {
                        'axis': {'range': [None, 15], 'tickcolor': "white"},
                        'bar': {'color': GOLD_TERTIARY},
                        'bgcolor': "rgba(0,0,0,0)",
                        'steps': [
                            {'range': [0, 5], 'color': DARK_ACCENT},
                            {'range': [5, 8], 'color': "#4A3F10"},
                            {'range': [8, 15], 'color': GOLD_SECONDARY}],
                    }
                ))
                fig_gauge.update_layout(template=PLOTLY_TEMPLATE, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_gauge, use_container_width=True)
                
                # Reference Data
                st.json(data["market_reference"])
            else:
                st.error(f"API Error {roi_resp.status_code}: {roi_resp.text}")
        except Exception as e:
            st.error(f"Error calculating ROI: {e}")

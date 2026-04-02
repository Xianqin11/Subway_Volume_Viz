import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from pathlib import Path

# --- 1. 页面基本设置 ---
st.set_page_config(layout="wide", page_title="轨道站点客流可视化", page_icon="🚇")
st.title("🚇 轨道站点客流与线路可视化")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# --- 2. 数据加载引擎 ---
@st.cache_data(show_spinner="正在云端加载空间数据，请稍候...")
def load_data():
    try:
        # 加载客流数据
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
        
        # 加载地理数据
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        # 数据融合
        merged_stations = gdf_stations.merge(df_flow, left_on='站点', right_on='stations', how='inner')
        
        # 提取经纬度
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        return merged_stations, gdf_lines
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None

df_stations, gdf_lines = load_data()

# --- 3. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    st.success(f"🎉 成功拼接了 {len(df_stations)} 个站点的数据！")
    
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    try:
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        # 【修改 1】：客流大于 50000 人次显示红色，否则绿色
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
        )

        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color=[100, 150, 250, 150],
            get_line_width=20,
            line_width_min_pixels=2,
        )

        layer_stations = pdk.Layer(
            "ScatterplotLayer",
            df_stations,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius=SAFE_COL,   
            # 【修改 2】：极小比例，把几万的数字缩小成合适的半径 (比如 50000 * 0.02 = 1000米)
            radius_scale=0.02,      
            radius_min_pixels=3,
            pickable=True,
        )

        view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            # 【修改 3】：把悬浮框里的“万”字删掉了，直接显示真实人次
            tooltip={"html": f"<b>{{stations}}</b><br/>进站量: {{{SAFE_COL}}} 人次"}
        ))
        
    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

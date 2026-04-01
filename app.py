import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from pathlib import Path

# --- 1. 页面基本设置 ---
st.set_page_config(layout="wide", page_title="轨道站点客流可视化", page_icon="🚇")
st.title("🚇 轨道站点客流与线路可视化")

# 获取云端/本地都通用的绝对路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# --- 2. 数据加载引擎 ---
@st.cache_data(show_spinner="正在云端加载空间数据，请稍候...")
def load_data():
    try:
        # 1. 加载客流数据 (读取你改好后缀的 Excel 文件)
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
        
        # 2. 加载地理数据，并统一转换坐标系为高德/Pydeck支持的 WGS84 (EPSG:4326)
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp").to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp").to_crs(epsg=4326)
        
        # 3. 数据融合：将客流数据挂载到车站坐标上
        # 注意：这里假设 shp 里的站名字段叫 'NAME'，CSV里叫 'stations'
        # 打印出地图文件到底有哪些列名
        st.info(f"地图文件包含的列名有: {gdf_stations.columns.tolist()}")
        merged_stations = gdf_stations.merge(df_flow, left_on='NAME', right_on='stations', how='inner')
        # 如果报错，我们需要根据你的实际字段名微调这里
        merged_stations = gdf_stations.merge(df_flow, left_on='NAME', right_on='stations', how='inner')
        
        # 提取经纬度供地图渲染
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        return merged_stations, gdf_lines
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None

df_stations, gdf_lines = load_data()

# --- 3. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    # 动态颜色：客流大于 50000 变红，否则为绿色
    df_stations['color'] = df_stations['2025年2月25日进站量'].apply(
        lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
    )

    # 图层 1：线路底图
    layer_lines = pdk.Layer(
        "GeoJsonLayer",
        gdf_lines,
        get_line_color=[100, 150, 250, 150],
        get_line_width=20,
        line_width_min_pixels=2,
    )

    # 图层 2：站点气泡图
    layer_stations = pdk.Layer(
        "ScatterplotLayer",
        df_stations,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="2025年2月25日进站量",
        radius_scale=0.03,  # 控制气泡缩放比例
        pickable=True,
    )

    # 设置地图初始视角 (北京中心)
    view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

    # 渲染出图
    st.pydeck_chart(pdk.Deck(
        layers=[layer_lines, layer_stations],
        initial_view_state=view_state,
        map_style="light", 
        tooltip={"html": "<b>{stations}</b><br/>进站量: {2025年2月25日进站量} 人次"}
    ))

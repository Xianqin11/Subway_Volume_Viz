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
        
        # 加载地理数据 (彻底解决中文乱码)
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        # 数据融合 (暗号对上：'站点')
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
    
    # 成功提示
    st.success(f"🎉 成功拼接了 {len(df_stations)} 个站点的数据！")
    
    # 原始的中文名字（带有数字，网页前端不认识）
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    # 安全的英文名字（骗过网页浏览器）
    SAFE_COL = 'volume'
    
    try:
        # 【关键魔术】：在代码里把带数字的名字，临时改成安全的英文名字
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        
        # 强行把客流数据转为数字
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        # 动态颜色：单位是万人次，大于5万人次显示红色，否则绿色
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 5 else [50, 200, 50, 200]
        )

        # 线路图层
        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color=[100, 150, 250, 150],
            get_line_width=20,
            line_width_min_pixels=2,
        )

        # 站点气泡图层
        layer_stations = pdk.Layer(
            "ScatterplotLayer",
            df_stations,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius=SAFE_COL,   # 这里使用安全的英文名
            radius_scale=200,      # 放大比例，适配万人次
            radius_min_pixels=3,
            pickable=True,
        )

        # 地图视角
        view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

        # 渲染图表
        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            # 悬浮提示框也使用安全的英文名
            tooltip={"html": f"<b>{{stations}}</b><br/>进站量: {{{SAFE_COL}}} 万人次"}
        ))
        
    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

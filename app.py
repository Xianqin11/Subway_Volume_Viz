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
        # 加载数据
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
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
    
    # 💥 终极侦察兵：看看我们成功匹配了多少个站，以及真正拥有的列名！
    st.success(f"🎉 成功拼接了 {len(df_stations)} 个站点的数据！")
    st.info(f"👉 真实的列名有：{df_stations.columns.tolist()}")
    
    # ========================================================
    # 【最后一步】：把下面这个词，换成上面蓝框里真正代表进站量的词！
    # 比如如果它叫 '进站量'，就把它改成 VOLUME_COL = '进站量'
    # ========================================================
    VOLUME_COL = '2025年2月25日进站量'
    
    try:
        # 强行把客流数据转为数字，防止里面有乱码报错
        df_stations[VOLUME_COL] = pd.to_numeric(df_stations[VOLUME_COL], errors='coerce').fillna(0)
        
        # 动态颜色：客流大于 50000 变红，否则为绿色
        df_stations['color'] = df_stations[VOLUME_COL].apply(
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
            get_radius=VOLUME_COL,
            radius_scale=0.03,  # 控制气泡缩放比例
            pickable=True,
        )

        view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            tooltip={"html": f"<b>{{stations}}</b><br/>进站量: {{{VOLUME_COL}}} 人次"}
        ))
        
    except KeyError:
        st.error(f"🚨 找不到名为 '{VOLUME_COL}' 的列！请看上方蓝框，把代码里的 VOLUME_COL 换成正确的名字。")

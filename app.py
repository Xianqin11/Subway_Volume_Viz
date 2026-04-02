import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from pathlib import Path
import base64

# --- 1. 页面基本设置 ---
st.set_page_config(layout="wide", page_title="轨道站点客流可视化", page_icon="🚇")
st.title("🚇 轨道站点客流与线路可视化")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# ==========================================
# 🚇 终极版：工程代号 -> 官方 RGB 映射表
# ==========================================
def get_line_color(line_code):
    if not isinstance(line_code, str): 
        return [150, 150, 150, 150] # 默认灰色
    
    name = line_code.strip().upper() # 转大写并去除两边空格，确保万无一失
    
    # 精确映射字典
    exact_mapping = {
        "M1": [194, 55, 48], "M2": [0, 70, 147], "M3": [227, 27, 35],
        "M4": [0, 172, 163], "M5": [166, 33, 127], "M6": [237, 157, 0],
        "M7": [255, 199, 44], "M8": [0, 158, 78], "M9": [153, 204, 0],
        "M10": [0, 158, 224], "M11": [237, 121, 107], "M12": [199, 107, 0],
        "M13": [255, 222, 0], "M14": [209, 139, 131], "M15": [106, 53, 125],
        "M16": [96, 176, 66], "M17": [0, 171, 171], "M19": [211, 163, 201],
        "FS": [237, 125, 49], "CP": [231, 131, 183], "YZ": [237, 0, 140],
        "S1": [170, 102, 34], "XJ": [227, 27, 35], "YZT1": [227, 27, 35],
        "JC": [153, 136, 166], "DXJC": [0, 70, 147]
    }
    
    # 优先精确匹配
    if name in exact_mapping:
        return exact_mapping[name] + [255] # 255 是不透明度 (完全不透明)
        
    # 如果是混合词（比如 M1_M2），降级包含匹配，按长词优先防止 M1 覆盖 M10
    for key in sorted(exact_mapping.keys(), key=len, reverse=True):
        if key in name:
            return exact_mapping[key] + [255]
            
    return [150, 150, 150, 150] # 找不到就给灰色

# --- 2. 数据加载引擎 ---
@st.cache_data(show_spinner="正在云端加载空间数据，请稍候...")
def load_data():
    try:
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        merged_stations = gdf_stations.merge(df_flow, left_on='站点', right_on='stations', how='inner')
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        # 既然我们已经确诊列名就叫 '线路'，直接点对点爆破
        if '线路' in gdf_lines.columns:
            gdf_lines['color'] = gdf_lines['线路'].apply(get_line_color)
        else:
            gdf_lines['color'] = pd.Series([[100, 150, 250, 150]] * len(gdf_lines))
            
        return merged_stations, gdf_lines
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None

df_stations, gdf_lines = load_data()

# --- 3. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    try:
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        # 气泡颜色：大于50000人次显示红色，否则显示绿色
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
        )

        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color="color", # 🌈 调取官方色
            get_line_width=25,      
            line_width_min_pixels=3,
            pickable=True,
            # 鼠标放上去可以显示对应的工程代号
            tooltip={"text": "工程代号: {线路}"} if '线路' in gdf_lines.columns else None
        )

        layer_stations = pdk.Layer(
            "ScatterplotLayer",
            df_stations,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius=SAFE_COL,   
            radius_scale=0.02,      
            radius_min_pixels=3,
            pickable=True,
        )

        view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            tooltip={"html": f"<b>{{stations}}</b><br/>进站量: {{{SAFE_COL}}} 人次"}
        ))
        
        # ==========================================
        # 🖼️ 左下角：高级悬浮图例
        # ==========================================
        def get_base64_of_bin_file(bin_file):
            try:
                with open(bin_file, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            except:
                return None

        # 无论你上传的是 png 还是 jpg，都能自动加载
        legend_base64 = get_base64_of_bin_file(DATA_DIR / "legend.png") or get_base64_of_bin_file(DATA_DIR / "legend.jpg")
        
        if legend_base64:
            st.markdown(
                f"""
                <style>
                .legend-container {{
                    position: fixed;
                    bottom: 30px;
                    left: 30px;
                    z-index: 99999;
                    background-color: rgba(255, 255, 255, 0.85);
                    padding: 8px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    backdrop-filter: blur(5px);
                }}
                .legend-container img {{
                    max-height: 350px; /* 控制图例高度 */
                    object-fit: contain;
                }}
                </style>
                <div class="legend-container">
                    <img src="data:image/png;base64,{legend_base64}">
                </div>
                """,
                unsafe_allow_html=True
            )

    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

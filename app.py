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

LINE_COLORS = {
    "1号线": [194, 55, 48], "八通线": [194, 55, 48], "2号线": [0, 70, 147],
    "3号线": [227, 27, 35], "4号线": [0, 172, 163], "大兴线": [0, 172, 163],
    "5号线": [166, 33, 127], "6号线": [237, 157, 0], "7号线": [255, 199, 44],
    "8号线": [0, 158, 78], "9号线": [153, 204, 0], "10号线": [0, 158, 224],
    "11号线": [237, 121, 107], "12号线": [199, 107, 0], "13号线": [255, 222, 0],
    "14号线": [209, 139, 131], "15号线": [106, 53, 125], "16号线": [96, 176, 66],
    "17号线": [0, 171, 171], "19号线": [211, 163, 201], "房山线": [237, 125, 49],
    "昌平线": [231, 131, 183], "亦庄线": [237, 0, 140], "燕房线": [237, 125, 49],
    "S1线": [170, 102, 34], "西郊线": [227, 27, 35], "T1线": [227, 27, 35],
    "首都机场": [153, 136, 166], "大兴机场": [0, 70, 147],
}

def get_line_color(line_name):
    if not isinstance(line_name, str): return [100, 150, 250, 150]
    for key, color in LINE_COLORS.items():
        if key in line_name: return color + [255]
    return [100, 150, 250, 150]

@st.cache_data(show_spinner="正在云端加载空间数据，请稍候...")
def load_data():
    try:
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        merged_stations = gdf_stations.merge(df_flow, left_on='站点', right_on='stations', how='inner')
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        # 匹配逻辑
        best_col = None
        max_matches = 0
        for col in gdf_lines.columns:
            if gdf_lines[col].dtype == object:
                matches = gdf_lines[col].astype(str).apply(lambda x: any(k in x for k in LINE_COLORS.keys())).sum()
                if matches > max_matches:
                    max_matches = matches
                    best_col = col
        
        if best_col:
            gdf_lines['color'] = gdf_lines[best_col].apply(get_line_color)
        else:
            gdf_lines['color'] = pd.Series([[100, 150, 250, 150]] * len(gdf_lines))
            
        return merged_stations, gdf_lines, best_col
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None, None

df_stations, gdf_lines, line_col_name = load_data()

if df_stations is not None and gdf_lines is not None:
    
    # ==========================================
    # 🕵️ 侦察兵：强制在左侧边栏打印地图里的数据
    # ==========================================
    with st.sidebar:
        st.header("🛠️ 侦察兵面板")
        st.write("👉 你的线路文件长这样：")
        # 把地理数据转成普通表格显示出来
        st.dataframe(pd.DataFrame(gdf_lines.drop(columns=['geometry', 'color'])).head(20))
    # ==========================================

    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    try:
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
        )

        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color="color", 
            get_line_width=25,
            line_width_min_pixels=3,
            pickable=True,
            # 添加悬浮提示，看看鼠标放在线上到底是什么名字
            tooltip={"text": "测试"} 
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
        
        def get_base64_of_bin_file(bin_file):
            try:
                with open(bin_file, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            except:
                return None

        legend_base64 = get_base64_of_bin_file(DATA_DIR / "legend.png") or get_base64_of_bin_file(DATA_DIR / "legend.jpg")
        
        if legend_base64:
            st.markdown(
                f"""
                <style>
                .legend-container {{
                    position: fixed; bottom: 30px; left: 30px; z-index: 99999;
                    background-color: rgba(255, 255, 255, 0.85); padding: 5px;
                    border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    backdrop-filter: blur(5px);
                }}
                .legend-container img {{ max-height: 280px; object-fit: contain; }}
                </style>
                <div class="legend-container"><img src="data:image/png;base64,{legend_base64}"></div>
                """, unsafe_allow_html=True
            )
            
    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

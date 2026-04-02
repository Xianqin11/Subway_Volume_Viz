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
# 🚇 官方线路 RGB 颜色字典 (由你完美提供)
# ==========================================
LINE_COLORS = {
    "1号线": [194, 55, 48],
    "八通线": [194, 55, 48],
    "2号线": [0, 70, 147],
    "3号线": [227, 27, 35],
    "4号线": [0, 172, 163],
    "大兴线": [0, 172, 163],
    "5号线": [166, 33, 127],
    "6号线": [237, 157, 0],
    "7号线": [255, 199, 44],
    "8号线": [0, 158, 78],
    "9号线": [153, 204, 0],
    "10号线": [0, 158, 224],
    "11号线": [237, 121, 107],
    "12号线": [199, 107, 0],
    "13号线": [255, 222, 0],
    "14号线": [209, 139, 131],
    "15号线": [106, 53, 125],
    "16号线": [96, 176, 66],
    "17号线": [0, 171, 171],
    "19号线": [211, 163, 201],
    "房山线": [237, 125, 49],
    "昌平线": [231, 131, 183],
    "亦庄线": [237, 0, 140],
    "燕房线": [237, 125, 49],
    "S1线": [170, 102, 34],
    "西郊线": [227, 27, 35],
    "T1线": [227, 27, 35],
    "首都机场": [153, 136, 166],
    "大兴机场": [0, 70, 147],
}

# 智能上色函数
def get_line_color(line_name):
    if not isinstance(line_name, str):
        return [150, 150, 150, 150] # 默认灰色
    for key, color in LINE_COLORS.items():
        if key in line_name:
            return color + [255] # [R, G, B, Alpha透明度]
    return [150, 150, 150, 150]

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
        
        # 🔮 自动侦察兵：寻找哪一列是线路名称，并自动上色
        best_col = None
        max_matches = 0
        for col in gdf_lines.columns:
            if gdf_lines[col].dtype == object:
                # 计算这列包含了多少个我们字典里的线路名
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

# --- 3. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    st.success(f"🎉 成功拼接了 {len(df_stations)} 个站点！(🤖 侦察兵自动为您匹配了 [{line_col_name}] 列并进行了官方上色)")
    
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    try:
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        # 气泡颜色：大于5万人次显示红色，否则显示绿色
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
        )

        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color="color", # 🌈 这里接入了我们配置的官方颜色
            get_line_width=25,      # 稍微加粗线路让颜色更明显
            line_width_min_pixels=3,
            pickable=True,
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
                    data = f.read()
                return base64.b64encode(data).decode()
            except:
                return None

        # 无论你上传的是 png 还是 jpg，代码都能自动识别
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
                    background-color: rgba(255, 255, 255, 0.85); /* 半透明背景 */
                    padding: 5px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    backdrop-filter: blur(5px); /* 毛玻璃特效 */
                }}
                .legend-container img {{
                    max-height: 280px; /* 限制最高高度，防止遮挡地图 */
                    object-fit: contain;
                }}
                </style>
                <div class="legend-container">
                    <img src="data:image/png;base64,{legend_base64}">
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.info("💡 提示：检测不到图例图片。如果你想在左下角显示图例，请将图片命名为 `legend.png` 或 `legend.jpg` 并放入 data 文件夹。")

    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

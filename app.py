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
# 🚇 安全稳定版：只用字母和汉字匹配
# ==========================================
def get_line_color(line_code):
    if pd.isna(line_code): 
        return [150, 150, 150, 150]
    
    name = str(line_code).strip().upper()
    
    safe_mapping = {
        "M1": [194, 55, 48], "1号": [194, 55, 48], "八通": [194, 55, 48], "一号": [194, 55, 48], "L1": [194, 55, 48],
        "M2": [0, 70, 147], "2号": [0, 70, 147], "二号": [0, 70, 147], "L2": [0, 70, 147],
        "M3": [227, 27, 35], "3号": [227, 27, 35], "三号": [227, 27, 35], "M03": [227, 27, 35], "L3": [227, 27, 35],
        "M4": [0, 172, 163], "4号": [0, 172, 163], "大兴线": [0, 172, 163], "四号": [0, 172, 163], "L4": [0, 172, 163],
        "M5": [166, 33, 127], "5号": [166, 33, 127], "五号": [166, 33, 127], "L5": [166, 33, 127],
        "M6": [237, 157, 0], "6号": [237, 157, 0], "六号": [237, 157, 0], "M06": [237, 157, 0], "L6": [237, 157, 0],
        "M7": [255, 199, 44], "7号": [255, 199, 44], "七号": [255, 199, 44], "L7": [255, 199, 44],
        "M8": [0, 158, 78], "8号": [0, 158, 78], "八号": [0, 158, 78], "L8": [0, 158, 78],
        "M9": [153, 204, 0], "9号": [153, 204, 0], "九号": [153, 204, 0], "L9": [153, 204, 0],
        "M10": [0, 158, 224], "10号": [0, 158, 224], "十号": [0, 158, 224], "L10": [0, 158, 224],
        "M11": [237, 121, 107], "11号": [237, 121, 107], "十一号": [237, 121, 107], "L11": [237, 121, 107],
        "M12": [199, 107, 0], "12号": [199, 107, 0], "十二号": [199, 107, 0], "M012": [199, 107, 0], "L12": [199, 107, 0],
        "M13": [255, 222, 0], "13号": [255, 222, 0], "十三号": [255, 222, 0], "L13": [255, 222, 0],
        "M14": [209, 139, 131], "14号": [209, 139, 131], "十四号": [209, 139, 131], "L14": [209, 139, 131],
        "M15": [106, 53, 125], "15号": [106, 53, 125], "十五号": [106, 53, 125], "L15": [106, 53, 125],
        "M16": [96, 176, 66], "16号": [96, 176, 66], "十六号": [96, 176, 66], "M016": [96, 176, 66], "L16": [96, 176, 66],
        "M17": [0, 171, 171], "17号": [0, 171, 171], "十七号": [0, 171, 171], "L17": [0, 171, 171],
        "M19": [211, 163, 201], "19号": [211, 163, 201], "十九号": [211, 163, 201], "M019": [211, 163, 201], "L19": [211, 163, 201],
        "FS": [237, 125, 49], "房山": [237, 125, 49], "燕房": [237, 125, 49],
        "CP": [231, 131, 183], "昌平": [231, 131, 183],
        "YZ": [237, 0, 140], "亦庄": [237, 0, 140],
        "S1": [170, 102, 34], "XJ": [227, 27, 35], "西郊": [227, 27, 35],
        "YZT1": [227, 27, 35], "T1": [227, 27, 35],
        "JC": [153, 136, 166], "首都机场": [153, 136, 166], "机场线": [153, 136, 166],
        "DXJC": [0, 70, 147], "大兴机场": [0, 70, 147], "新机场": [0, 70, 147]
    }
        
    for key in sorted(safe_mapping.keys(), key=len, reverse=True):
        if key in name:
            return safe_mapping[key] + [255]
            
    return [150, 150, 150, 150]

# --- 2. 注入全局 CSS：严格恢复到 60vh (3/5) ---
st.markdown(
    """
    <style>
    [data-testid="stDeckGlJsonChart"] { height: 60vh !important; }
    [data-testid="StyledFullScreenButton"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 3. 数据加载引擎 ---
@st.cache_data(show_spinner="正在云端加载空间数据，请稍候...")
def load_data():
    try:
        df_flow = pd.read_excel(DATA_DIR / "flow_static.xlsx")
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        merged_stations = gdf_stations.merge(df_flow, left_on='站点', right_on='stations', how='inner')
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        best_col = None
        for col in gdf_lines.columns:
            if col == 'geometry': continue
            test_colors = gdf_lines[col].apply(get_line_color)
            if test_colors.apply(lambda c: c != [150, 150, 150, 150]).any():
                best_col = col
                gdf_lines['color'] = test_colors
                break
                
        if not best_col:
            gdf_lines['color'] = pd.Series([[100, 100, 100, 200]] * len(gdf_lines))
            
        return merged_stations, gdf_lines
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None

df_stations, gdf_lines = load_data()

# --- 4. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    try:
        df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
        df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
        
        df_stations['color'] = df_stations[SAFE_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
        )
        
        # 💥 降维打击：在送入地图前，提前用 Python 把带中文的提示文本拼装好！彻底避开乱码！
        df_stations['tooltip_text'] = "<b>站点：</b>" + df_stations['stations'].astype(str) + "<br/><b>进站量：</b>" + df_stations[SAFE_COL].astype(str) + " 人次"

        layer_lines = pdk.Layer(
            "GeoJsonLayer",
            gdf_lines,
            get_line_color="color", 
            get_line_width=25,      
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

        view_state = pdk.ViewState(latitude=39.92, longitude=116.40, zoom=9.5, pitch=0, bearing=0)

        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            # 引擎只需要无脑提取刚刚拼好的这一列就行了
            tooltip={
                "html": "{tooltip_text}"
            }
        ))
        
        def get_base64_of_bin_file(bin_file):
            try:
                with open(bin_file, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            except:
                return None

        legend_base64 = get_base64_of_bin_file(DATA_DIR / "legend.png") or get_base64_of_bin_file(DATA_DIR / "legend.jpg")
        
        ui_html = """
        <style>
        .custom-toolbar {
            position: fixed; top: 180px; left: 40px; z-index: 99999;
            display: flex; flex-direction: column; gap: 12px;
        }
        .tool-btn {
            background-color: rgba(255, 255, 255, 0.9); border: 1px solid #ccc;
            border-radius: 6px; width: 45px; height: 45px; display: flex;
            justify-content: center; align-items: center; font-size: 24px;
            cursor: default; box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            transition: all 0.2s; color: #333; position: relative;
        }
        .tool-btn:hover { background-color: #f5f5f5; transform: scale(1.05); }
        .mouse-tooltip {
            visibility: hidden; position: absolute; left: 60px; top: 0;
            background-color: rgba(255, 255, 255, 0.95); color: #333;
            padding: 15px 20px; border-radius: 8px; width: 280px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2); opacity: 0;
            transition: opacity 0.3s; font-size: 14px; line-height: 1.8;
            border: 1px solid #ddd; pointer-events: none;
        }
        .tool-btn:hover .mouse-tooltip { visibility: visible; opacity: 1; }
        </style>
        
        <div class="custom-toolbar">
            <div class="tool-btn">🖱️
                <div class="mouse-tooltip">
                    <b style="font-size: 16px;">🖱️ 地图交互说明</b><hr style="margin: 8px 0;">
                    <span style="color:#d32f2f;">●</span> <b>左键按住拖动</b>：平移地图<br>
                    <span style="color:#1976d2;">●</span> <b>鼠标滚轮滚动</b>：放大 / 缩小<br>
                    <span style="color:#388e3c;">●</span> <b>右键按住拖动</b>：3D旋转 / 倾斜<br>
                    <span style="color:#f57c00;">●</span> <b>左键点击气泡</b>：查看站点详情
                </div>
            </div>
        </div>
        """

        if legend_base64:
            ui_html += f"""
            <style>
            .legend-container {{
                position: fixed; bottom: 40px; right: 40px; z-index: 99999;
                background-color: rgba(255, 255, 255, 0.85); padding: 10px;
                border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                backdrop-filter: blur(8px); pointer-events: none;
            }}
            .legend-container img {{ max-height: 280px; object-fit: contain; }}
            </style>
            <div class="legend-container"><img src="data:image/png;base64,{legend_base64}"></div>
            """

        st.markdown(ui_html, unsafe_allow_html=True)

    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from pathlib import Path
import base64

# --- 1. 页面基本设置 ---
st.set_page_config(layout="wide", page_title="轨道站点客流可视化", page_icon="🚇")

# ==========================================
# 🚇 双语全覆盖：工程代号 + 中文名 RGB 映射表
# ==========================================
def get_line_color(line_code):
    if pd.isna(line_code): 
        return [150, 150, 150, 150]
    
    name = str(line_code).strip().upper()
    
    exact_mapping = {
        "M1": [194, 55, 48], "1号线": [194, 55, 48], "八通线": [194, 55, 48],
        "M2": [0, 70, 147], "2号线": [0, 70, 147],
        "M3": [227, 27, 35], "3号线": [227, 27, 35],
        "M4": [0, 172, 163], "4号线": [0, 172, 163], "大兴线": [0, 172, 163],
        "M5": [166, 33, 127], "5号线": [166, 33, 127],
        "M6": [237, 157, 0], "6号线": [237, 157, 0],
        "M7": [255, 199, 44], "7号线": [255, 199, 44],
        "M8": [0, 158, 78], "8号线": [0, 158, 78],
        "M9": [153, 204, 0], "9号线": [153, 204, 0],
        "M10": [0, 158, 224], "10号线": [0, 158, 224],
        "M11": [237, 121, 107], "11号线": [237, 121, 107],
        "M12": [199, 107, 0], "12号线": [199, 107, 0],
        "M13": [255, 222, 0], "13号线": [255, 222, 0],
        "M14": [209, 139, 131], "14号线": [209, 139, 131],
        "M15": [106, 53, 125], "15号线": [106, 53, 125],
        "M16": [96, 176, 66], "16号线": [96, 176, 66],
        "M17": [0, 171, 171], "17号线": [0, 171, 171],
        "M19": [211, 163, 201], "19号线": [211, 163, 201],
        "FS": [237, 125, 49], "房山线": [237, 125, 49], "燕房线": [237, 125, 49],
        "CP": [231, 131, 183], "昌平线": [231, 131, 183],
        "YZ": [237, 0, 140], "亦庄线": [237, 0, 140],
        "S1": [170, 102, 34], "S1线": [170, 102, 34],
        "XJ": [227, 27, 35], "西郊线": [227, 27, 35],
        "YZT1": [227, 27, 35], "T1线": [227, 27, 35],
        "JC": [153, 136, 166], "首都机场": [153, 136, 166], "机场线": [153, 136, 166],
        "DXJC": [0, 70, 147], "大兴机场": [0, 70, 147], "新机场": [0, 70, 147]
    }
    
    if name in exact_mapping:
        return exact_mapping[name] + [255]
        
    for key in sorted(exact_mapping.keys(), key=len, reverse=True):
        if key in name:
            return exact_mapping[key] + [255]
            
    return [150, 150, 150, 150]

# --- 2. 注入全局 CSS ---
st.markdown(
    """
    <style>
    [data-testid="stDeckGlJsonChart"] { height: 70vh !important; }
    [data-testid="StyledFullScreenButton"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

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
            
        return merged_stations, gdf_lines, best_col
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None, None

df_stations, gdf_lines, line_name_col = load_data()

# --- 4. 核心渲染与交互逻辑 ---
if df_stations is not None and gdf_lines is not None:
    
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
    df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
    
    def combine_lines(row):
        lines = []
        for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
            if col in row and pd.notna(row[col]):
                val = str(row[col]).strip()
                if val and val.lower() != 'nan':
                    lines.append(val)
        return "、".join(lines) if lines else "未知线路"

    df_stations['所属线路'] = df_stations.apply(combine_lines, axis=1)
    df_stations['区县'] = df_stations['区县'].fillna('未知区县')
    
    # ==========================================
    # 🎛️ 左侧边栏：交互控制台
    # ==========================================
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Beijing_Subway_logo.svg/200px-Beijing_Subway_logo.svg.png", width=60)
        st.header("🎛️ 数据筛选控制台")
        st.markdown("---")
        
        # 自动从表格里收集所有的线路名称
        all_station_lines = set()
        for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
            if col in df_stations.columns:
                for val in df_stations[col].dropna().astype(str):
                    if val and val.lower() != 'nan' and '未知' not in val:
                        all_station_lines.add(val.strip())
        
        # 渲染多选框
        selected_lines = st.multiselect(
            "🚇 按路线筛选客流 (可多选)", 
            options=sorted(list(all_station_lines)),
            default=[],
            help="选择你要查看的线路。不选则默认显示全网数据。"
        )

    # ==========================================
    # 🔍 数据过滤与聚光灯特效
    # ==========================================
    if selected_lines:
        # 1. 过滤站点：只要这个站所属的线路里包含选中的线路，就把它保留下来
        mask = pd.Series(False, index=df_stations.index)
        for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
            if col in df_stations.columns:
                mask = mask | df_stations[col].isin(selected_lines)
        filtered_stations = df_stations[mask].copy()
        
        # 2. 聚光灯特效：把没有被选中的轨道路线变成淡淡的灰色背景
        def is_line_selected(code):
            name = str(code).strip().upper()
            for sl in selected_lines:
                sl_clean = sl.replace("线", "")
                if sl_clean in name or sl in name: return True
                if name.startswith("M") and name[1:] == sl_clean: return True
            return False
            
        if line_name_col:
            gdf_lines['color'] = gdf_lines.apply(
                lambda row: row['color'] if is_line_selected(row[line_name_col]) else [200, 200, 200, 50], 
                axis=1
            )
    else:
        # 如果什么都没选，就显示全部
        filtered_stations = df_stations.copy()

    # 动态计算气泡颜色
    filtered_stations['color'] = filtered_stations[SAFE_COL].apply(
        lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
    )

    st.title("🚇 轨道站点客流与线路可视化")
    
    # 图层渲染
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
        filtered_stations, # 这里使用了过滤后的气泡数据
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
        tooltip={
            "html": "<b>📍 站点:</b> {stations} <br/> <b>🏙️ 区县:</b> {区县} <br/> <b>🚇 线路:</b> {所属线路} <br/> <b>🚶 进站量:</b> {volume} 人次"
        }
    ))
    
    # 🖼️ 左下角图例
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
                position: fixed;
                bottom: 40px;
                left: 40px; 
                z-index: 99999;
                background-color: rgba(255, 255, 255, 0.85);
                padding: 8px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                backdrop-filter: blur(5px);
                pointer-events: none;
            }}
            .legend-container img {{
                max-height: 280px; 
                object-fit: contain;
            }}
            </style>
            <div class="legend-container">
                <img src="data:image/png;base64,{legend_base64}">
            </div>
            """,
            unsafe_allow_html=True
        )

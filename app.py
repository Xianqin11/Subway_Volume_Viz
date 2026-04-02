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
    if pd.isna(line_code): 
        return [150, 150, 150, 150] # 默认灰色
    
    name = str(line_code).strip().upper()
    
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
    
    if name in exact_mapping:
        return exact_mapping[name] + [255]
        
    for key in sorted(exact_mapping.keys(), key=len, reverse=True):
        if key in name:
            return exact_mapping[key] + [255]
            
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
        
        # 💥 智能盲找黑科技：不管列名叫啥，直接搜数据！
        best_col = None
        for col in gdf_lines.columns:
            if col == 'geometry': continue
            
            # 让每一列都去试一下能不能找到颜色
            test_colors = gdf_lines[col].apply(get_line_color)
            
            # 只要有一列成功匹配上颜色（而不是全是灰色），就是找对列了！
            if test_colors.apply(lambda c: c != [150, 150, 150, 150]).any():
                best_col = col
                gdf_lines['color'] = test_colors
                break
                
        if best_col:
            gdf_lines['display_name'] = gdf_lines[best_col].astype(str)
        else:
            # 万一连盲找都失败了（说明文件里根本没有 M1 这种字眼），就给深灰色报错
            gdf_lines['color'] = pd.Series([[100, 100, 100, 200]] * len(gdf_lines))
            gdf_lines['display_name'] = "无法识别代号"
            
        return merged_stations, gdf_lines, best_col
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None, None

df_stations, gdf_lines, found_line_col = load_data()

# --- 3. 地图渲染引擎 ---
if df_stations is not None and gdf_lines is not None:
    
    # 在网页最上方播报侦察结果
    if found_line_col:
        st.success(f"🎉 大获全胜！智能算法在地图的 [{found_line_col}] 列中精准找到了 M1、M2 等代号，并已全面涂装！")
    else:
        st.warning("⚠️ 破案失败：算法翻遍了所有数据，也没找到 M1、M2 等代号，最后只能全部涂成灰色。")

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
            tooltip={
                "html": "<b>站点:</b> {stations} <br/> <b>代号:</b> {display_name} <br/> <b>数据:</b> {volume}"
            }
        ))
        
        # 左下角图例模块
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
                    background-color: rgba(255, 255, 255, 0.85); padding: 8px;
                    border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    backdrop-filter: blur(5px);
                }}
                .legend-container img {{ max-height: 350px; object-fit: contain; }}
                </style>
                <div class="legend-container"><img src="data:image/png;base64,{legend_base64}"></div>
                """, unsafe_allow_html=True
            )

    except KeyError:
        st.error(f"🚨 找不到名为 '{ORIGINAL_COL}' 的列！")

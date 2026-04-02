import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from pathlib import Path
import base64

# --- 优雅导入高级图表库 ---
try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# --- 1. 页面基本设置 ---
st.set_page_config(layout="wide", page_title="轨道站点客流可视化", page_icon="🚇")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# ==========================================
# 🚇 史诗级全覆盖：RGB 映射表
# ==========================================
def get_line_color(line_code):
    if pd.isna(line_code): return [150, 150, 150, 150]
    name = str(line_code).strip().upper()
    exact_mapping = {
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
    for key in sorted(exact_mapping.keys(), key=len, reverse=True):
        if key in name: return exact_mapping[key] + [255]
    return [150, 150, 150, 150]

# --- 2. 注入全局 CSS 强制放大地图 ---
st.markdown(
    """
    <style>
    [data-testid="stDeckGlJsonChart"] { height: 60vh !important; } 
    [data-testid="StyledFullScreenButton"] { display: none; }
    /* 美化文件上传框 */
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #009EE0; background-color: #f0f8ff; }
    </style>
    """, 
    unsafe_allow_html=True
)

# --- 3. 核心加载引擎：支持外部文件接入 ---
@st.cache_data(show_spinner="正在解析空间与客流数据，请稍候...")
def load_all_data(excel_file_path_or_buffer):
    try:
        # 支持读取上传的内存文件或本地路径
        df_flow = pd.read_excel(excel_file_path_or_buffer)
        gdf_stations = gpd.read_file(DATA_DIR / "现状423座车站.shp", encoding='utf-8').to_crs(epsg=4326)
        gdf_lines = gpd.read_file(DATA_DIR / "2025年底-线路909km-现状.shp", encoding='utf-8').to_crs(epsg=4326)
        
        # 将站名转为字符串以便匹配
        df_flow['stations'] = df_flow['stations'].astype(str).str.strip()
        gdf_stations['站点'] = gdf_stations['站点'].astype(str).str.strip()
        
        merged_stations = gdf_stations.merge(df_flow, left_on='站点', right_on='stations', how='inner')
        merged_stations['lon'] = merged_stations.geometry.x
        merged_stations['lat'] = merged_stations.geometry.y
        
        best_col = None
        for col in gdf_lines.columns:
            if col == 'geometry': continue
            test_colors = gdf_lines[col].apply(get_line_color)
            if test_colors.apply(lambda c: c != [150, 150, 150, 150]).any():
                best_col = col
                break
        return merged_stations, gdf_lines, best_col
    except Exception as e:
        st.error(f"🚨 数据合并出错啦，请检查上传的 Excel 是否包含 'stations' 列！详细报错: {e}")
        return None, None, None


# ==========================================
# 🎛️ 左侧边栏：文件上传与交互控制台
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Beijing_Subway_logo.svg/200px-Beijing_Subway_logo.svg.png", width=60)
    
    st.header("📂 1. 更新数据源")
    # 允许用户上传新文件
    uploaded_file = st.file_uploader("上传最新客流数据 (Excel格式)", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        st.success(f"✅ 成功加载外部数据: {uploaded_file.name}")
        data_source = uploaded_file
    else:
        st.info("💡 当前正在使用系统内置的历史数据。可随时上传新 Excel 替换。")
        data_source = DATA_DIR / "flow_static.xlsx"
        
    st.markdown("---")
    st.header("🎛️ 2. 空间数据过滤")

# --- 拦截数据流，开始渲染 ---
df_stations, gdf_lines_cached, line_name_col = load_all_data(data_source)

if df_stations is not None and gdf_lines_cached is not None:
    
    # 💥 AI 智能表头嗅探器：不再写死列名，自动寻找客流量列！
    SAFE_COL = 'volume'
    target_flow_col = None
    
    # 遍历所有列，找包含“全日进站”或者“进站”的列
    for col in df_stations.columns:
        if "全日进站" in col or ("进站" in col and "万人次" in col) or col == '2025年2月25日工作日全日进站（万人次）':
            target_flow_col = col
            break
            
    if not target_flow_col:
        st.error("🚨 在上传的数据表中，没有找到包含『全日进站』字眼的客流量列！请检查表头。")
        st.stop()
        
    # 重命名为安全列名，方便后续处理
    df_stations = df_stations.rename(columns={target_flow_col: SAFE_COL})
    df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
    
    def combine_lines(row):
        lines = [str(row[col]).strip() for col in ['轨道线路1', '轨道线路2', '轨道线路3'] if col in row and pd.notna(row[col])]
        lines = [val for val in lines if val and val.lower() != 'nan']
        return "、".join(lines) if lines else "未知线路"

    df_stations['所属线路'] = df_stations.apply(combine_lines, axis=1)
    # 处理区县如果不存在或缺失的情况
    if '区县' not in df_stations.columns:
        df_stations['区县'] = '未知区县'
    else:
        df_stations['区县'] = df_stations['区县'].fillna('未知区县')
    
    # --- 侧边栏联动筛选逻辑 ---
    with st.sidebar:
        all_station_lines = set()
        for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
            if col in df_stations.columns:
                for val in df_stations[col].dropna().astype(str):
                    if val and val.lower() != 'nan' and '未知' not in val:
                        all_station_lines.add(val.strip())
        
        selected_lines = st.multiselect("🚇 按路线筛选", options=sorted(list(all_station_lines)), default=[])

        if selected_lines:
            mask_for_stations = pd.Series(False, index=df_stations.index)
            for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
                if col in df_stations.columns:
                    mask_for_stations = mask_for_stations | df_stations[col].isin(selected_lines)
            available_stations = df_stations[mask_for_stations]['stations'].dropna().unique().tolist()
        else:
            available_stations = df_stations['stations'].dropna().unique().tolist()
            
        selected_stations = st.multiselect(
            "📍 按站点筛选 (支持多选)", 
            options=sorted(available_stations), 
            default=[],
            help="先选上方线路缩小范围，再在此精确选站。"
        )

        # ------------------------------------------
        # 🧠 智能数据分析引擎
        # ------------------------------------------
        st.markdown("---")
        st.header("🧠 3. 智能数据报告")
        
        final_mask = pd.Series(True, index=df_stations.index)
        is_filtered = False
        
        if selected_lines:
            line_mask = pd.Series(False, index=df_stations.index)
            for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
                if col in df_stations.columns:
                    line_mask = line_mask | df_stations[col].isin(selected_lines)
            final_mask = final_mask & line_mask
            is_filtered = True
            
        if selected_stations:
            station_mask = df_stations['stations'].isin(selected_stations)
            final_mask = final_mask & station_mask
            is_filtered = True

        ana_df = df_stations[final_mask] if is_filtered else df_stations
            
        if not ana_df.empty:
            total_vol = ana_df[SAFE_COL].sum()
            max_row = ana_df.loc[ana_df[SAFE_COL].idxmax()]
            
            col1, col2 = st.columns(2)
            col1.metric("总进站量", f"{total_vol:,.0f}")
            col2.metric("最高峰站点", f"{max_row['stations']}")
            
            # 使用动态探测出来的原列名，展示给用户看，更显得专业
            st.info(f"💡 **AI 数据总结**：\n共检索到 **{len(ana_df)}** 个站点。\n分析字段：*{target_flow_col}*。\n客流极值出现在【{max_row['区县']}】的 **{max_row['stations']}** 站，单日进站 **{max_row[SAFE_COL]:,.0f}** 人次。")
            
            if HAS_PLOTLY:
                chart_style = st.selectbox("🎨 图表样式切换", ["📊 柱状图", "🍩 圈状图", "🥧 饼状图", "🕸️ 雷达图"])
                
                top_n = min(10, len(ana_df))
                top_df = ana_df.nlargest(top_n, SAFE_COL).sort_values(by=SAFE_COL, ascending=True).copy()
                district_df = ana_df.groupby('区县')[SAFE_COL].sum().reset_index()

                def render_chart(df, name_col, value_col, title, color_theme):
                    if chart_style == "📊 柱状图":
                        fig = px.bar(df, x=value_col, y=name_col, orientation='h', title=title, color_discrete_sequence=[color_theme])
                    elif chart_style == "🍩 圈状图":
                        fig = px.pie(df, names=name_col, values=value_col, hole=0.5, title=title)
                    elif chart_style == "🥧 饼状图":
                        fig = px.pie(df, names=name_col, values=value_col, title=title)
                    elif chart_style == "🕸️ 雷达图":
                        fig = px.line_polar(df, r=value_col, theta=name_col, line_close=True, title=title)
                        fig.update_traces(fill='toself', line_color=color_theme)
                    
                    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title_font_size=14)
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                render_chart(top_df, 'stations', SAFE_COL, f"📈 客流 TOP {top_n} 站点", "#ff4b4b")
                render_chart(district_df, '区县', SAFE_COL, "🏙️ 区县分布热度", "#009EE0")
            else:
                st.warning("正在等待图表库加载...")
                st.bar_chart(ana_df.nlargest(10, SAFE_COL)[['stations', SAFE_COL]].set_index('stations'), color="#ff4b4b")

        else:
            st.warning("所选范围内暂无数据。")

    # ==========================================
    # 🔍 空间关联渲染
    # ==========================================
    render_lines = gdf_lines_cached.copy()

    def is_line_selected(shp_code, sel_lines):
        if pd.isna(shp_code): return False
        name = str(shp_code).strip().upper()
        for sl in sel_lines:
            sl_upper = str(sl).strip().upper()
            if name == sl_upper or name in sl_upper or sl_upper in name: return True
            sl_num = sl_upper.replace("号线", "").replace("线", "")
            name_num = name.replace("M0", "").replace("M", "").replace("L", "").replace("号线", "").replace("线", "")
            if sl_num.isdigit() and name_num.isdigit() and sl_num == name_num: return True
            if "房山" in sl_upper and name == "FS": return True
            if "燕房" in sl_upper and name == "FS": return True
            if "昌平" in sl_upper and name == "CP": return True
            if "亦庄" in sl_upper and name == "YZ": return True
            if "S1" in sl_upper and name == "S1": return True
            if "西郊" in sl_upper and name == "XJ": return True
            if "T1" in sl_upper and name == "YZT1": return True
            if "首都机场" in sl_upper and name == "JC": return True
            if ("大兴机场" in sl_upper or "新机场" in sl_upper) and name == "DXJC": return True
            if "八通" in sl_upper and name == "M1": return True
            if "大兴线" in sl_upper and name == "M4": return True
        return False

    if selected_lines and line_name_col:
        render_lines['color'] = render_lines[line_name_col].apply(
            lambda x: get_line_color(x) if is_line_selected(x, selected_lines) else [200, 200, 200, 50]
        )
    else:
        render_lines['color'] = render_lines[line_name_col].apply(get_line_color) if line_name_col else pd.Series([[100, 100, 100, 200]] * len(render_lines))

    filtered_stations = ana_df.copy() 
    filtered_stations['color'] = filtered_stations[SAFE_COL].apply(
        lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
    )

    st.title("🚇 轨道站点客流与空间分析引擎")
    
    layer_lines = pdk.Layer("GeoJsonLayer", render_lines, get_line_color="color", get_line_width=25, line_width_min_pixels=3, pickable=True)
    layer_stations = pdk.Layer("ScatterplotLayer", filtered_stations, get_position=["lon", "lat"], get_color="color", get_radius=SAFE_COL, radius_scale=0.02, radius_min_pixels=3, pickable=True)
    view_state = pdk.ViewState(latitude=39.92, longitude=116.40, zoom=9.5, pitch=0, bearing=0)

    st.pydeck_chart(pdk.Deck(
        layers=[layer_lines, layer_stations], initial_view_state=view_state, map_style="light", 
        tooltip={"html": "<b>📍 站点:</b> {stations} <br/> <b>🏙️ 区县:</b> {区县} <br/> <b>🚇 线路:</b> {所属线路} <br/> <b>🚶 客流量:</b> {volume} 人次"}
    ))
    
    def get_base64_of_bin_file(bin_file):
        try:
            with open(bin_file, 'rb') as f: return base64.b64encode(f.read()).decode()
        except: return None
    legend_base64 = get_base64_of_bin_file(DATA_DIR / "legend.png") or get_base64_of_bin_file(DATA_DIR / "legend.jpg")
    if legend_base64:
        st.markdown(
            f"""<style>.legend-container {{ position: fixed; bottom: 40px; left: 40px; z-index: 99999; background-color: rgba(255, 255, 255, 0.85); padding: 8px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); backdrop-filter: blur(5px); pointer-events: none; }} .legend-container img {{ max-height: 280px; object-fit: contain; }} </style> <div class="legend-container"> <img src="data:image/png;base64,{legend_base64}"> </div>""",
            unsafe_allow_html=True
        )


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

# --- 2. 注入全局 CSS 强制放大地图 (60vh 黄金比例) ---
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
                break
        return merged_stations, gdf_lines, best_col
    except Exception as e:
        st.error(f"数据加载出错啦: {e}")
        return None, None, None

df_stations, gdf_lines_cached, line_name_col = load_data()

# --- 4. 核心渲染与分析逻辑 ---
if df_stations is not None and gdf_lines_cached is not None:
    ORIGINAL_COL = '2025年2月25日工作日全日进站（万人次）'
    SAFE_COL = 'volume'
    
    df_stations = df_stations.rename(columns={ORIGINAL_COL: SAFE_COL})
    df_stations[SAFE_COL] = pd.to_numeric(df_stations[SAFE_COL], errors='coerce').fillna(0)
    
    def combine_lines(row):
        lines = [str(row[col]).strip() for col in ['轨道线路1', '轨道线路2', '轨道线路3'] if col in row and pd.notna(row[col])]
        lines = [val for val in lines if val and val.lower() != 'nan']
        return "、".join(lines) if lines else "未知线路"

    df_stations['所属线路'] = df_stations.apply(combine_lines, axis=1)
    df_stations['区县'] = df_stations['区县'].fillna('未知区县')
    
    # ==========================================
    # 🎛️ 左侧边栏：交互控制台 + 级联筛选
    # ==========================================
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Beijing_Subway_logo.svg/200px-Beijing_Subway_logo.svg.png", width=60)
        st.header("🎛️ 数据筛选控制台")
        
        # --- 获取全部线路列表 ---
        all_station_lines = set()
        for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
            if col in df_stations.columns:
                for val in df_stations[col].dropna().astype(str):
                    if val and val.lower() != 'nan' and '未知' not in val:
                        all_station_lines.add(val.strip())
        
        # 1. 线路多选框
        selected_lines = st.multiselect("🚇 按路线筛选", options=sorted(list(all_station_lines)), default=[])

        # --- 💥 核心黑科技：动态提取可用站点 ---
        # 如果选了线路，就只把这些线路上的站点提取出来；如果没选线路，就提取所有站点。
        if selected_lines:
            mask_for_stations = pd.Series(False, index=df_stations.index)
            for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
                if col in df_stations.columns:
                    mask_for_stations = mask_for_stations | df_stations[col].isin(selected_lines)
            available_stations = df_stations[mask_for_stations]['stations'].dropna().unique().tolist()
        else:
            available_stations = df_stations['stations'].dropna().unique().tolist()
            
        # 2. 站点多选框 (随线路动态更新！)
        selected_stations = st.multiselect(
            "📍 按站点筛选 (支持多选)", 
            options=sorted(available_stations), 
            default=[],
            help="你可以先在上面选择线路缩小范围，然后在这里选择具体的站点。"
        )

        # ------------------------------------------
        # 🧠 智能数据分析引擎
        # ------------------------------------------
        st.markdown("---")
        st.header("🧠 智能数据分析")
        
        # === 综合筛选逻辑 ===
        # 建立一个全为 True 的初始过滤网
        final_mask = pd.Series(True, index=df_stations.index)
        is_filtered = False
        
        # 过滤线路
        if selected_lines:
            line_mask = pd.Series(False, index=df_stations.index)
            for col in ['轨道线路1', '轨道线路2', '轨道线路3']:
                if col in df_stations.columns:
                    line_mask = line_mask | df_stations[col].isin(selected_lines)
            final_mask = final_mask & line_mask
            is_filtered = True
            
        # 过滤站点
        if selected_stations:
            station_mask = df_stations['stations'].isin(selected_stations)
            final_mask = final_mask & station_mask
            is_filtered = True

        # 生成最终被选中的数据
        ana_df = df_stations[final_mask] if is_filtered else df_stations
            
        if not ana_df.empty:
            total_vol = ana_df[SAFE_COL].sum()
            max_row = ana_df.loc[ana_df[SAFE_COL].idxmax()]
            
            col1, col2 = st.columns(2)
            col1.metric("总进站量", f"{total_vol:,.0f}")
            col2.metric("最挤站点", f"{max_row['stations']}")
            
            st.info(f"💡 **数据洞察**：\n当前共展示 **{len(ana_df)}** 个站点。客流最高峰出现在【{max_row['区县']}】的 **{max_row['stations']}** 站，单日进站量达到 **{max_row[SAFE_COL]:,.0f}** 人次。")
            
            # 🎨 百变高级图表
            if HAS_PLOTLY:
                chart_style = st.selectbox("🎨 图表样式切换", ["📊 柱状图", "🍩 圈状图", "🥧 饼状图", "🕸️ 雷达图"])
                
                # 如果选中的站少于10个，就显示实际数量，否则显示TOP10
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
                    
                    fig.update_layout(
                        margin=dict(l=10, r=10, t=40, b=10), 
                        paper_bgcolor="rgba(0,0,0,0)", 
                        plot_bgcolor="rgba(0,0,0,0)",
                        title_font_size=14
                    )
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                render_chart(top_df, 'stations', SAFE_COL, f"📈 客流 TOP {top_n} 站点", "#ff4b4b")
                render_chart(district_df, '区县', SAFE_COL, "🏙️ 区县分布热度", "#009EE0")

            else:
                st.warning("🚀 正在等待服务器部署 plotly 高级图表库...")
                st.info("💡 提示：如果您刚刚在 requirements.txt 中添加了 plotly，请耐心等待1-2分钟后刷新网页。")
                st.bar_chart(ana_df.nlargest(10, SAFE_COL)[['stations', SAFE_COL]].set_index('stations'), color="#ff4b4b")

        else:
            st.warning("所选线路暂无数据。")

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

    # 地图线条颜色：根据线路筛选而定
    if selected_lines and line_name_col:
        render_lines['color'] = render_lines[line_name_col].apply(
            lambda x: get_line_color(x) if is_line_selected(x, selected_lines) else [200, 200, 200, 50]
        )
    else:
        render_lines['color'] = render_lines[line_name_col].apply(get_line_color) if line_name_col else pd.Series([[100, 100, 100, 200]] * len(render_lines))

    # 气泡渲染：使用我们刚才双重过滤后的 ana_df
    filtered_stations = ana_df.copy() 
    filtered_stations['color'] = filtered_stations[SAFE_COL].apply(
        lambda x: [255, 50, 50, 200] if x > 50000 else [50, 200, 50, 200]
    )

    st.title("🚇 轨道站点客流与线路可视化")
    
    layer_lines = pdk.Layer("GeoJsonLayer", render_lines, get_line_color="color", get_line_width=25, line_width_min_pixels=3, pickable=True)
    layer_stations = pdk.Layer("ScatterplotLayer", filtered_stations, get_position=["lon", "lat"], get_color="color", get_radius=SAFE_COL, radius_scale=0.02, radius_min_pixels=3, pickable=True)
    
    # 智能视角缩放：如果只选了一个站，可以自动聚焦过去，如果不选就看全图
    view_state = pdk.ViewState(latitude=39.92, longitude=116.40, zoom=9.5, pitch=0, bearing=0)

    st.pydeck_chart(pdk.Deck(
        layers=[layer_lines, layer_stations], initial_view_state=view_state, map_style="light", 
        tooltip={"html": "<b>📍 站点:</b> {stations} <br/> <b>🏙️ 区县:</b> {区县} <br/> <b>🚇 线路:</b> {所属线路} <br/> <b>🚶 进站量:</b> {volume} 人次"}
    ))
    
    # 🖼️ 左下角图例固定
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

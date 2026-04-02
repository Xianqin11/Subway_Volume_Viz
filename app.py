# 💥 终极侦察兵：看看我们成功匹配了多少个站
    st.success(f"🎉 成功拼接了 {len(df_stations)} 个站点的数据！")
    
    # 【完美对上暗号】
    VOLUME_COL = '2025年2月25日工作日全日进站（万人次）'
    
    try:
        # 强行把客流数据转为数字
        df_stations[VOLUME_COL] = pd.to_numeric(df_stations[VOLUME_COL], errors='coerce').fillna(0)
        
        # 动态颜色：因为单位是“万人次”，我们设定客流大于 5（即5万人次）变红，否则为绿色
        df_stations['color'] = df_stations[VOLUME_COL].apply(
            lambda x: [255, 50, 50, 200] if x > 5 else [50, 200, 50, 200]
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
            radius_scale=200,  # 放大气泡，让“万人次”的微小数字能在地图上清晰可见
            radius_min_pixels=3,
            pickable=True,
        )

        view_state = pdk.ViewState(latitude=39.9, longitude=116.4, zoom=10, pitch=40)

        st.pydeck_chart(pdk.Deck(
            layers=[layer_lines, layer_stations],
            initial_view_state=view_state,
            map_style="light", 
            tooltip={"html": f"<b>{{stations}}</b><br/>进站量: {{{VOLUME_COL}}} 万人次"}
        ))
        
    except KeyError:
        st.error(f"🚨 找不到名为 '{VOLUME_COL}' 的列！")

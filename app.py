import streamlit as st
import sqlite3
import pandas as pd
import math
import json
import plotly.graph_objects as go
from datetime import datetime, timedelta

from static_data import (
    fish_data,
    crops_data,
    store_data,
    recipe_raw_data,
    generic_seafood_prices,
    forage_sell_prices,
    growth_mins,
    store_alias,  # <-- 추가!
    sub_recipe_map,  # <-- 추가!
)
from database import get_connection, init_db
from utils import get_kst_now, get_kst_date, calculate_wilson_ci

# ==========================================
# [LLM SYSTEM MEMO / AI 참조용 메모]
# 1. 요리 단가 및 효율 계산 시, 과일 채집 탭에서 측정된 '사과(Apple)'의 분당 획득 효율을
#    '귤(Mandarin)'의 채집 효율과 완전히 동일하게 취급하여 계산할 것.
# ==========================================


# --- 데이터베이스 초기화 및 연결 ---
DB_NAME = "duduta_experiment.db"


init_db()


def get_fishes_for_location(location, weather_selection):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT fish_name, location_category, weather_req, time_req, shadow_size FROM fish_reference"
    )
    all_fish = c.fetchall()
    conn.close()

    weather_emoji = ""
    if "맑음" in weather_selection:
        weather_emoji = "☀️"
    elif "비" in weather_selection:
        weather_emoji = "🌧️"
    elif "무지개" in weather_selection:
        weather_emoji = "🌈"

    available = []
    for f_name, loc_cat, w_req, t_req, s_size in all_fish:
        if weather_emoji not in w_req:
            continue
        if (
            loc_cat == location
            or (loc_cat == "Lake" and "Lake" in location and location != "Lake")
            or (loc_cat == "Rivers" and "River" in location and location != "Rivers")
            or (location == "Sea Fishing" and loc_cat == "Ocean")
        ):
            available.append((f_name, w_req, t_req, s_size))
    return available


# --- UI 설정 ---
st.set_page_config(page_title="두두타 원예 & 요리 & 낚시 데이터베이스", layout="wide")

app_mode = st.sidebar.radio(
    "📊 실험 트래커 선택",
    [
        "🌱 원예 (작물) 실험",
        "🍳 요리 실험",
        "🍎 과일 채집 실험",
        "🍓 라즈베리 채집 실험",
        "🍄 버섯 채집 실험",
        "🎣 낚시 실험",
        "🏪 상점 할인 트래커",
        "📈 요리 효율 계산",
    ],
)


def render_gardening():
    st.title("🌱 두두타 원예 실험 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["데이터 입력", "데이터 분석 및 필터링", "데이터 관리(삭제)"]
    )

    with tab1:
        st.header("새로운 원예 실험 결과 입력")

        if "show_success" in st.session_state:
            st.success(st.session_state["show_success"])
            del st.session_state["show_success"]

        # Initialize map session state FIRST so we can calculate valid options
        for i in range(4):
            for z in range(5):
                for r in range(3):
                    for c in range(3):
                        wkey = f"wmap_{i}_{z}_{r}_{c}"
                        if wkey not in st.session_state:
                            st.session_state[wkey] = False

        # Evaluate the map to filter dropdown options
        all_map_options = {
            "All Cumulative (Any Stage)": "OR_ALL",
            "Stage 1 ONLY": "EXACT_0",
            "Stage 2 ONLY": "EXACT_1",
            "Stage 3 ONLY": "EXACT_2",
            "Stage 4 ONLY": "EXACT_3",
            "Overlap: Stage 1 & 2 ONLY": "EXACT_0_1",
            "Overlap: Stage 1 & 3 ONLY": "EXACT_0_2",
            "Overlap: Stage 1 & 4 ONLY": "EXACT_0_3",
            "Overlap: Stage 2 & 3 ONLY": "EXACT_1_2",
            "Overlap: Stage 2 & 4 ONLY": "EXACT_1_3",
            "Overlap: Stage 3 & 4 ONLY": "EXACT_2_3",
            "Overlap: Stage 1, 2, 3 ONLY": "EXACT_0_1_2",
            "Overlap: Stage 1, 2, 4 ONLY": "EXACT_0_1_3",
            "Overlap: Stage 1, 3, 4 ONLY": "EXACT_0_2_3",
            "Overlap: Stage 2, 3, 4 ONLY": "EXACT_1_2_3",
            "Overlap: ALL 4 Stages": "EXACT_0_1_2_3",
        }

        valid_options = {}
        counts_for_options = {}

        for name, mode in all_map_options.items():
            if mode != "OR_ALL":
                req_indices = [int(x) for x in mode.split("_")[1:]]
                target_state = [(i in req_indices) for i in range(4)]

            checked_count = 0
            unchecked_count = 0

            for z in range(5):
                for r in range(3):
                    for c in range(3):
                        if r == 1 and c == 1:
                            continue

                        v0 = st.session_state[f"wmap_0_{z}_{r}_{c}"]
                        v1 = st.session_state[f"wmap_1_{z}_{r}_{c}"]
                        v2 = st.session_state[f"wmap_2_{z}_{r}_{c}"]
                        v3 = st.session_state[f"wmap_3_{z}_{r}_{c}"]
                        current_vals = [v0, v1, v2, v3]

                        if mode == "OR_ALL":
                            is_weed_here = any(current_vals)
                        else:
                            is_weed_here = current_vals == target_state

                        if is_weed_here:
                            checked_count += 1
                        else:
                            unchecked_count += 1

            # Only add to valid list if at least one weed exists for this combination
            if mode == "OR_ALL":
                if checked_count > 0:
                    valid_options[name] = mode
                    counts_for_options[name] = (
                        unchecked_count  # Planted count = empty spaces
                    )
            else:
                if checked_count > 0:
                    valid_options[name] = mode
                    counts_for_options[name] = (
                        checked_count  # Planted count = checked spaces
                    )

        # Fallback if map is completely blank
        if not valid_options:
            valid_options = {"No weeds (Check the map first)": "NONE"}
            counts_for_options["No weeds (Check the map first)"] = 0

        # --- [추가된 심은 작물 개수 자동 동기화 로직] ---
        target_selector = st.session_state.get("weed_map_selector")

        # 목록이 "No weeds"에서 "All Cumulative" 등으로 바뀔 때 셀렉터 강제 업데이트
        if target_selector not in valid_options:
            target_selector = list(valid_options.keys())[0]
            st.session_state["weed_map_selector"] = target_selector

        current_calc_count = counts_for_options[target_selector]

        # 지도 상태가 변했거나, 데이터 저장/초기화 직후인 경우 개수 연동
        if (
            ("last_auto_planted_count" not in st.session_state)
            or (current_calc_count != st.session_state["last_auto_planted_count"])
            or ("g_planted" not in st.session_state)
        ):
            st.session_state["g_planted"] = max(0, current_calc_count)
            st.session_state["last_auto_planted_count"] = current_calc_count
        # ---------------------------------

        # Callback function for dropdown
        def on_map_viewer_change():
            sel_name = st.session_state["weed_map_selector"]
            if sel_name in counts_for_options:
                calc = max(0, counts_for_options[sel_name])
                st.session_state["g_planted"] = calc
                st.session_state["last_auto_planted_count"] = (
                    calc  # 동기화 추적 변수 업데이트
                )
                st.session_state["g_s1"] = 0
                st.session_state["g_s2"] = 0
                st.session_state["g_s3"] = 0
                st.session_state["g_s4"] = 0
                st.session_state["g_s5"] = 0

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("실험 조건")
            fertilizer = st.checkbox("비료 사용 여부", key="g_fert")
            crop_type = st.selectbox(
                "작물 종류",
                [
                    "Tomato",
                    "Potato",
                    "Wheat",
                    "Lettuce",
                    "Pineapple",
                    "Carrot",
                    "Strawberry",
                    "Corn",
                    "Grapes",
                    "Eggplant",
                    "Tea Tree",
                    "Cacao Tree",
                    "Avocado",
                ],
                key="g_crop",
            )
            water_stars = st.slider("물 별 개수", 1, 5, 1, key="g_water")

            st.write("잡초 생성 비트맵 (4-bit)")
            w_col1, w_col2, w_col3, w_col4 = st.columns(4)
            with w_col1:
                w1 = st.checkbox("1단계 잡초", key="g_w1")
            with w_col2:
                w2 = st.checkbox("2단계 잡초", key="g_w2")
            with w_col3:
                w3 = st.checkbox("3단계 잡초", key="g_w3")
            with w_col4:
                w4 = st.checkbox("4단계 잡초", key="g_w4")
            weed_bitmap_val = f"{int(w1)}{int(w2)}{int(w3)}{int(w4)}"

            weed_removed = st.checkbox("잡초 제거 여부", key="g_weed_rm")
            # [추가된 부분] 잡초 제거가 체크(True)되어야만 활성화됨
            weed_removed_after = st.checkbox(
                "방치 후 제거 여부", key="g_weed_rm_after", disabled=not weed_removed
            )
            unattended_time = st.number_input(
                "성장 후 방치 시간 (30분 단위 정수)", min_value=0, step=1, key="g_time"
            )

        with col2:
            st.subheader("수확 결과")
            # 입력창을 비활성화(disabled=True)하여 유저가 임의로 수정할 수 없게 잠금
            planted_count = st.number_input(
                "심은 작물 개수 (지도 자동 계산)",
                min_value=0,
                step=1,
                key="g_planted",
                disabled=True,
            )

            st.write("수확한 아이템 성급별 개수")
            star_1 = st.number_input("1성 아이템 개수", min_value=0, step=1, key="g_s1")
            star_2 = st.number_input("2성 아이템 개수", min_value=0, step=1, key="g_s2")
            star_3 = st.number_input("3성 아이템 개수", min_value=0, step=1, key="g_s3")
            star_4 = st.number_input("4성 아이템 개수", min_value=0, step=1, key="g_s4")
            star_5 = st.number_input("5성 아이템 개수", min_value=0, step=1, key="g_s5")

        st.divider()
        st.subheader("🌿 잡초 위치 생성 지도")
        st.caption("체크된 지도를 바탕으로 하단에 비트맵 문자열이 자동 생성됩니다.")

        for i in range(4):
            for z in range(5):
                for r in range(3):
                    for c in range(3):
                        wkey = f"wmap_{i}_{z}_{r}_{c}"
                        if wkey not in st.session_state:
                            st.session_state[wkey] = False

        map_col1, map_col2 = st.columns(2)

        with map_col1:
            w_tabs = st.tabs(["1차 잡초", "2차 잡초", "3차 잡초", "4차 잡초"])
            for i in range(4):
                with w_tabs[i]:
                    st.caption(f"**{i+1}차에 '새롭게' 돋아난 잡초 위치만 체크하세요.**")
                    for z in range(5):
                        st.markdown(f"**[{z+1} 구역]**")
                        for r in range(3):
                            cell_cols = st.columns([0.5, 0.5, 0.5, 3])
                            for c in range(3):
                                is_center = r == 1 and c == 1
                                with cell_cols[c]:
                                    st.checkbox(
                                        label=f"{i}_{z}_{r}_{c}",
                                        key=f"wmap_{i}_{z}_{r}_{c}",
                                        disabled=is_center,
                                        label_visibility="collapsed",
                                    )
                        st.write("")

        with map_col2:
            st.markdown("👀 **Weed Map Viewer (Auto-Sync)**")
            st.caption(
                "Changing the list resets stars to 0 and auto-calculates planted crops."
            )

            selected_map_name = st.selectbox(
                "Select map to view (Only active overlaps shown):",
                list(valid_options.keys()),
                key="weed_map_selector",
                on_change=on_map_viewer_change,
            )

            selected_mode = valid_options[selected_map_name]

            if selected_mode not in ("NONE", "OR_ALL"):
                req_indices = [int(x) for x in selected_mode.split("_")[1:]]
                target_state = [(i in req_indices) for i in range(4)]

            st.write("")

            for z in range(5):
                st.markdown(f"**[Zone {z+1}]**")
                for r in range(3):
                    cell_cols = st.columns([0.5, 0.5, 0.5, 3])
                    for c in range(3):
                        is_center = r == 1 and c == 1

                        v0 = st.session_state.get(f"wmap_0_{z}_{r}_{c}", False)
                        v1 = st.session_state.get(f"wmap_1_{z}_{r}_{c}", False)
                        v2 = st.session_state.get(f"wmap_2_{z}_{r}_{c}", False)
                        v3 = st.session_state.get(f"wmap_3_{z}_{r}_{c}", False)
                        current_vals = [v0, v1, v2, v3]

                        if selected_mode == "OR_ALL":
                            is_weed_here = any(current_vals)
                        else:
                            # Strict comparison: exactly matches the required Trues and Falses
                            is_weed_here = current_vals == target_state

                        st.session_state[f"cumul_dummy_{z}_{r}_{c}"] = is_weed_here
                        with cell_cols[c]:
                            st.checkbox(
                                label=f"cumul_{z}_{r}_{c}",
                                key=f"cumul_dummy_{z}_{r}_{c}",
                                disabled=True,
                                label_visibility="collapsed",
                            )
                st.write("")

        bitmaps = []
        for i in range(4):
            bmap = ""
            for r in range(3):
                for z in range(5):
                    for c in range(3):
                        if r == 1 and c == 1:
                            continue
                        val = st.session_state.get(f"wmap_{i}_{z}_{r}_{c}", False)
                        bmap += "1" if val else "0"
            bitmaps.append(bmap)
        final_weed_bitmap = "|".join(bitmaps)

        st.write("")
        st.text_input(
            "📋 생성된 잡초 비트맵 (복사 전용 / DB 저장 안 됨)",
            final_weed_bitmap,
            disabled=True,
        )

        st.write("")
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            if st.button(
                "🗑️ 잡초 지도 초기화", type="secondary", use_container_width=True
            ):
                keys_to_clear = [
                    k
                    for k in st.session_state.keys()
                    if k.startswith("wmap_") or k.startswith("cumul_dummy_")
                ]
                for k in keys_to_clear:
                    del st.session_state[k]
                st.rerun()

        with btn_col2:
            submit_button = st.button(
                "데이터 저장 (실험 결과만)", type="primary", use_container_width=True
            )
            if submit_button:
                conn = get_connection()
                c = conn.cursor()
                # 잡초 제거가 해제되어 있다면 방치 후 제거도 무조건 False로 강제 보정
                final_weed_rm_after = weed_removed_after if weed_removed else False

                c.execute(
                    """
                    INSERT INTO experiments 
                    (fertilizer, crop_type, water_stars, weed_bitmap, weed_removed, weed_removed_after, unattended_time, planted_count, star_1, star_2, star_3, star_4, star_5, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fertilizer,
                        crop_type,
                        water_stars,
                        weed_bitmap_val,
                        weed_removed,
                        final_weed_rm_after,  # 새로 추가된 변수
                        unattended_time,
                        planted_count,
                        star_1,
                        star_2,
                        star_3,
                        star_4,
                        star_5,
                        get_kst_now(),
                    ),
                )
                conn.commit()
                conn.close()

                keys_to_clear = [
                    k for k in st.session_state.keys() if k.startswith("g_")
                ]
                for k in keys_to_clear:
                    del st.session_state[k]

                st.session_state["show_success"] = (
                    "원예 데이터가 성공적으로 저장되었습니다! (지도는 초기화되지 않았습니다)"
                )
                st.rerun()

    with tab2:
        st.header("원예 실험 결과 분석")
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM experiments", conn)
        conn.close()

        if df.empty:
            st.info("아직 입력된 데이터가 없습니다.")
        else:
            st.sidebar.header("🌱 원예 조건 필터링")

            # [수정] 비료 미사용(X)이 기본값이 되도록 index=2 설정
            f_fert = st.sidebar.selectbox(
                "비료 유무", ["전체", "사용(O)", "미사용(X)"], index=2
            )

            f_crop = st.sidebar.selectbox(
                "작물 종류", ["전체"] + list(df["crop_type"].unique())
            )
            f_water = st.sidebar.multiselect(
                "물 별 개수", options=[1, 2, 3, 4, 5], default=[5]
            )
            f_weed_map = st.sidebar.selectbox(
                "잡초 생성 비트맵 (4-bit)", ["전체"] + list(df["weed_bitmap"].unique())
            )

            # [수정] 잡초 방치함(X)이 기본값이 되도록 index=2 설정
            f_weed_rm = st.sidebar.selectbox(
                "잡초 제거", ["전체", "제거함(O)", "방치함(X)"], index=2
            )

            # [추가] 방치 후 제거 여부 필터 UI
            f_weed_rm_after = st.sidebar.selectbox(
                "방치 후 제거 여부", ["전체", "방치함(O)", "방치 안 함(X)"]
            )

            min_time, max_time = int(df["unattended_time"].min()), int(
                df["unattended_time"].max()
            )
            if min_time == max_time:
                f_time = st.sidebar.slider(
                    "방치 시간", min_time, max_time + 1, (min_time, max_time + 1)
                )
            else:
                f_time = st.sidebar.slider(
                    "방치 시간", min_time, max_time, (min_time, max_time)
                )

            filtered_df = df.copy()
            if f_fert != "전체":
                filtered_df = filtered_df[
                    filtered_df["fertilizer"] == (1 if f_fert == "사용(O)" else 0)
                ]
            if f_crop != "전체":
                filtered_df = filtered_df[filtered_df["crop_type"] == f_crop]
            filtered_df = filtered_df[filtered_df["water_stars"].isin(f_water)]

            if f_weed_map != "전체":
                filtered_df = filtered_df[filtered_df["weed_bitmap"] == f_weed_map]

            if f_weed_rm != "전체":
                filtered_df = filtered_df[
                    filtered_df["weed_removed"]
                    == (1 if f_weed_rm == "제거함(O)" else 0)
                ]

            # [추가] 방치 후 제거 여부 데이터 필터링 적용
            if f_weed_rm_after != "전체":
                if "weed_removed_after" in filtered_df.columns:
                    filtered_df = filtered_df[
                        filtered_df["weed_removed_after"]
                        == (1 if f_weed_rm_after == "방치함(O)" else 0)
                    ]

            filtered_df = filtered_df[
                (filtered_df["unattended_time"] >= f_time[0])
                & (filtered_df["unattended_time"] <= f_time[1])
            ]

            st.subheader(f"필터링된 실험 횟수: {len(filtered_df)}회")

            if not filtered_df.empty:
                total_planted = filtered_df["planted_count"].sum()
                total_stars = [
                    filtered_df["star_1"].sum(),
                    filtered_df["star_2"].sum(),
                    filtered_df["star_3"].sum(),
                    filtered_df["star_4"].sum(),
                    filtered_df["star_5"].sum(),
                ]
                total_items = sum(total_stars)

                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("총 심은 작물 수", total_planted)
                col_k2.metric("총 획득 아이템 수", total_items)
                col_k3.metric(
                    "작물당 평균 드랍률",
                    (
                        f"{total_items / total_planted:.2f}개"
                        if total_planted > 0
                        else "0개"
                    ),
                )

                stats_data = []
                for i, count in enumerate(total_stars):
                    p, lower, upper = calculate_wilson_ci(count, total_items)
                    stats_data.append(
                        {
                            "성급": f"{i+1}성",
                            "획득 수": count,
                            "확률(%)": p * 100,
                            "신뢰구간 하한(%)": lower * 100,
                            "신뢰구간 상한(%)": upper * 100,
                            "오차 범위(±%)": (upper - p) * 100,
                        }
                    )

                stats_df = pd.DataFrame(stats_data)
                st.dataframe(
                    stats_df.style.format(
                        {
                            "확률(%)": "{:.2f}%",
                            "신뢰구간 하한(%)": "{:.2f}%",
                            "신뢰구간 상한(%)": "{:.2f}%",
                            "오차 범위(±%)": "{:.2f}%",
                        }
                    ),
                    use_container_width=True,
                )

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=stats_df["성급"],
                        y=stats_df["확률(%)"],
                        error_y=dict(
                            type="data", array=stats_df["오차 범위(±%)"], visible=True
                        ),
                        marker_color=[
                            "#B0C4DE",
                            "#8FBC8F",
                            "#4682B4",
                            "#DAA520",
                            "#FF8C00",
                        ],
                        text=[f"{v:.1f}%" for v in stats_df["확률(%)"]],
                        textposition="auto",
                    )
                )
                fig.update_layout(
                    title="조건별 작물 성급 드랍 확률 및 95% 신뢰구간",
                    xaxis_title="작물 성급",
                    yaxis_title="확률 (%)",
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("저장된 원예 데이터 관리")
        conn = get_connection()
        df_all = pd.read_sql_query("SELECT * FROM experiments ORDER BY id DESC", conn)
        conn.close()

        if df_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_all, use_container_width=True)
            delete_id = st.number_input(
                "삭제할 원예 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_gardening",
            )
            if st.button("해당 ID 원예 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM experiments WHERE id = ?", (delete_id,))
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_id} 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()


def render_cooking():
    st.title("🍳 두두타 요리 실험 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["요리 데이터 입력", "요리 데이터 분석 및 필터링", "요리 데이터 관리(삭제)"]
    )

    conn = get_connection()
    recipe_df = pd.read_sql_query(
        "SELECT DISTINCT recipe_name FROM cooking_experiments ORDER BY recipe_name",
        conn,
    )
    conn.close()
    existing_recipes = recipe_df["recipe_name"].tolist()

    with tab1:
        st.header("새로운 요리 실험 결과 입력")
        with st.form("cooking_input_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("요리 조건")
                recipe_options = ["(새로운 레시피 직접 입력)"] + existing_recipes
                selected_recipe = st.selectbox("레시피 선택", recipe_options)
                new_recipe_name = st.text_input(
                    "새로운 레시피 이름 (위에서 '(새로운 레시피 직접 입력)' 선택 시 작성)"
                )
                cook_count = st.number_input("요리 시도 횟수", min_value=1, step=1)
            with col2:
                st.subheader("요리 결과 (성급별 개수)")
                c_star_1 = st.number_input(
                    "1성 요리 개수", min_value=0, step=1, key="c_s1"
                )
                c_star_2 = st.number_input(
                    "2성 요리 개수", min_value=0, step=1, key="c_s2"
                )
                c_star_3 = st.number_input(
                    "3성 요리 개수", min_value=0, step=1, key="c_s3"
                )
                c_star_4 = st.number_input(
                    "4성 요리 개수", min_value=0, step=1, key="c_s4"
                )
                c_star_5 = st.number_input(
                    "5성 요리 개수", min_value=0, step=1, key="c_s5"
                )

            submit_button = st.form_submit_button(label="요리 데이터 저장")
            if submit_button:
                final_recipe_name = (
                    new_recipe_name.strip()
                    if selected_recipe == "(새로운 레시피 직접 입력)"
                    else selected_recipe
                )
                if not final_recipe_name:
                    st.error("레시피 이름을 입력하거나 선택해주세요!")
                else:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO cooking_experiments (recipe_name, cook_count, star_1, star_2, star_3, star_4, star_5, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            final_recipe_name,
                            cook_count,
                            c_star_1,
                            c_star_2,
                            c_star_3,
                            c_star_4,
                            c_star_5,
                            get_kst_now(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success(
                        f"[{final_recipe_name}] 요리 데이터가 성공적으로 저장되었습니다!"
                    )

    with tab2:
        st.header("요리 실험 결과 분석")
        conn = get_connection()
        df_cook = pd.read_sql_query("SELECT * FROM cooking_experiments", conn)
        conn.close()

        if df_cook.empty:
            st.info("아직 입력된 요리 데이터가 없습니다.")
        else:
            st.sidebar.header("🍳 요리 조건 필터링")
            f_ingredient_tier = st.sidebar.selectbox(
                "재료 성급 카테고리 (접미사 기준)",
                [
                    "전체",
                    "1/2성 재료 (접미사 없음)",
                    "3성 재료 (_3)",
                    "4성 재료 (_4)",
                    "5성 재료 (_5)",
                ],
            )
            filtered_cook = df_cook.copy()
            if f_ingredient_tier == "1/2성 재료 (접미사 없음)":
                filtered_cook = filtered_cook[
                    ~filtered_cook["recipe_name"].str.endswith(("_3", "_4", "_5"))
                ]
            elif f_ingredient_tier == "3성 재료 (_3)":
                filtered_cook = filtered_cook[
                    filtered_cook["recipe_name"].str.endswith("_3")
                ]
            elif f_ingredient_tier == "4성 재료 (_4)":
                filtered_cook = filtered_cook[
                    filtered_cook["recipe_name"].str.endswith("_4")
                ]
            elif f_ingredient_tier == "5성 재료 (_5)":
                filtered_cook = filtered_cook[
                    filtered_cook["recipe_name"].str.endswith("_5")
                ]

            f_recipe = st.sidebar.selectbox(
                "레시피 이름", ["전체"] + list(filtered_cook["recipe_name"].unique())
            )
            if f_recipe != "전체":
                filtered_cook = filtered_cook[filtered_cook["recipe_name"] == f_recipe]

            st.subheader(f"필터링된 요리 실험 기록 수: {len(filtered_cook)}건")

            if not filtered_cook.empty:
                total_cooks = filtered_cook["cook_count"].sum()
                total_c_stars = [
                    filtered_cook["star_1"].sum(),
                    filtered_cook["star_2"].sum(),
                    filtered_cook["star_3"].sum(),
                    filtered_cook["star_4"].sum(),
                    filtered_cook["star_5"].sum(),
                ]
                total_c_items = sum(total_c_stars)

                col_c1, col_c2 = st.columns(2)
                col_c1.metric("총 요리 시도 횟수", total_cooks)
                col_c2.metric("총 획득 요리 개수", total_c_items)

                stats_data_c = []
                for i, count in enumerate(total_c_stars):
                    p, lower, upper = calculate_wilson_ci(count, total_c_items)
                    stats_data_c.append(
                        {
                            "성급": f"{i+1}성",
                            "획득 수": count,
                            "확률(%)": p * 100,
                            "신뢰구간 하한(%)": lower * 100,
                            "신뢰구간 상한(%)": upper * 100,
                            "오차 범위(±%)": (upper - p) * 100,
                        }
                    )

                stats_df_c = pd.DataFrame(stats_data_c)
                st.dataframe(
                    stats_df_c.style.format(
                        {
                            "확률(%)": "{:.2f}%",
                            "신뢰구간 하한(%)": "{:.2f}%",
                            "신뢰구간 상한(%)": "{:.2f}%",
                            "오차 범위(±%)": "{:.2f}%",
                        }
                    ),
                    use_container_width=True,
                )

                fig_c = go.Figure()
                fig_c.add_trace(
                    go.Bar(
                        x=stats_df_c["성급"],
                        y=stats_df_c["확률(%)"],
                        error_y=dict(
                            type="data", array=stats_df_c["오차 범위(±%)"], visible=True
                        ),
                        marker_color=[
                            "#D8BFD8",
                            "#DDA0DD",
                            "#BA55D3",
                            "#9932CC",
                            "#4B0082",
                        ],
                        text=[f"{v:.1f}%" for v in stats_df_c["확률(%)"]],
                        textposition="auto",
                    )
                )
                fig_c.update_layout(
                    title="요리 성급별 등장 확률 및 95% 신뢰구간",
                    xaxis_title="요리 성급",
                    yaxis_title="확률 (%)",
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig_c, use_container_width=True)

    with tab3:
        st.header("저장된 요리 데이터 관리")
        conn = get_connection()
        df_cook_all = pd.read_sql_query(
            "SELECT * FROM cooking_experiments ORDER BY id DESC", conn
        )
        conn.close()

        if df_cook_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_cook_all, use_container_width=True)
            delete_c_id = st.number_input(
                "삭제할 요리 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_cooking",
            )
            if st.button("해당 ID 요리 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM cooking_experiments WHERE id = ?", (delete_c_id,)
                )
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_c_id} 요리 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()


def render_apple():
    st.title("🍎 두두타 과일 채집 효율 트래커")
    st.info(
        "💡 **시스템 메모:** 추후 요리 효율 계산 시, 여기서 측정된 **사과(Apple) 채집 효율**은 **귤(Mandarin) 채집 효율**과 1:1로 동일하게 적용됩니다."
    )
    tab1, tab2, tab3 = st.tabs(
        ["채집 데이터 입력", "채집 효율 분석", "채집 데이터 관리(삭제)"]
    )

    def save_foraging_data():
        duration = st.session_state["f_min"] + (st.session_state["f_sec"] / 60.0)
        if duration <= 0:
            st.session_state["f_error"] = "소요 시간은 0초보다 길어야 합니다!"
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO foraging_experiments (rainbow_buff, duration_minutes, apples_count, blueberries_count, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                st.session_state["f_rainbow"],
                duration,
                st.session_state["f_apples"],
                st.session_state["f_blue"],
                get_kst_now(),
            ),
        )
        conn.commit()
        conn.close()
        st.session_state["f_min"] = 0
        st.session_state["f_sec"] = 0
        st.session_state["f_apples"] = 0
        st.session_state["f_blue"] = 0
        st.session_state["f_success"] = (
            "채집 데이터가 성공적으로 저장되었습니다! (버프 상태는 유지됩니다)"
        )

    with tab1:
        st.header("새로운 채집 결과 입력")
        if "f_success" in st.session_state:
            st.success(st.session_state["f_success"])
            del st.session_state["f_success"]
        if "f_error" in st.session_state:
            st.error(st.session_state["f_error"])
            del st.session_state["f_error"]
        with st.form("foraging_input_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("채집 조건")
                st.checkbox("🌈 무지개 버프 적용 여부", key="f_rainbow")
                st.write("⏱️ 채집 소요 시간")
                t_col1, t_col2 = st.columns(2)
                with t_col1:
                    st.number_input("분", min_value=0, step=1, key="f_min")
                with t_col2:
                    st.number_input(
                        "초", min_value=0, max_value=59, step=1, key="f_sec"
                    )
            with col2:
                st.subheader("획득 결과")
                st.number_input(
                    "🍎 사과 획득 개수", min_value=0, step=1, key="f_apples"
                )
                st.number_input(
                    "🫐 블루베리 획득 개수", min_value=0, step=1, key="f_blue"
                )
            submit_button = st.form_submit_button(
                label="채집 데이터 저장", on_click=save_foraging_data
            )

    with tab2:
        st.header("무지개 버프 효율 분석")
        conn = get_connection()
        df_foraging = pd.read_sql_query("SELECT * FROM foraging_experiments", conn)
        conn.close()
        if df_foraging.empty:
            st.info("아직 입력된 채집 데이터가 없습니다.")
        else:
            total_time = df_foraging["duration_minutes"].sum()
            total_apples = df_foraging["apples_count"].sum()
            total_blueberries = df_foraging["blueberries_count"].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "총 누적 채집 시간",
                f"{int(total_time)}분 {int(round((total_time - int(total_time)) * 60))}초",
            )
            c2.metric("총 획득 사과", f"{total_apples:,} 개")
            c3.metric("총 획득 블루베리", f"{total_blueberries:,} 개")

            grouped = (
                df_foraging.groupby("rainbow_buff")[
                    ["duration_minutes", "apples_count", "blueberries_count"]
                ]
                .sum()
                .reset_index()
            )
            grouped["apple_per_min"] = (
                grouped["apples_count"] / grouped["duration_minutes"]
            )
            grouped["blueberry_per_min"] = (
                grouped["blueberries_count"] / grouped["duration_minutes"]
            )
            grouped["total_per_min"] = (
                grouped["apples_count"] + grouped["blueberries_count"]
            ) / grouped["duration_minutes"]
            grouped["buff_status"] = grouped["rainbow_buff"].apply(
                lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
            )

            display_df = grouped[
                [
                    "buff_status",
                    "apples_count",
                    "blueberries_count",
                    "apple_per_min",
                    "blueberry_per_min",
                    "total_per_min",
                ]
            ].copy()
            st.dataframe(
                display_df.style.format(
                    {
                        "apple_per_min": "{:.2f}",
                        "blueberry_per_min": "{:.2f}",
                        "total_per_min": "{:.2f}",
                    }
                ),
                use_container_width=True,
            )

    with tab3:
        st.header("저장된 채집 데이터 관리")
        conn = get_connection()
        df_foraging_all = pd.read_sql_query(
            "SELECT * FROM foraging_experiments ORDER BY id DESC", conn
        )
        conn.close()
        if df_foraging_all.empty:
            st.write("삭제할 데이터가 없습니다.")
        else:
            st.dataframe(df_foraging_all, use_container_width=True)
            delete_f_id = st.number_input(
                "삭제할 채집 실험의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_foraging",
            )
            if st.button("해당 ID 채집 데이터 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM foraging_experiments WHERE id = ?", (delete_f_id,)
                )
                conn.commit()
                conn.close()
                st.rerun()


def render_raspberry():
    st.title("🍓 두두타 라즈베리 채집 효율 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["채집 데이터 입력", "채집 효율 분석", "채집 데이터 관리(삭제)"]
    )

    def save_raspberry_data():
        duration = st.session_state["r_min"] + (st.session_state["r_sec"] / 60.0)
        if duration <= 0:
            st.session_state["r_error"] = "소요 시간은 0초보다 길어야 합니다!"
            return
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO raspberry_experiments (rainbow_buff, duration_minutes, gathered_count, timestamp) VALUES (?, ?, ?, ?)",
            (
                st.session_state["r_rainbow"],
                duration,
                st.session_state["r_count"],
                get_kst_now(),
            ),
        )
        conn.commit()
        conn.close()
        st.session_state["r_min"] = 0
        st.session_state["r_sec"] = 0
        st.session_state["r_count"] = 0
        st.session_state["r_success"] = (
            "라즈베리 채집 데이터가 성공적으로 저장되었습니다! (버프 상태는 유지됩니다)"
        )

    with tab1:
        st.header("새로운 라즈베리 채집 결과 입력")
        if "r_success" in st.session_state:
            st.success(st.session_state["r_success"])
            del st.session_state["r_success"]
        if "r_error" in st.session_state:
            st.error(st.session_state["r_error"])
            del st.session_state["r_error"]
        with st.form("raspberry_input_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                st.checkbox("🌈 무지개 버프 적용 여부", key="r_rainbow")
                t_col1, t_col2 = st.columns(2)
                with t_col1:
                    st.number_input("분", min_value=0, step=1, key="r_min")
                with t_col2:
                    st.number_input(
                        "초", min_value=0, max_value=59, step=1, key="r_sec"
                    )
            with col2:
                st.number_input(
                    "🍓 라즈베리 획득 개수", min_value=0, step=1, key="r_count"
                )
            st.form_submit_button(
                label="채집 데이터 저장", on_click=save_raspberry_data
            )

    with tab2:
        st.header("무지개 버프 효율 분석")
        conn = get_connection()
        df_rasp = pd.read_sql_query("SELECT * FROM raspberry_experiments", conn)
        conn.close()
        if df_rasp.empty:
            st.info("아직 입력된 라즈베리 채집 데이터가 없습니다.")
        else:
            grouped = (
                df_rasp.groupby("rainbow_buff")[["duration_minutes", "gathered_count"]]
                .sum()
                .reset_index()
            )
            grouped["per_min"] = grouped["gathered_count"] / grouped["duration_minutes"]
            grouped["buff_status"] = grouped["rainbow_buff"].apply(
                lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
            )
            st.dataframe(
                grouped[["buff_status", "gathered_count", "per_min"]].style.format(
                    {"per_min": "{:.2f}"}
                ),
                use_container_width=True,
            )

    with tab3:
        st.header("저장된 라즈베리 데이터 관리")
        conn = get_connection()
        df_rasp_all = pd.read_sql_query(
            "SELECT * FROM raspberry_experiments ORDER BY id DESC", conn
        )
        conn.close()
        if not df_rasp_all.empty:
            st.dataframe(df_rasp_all, use_container_width=True)
            del_r_id = st.number_input(
                "삭제할 ID 입력", min_value=0, step=1, key="del_raspberry"
            )
            if st.button("해당 ID 채집 데이터 삭제"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM raspberry_experiments WHERE id = ?", (del_r_id,))
                conn.commit()
                conn.close()
                st.rerun()


def render_mushroom():
    st.title("🍄 두두타 버섯 개별 채집 트래커")
    mushroom_names = {
        "Oyster": "느타리버섯",
        "Shiitake": "표고버섯",
        "Button": "양송이버섯",
        "Penny Bun": "그물버섯",
        "Truffle": "트러플 버섯",
    }
    tabs = st.tabs([f"{kor} ({eng})" for eng, kor in mushroom_names.items()])

    for idx, (m_eng, m_kor) in enumerate(mushroom_names.items()):
        with tabs[idx]:
            st.header(f"[{m_kor}] 채집 데이터 관리")
            with st.form(f"form_{m_eng}", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    buff = st.checkbox("🌈 무지개 버프 적용", key=f"buff_{m_eng}")
                    if m_eng == "Truffle":
                        mins, secs = 13, 0
                    else:
                        t_col1, t_col2 = st.columns(2)
                        with t_col1:
                            mins = st.number_input(
                                "분", min_value=0, step=1, key=f"min_{m_eng}"
                            )
                        with t_col2:
                            secs = st.number_input(
                                "초",
                                min_value=0,
                                max_value=59,
                                step=1,
                                key=f"sec_{m_eng}",
                            )
                with col2:
                    count = st.number_input(
                        f"{m_kor} 획득 개수", min_value=0, step=1, key=f"count_{m_eng}"
                    )
                submit = st.form_submit_button("데이터 저장")
                if submit:
                    duration = mins + (secs / 60.0)
                    if duration > 0:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO mushroom_experiments (mushroom_type, rainbow_buff, duration_minutes, gathered_count, timestamp) VALUES (?, ?, ?, ?, ?)",
                            (m_eng, buff, duration, count, get_kst_now()),
                        )
                        conn.commit()
                        conn.close()
                        st.success("저장 완료!")

            conn = get_connection()
            df_m = pd.read_sql_query(
                "SELECT * FROM mushroom_experiments WHERE mushroom_type = ?",
                conn,
                params=(m_eng,),
            )
            conn.close()
            if not df_m.empty:
                grouped = (
                    df_m.groupby("rainbow_buff")[["duration_minutes", "gathered_count"]]
                    .sum()
                    .reset_index()
                )
                grouped["per_min"] = (
                    grouped["gathered_count"] / grouped["duration_minutes"]
                )
                grouped["buff_status"] = grouped["rainbow_buff"].apply(
                    lambda x: "버프 적용 (O)" if x == 1 else "버프 미적용 (X)"
                )
                st.dataframe(
                    grouped[
                        ["buff_status", "duration_minutes", "gathered_count", "per_min"]
                    ].style.format({"duration_minutes": "{:.2f}", "per_min": "{:.2f}"}),
                    use_container_width=True,
                )
                with st.expander(f"🗑️ {m_kor} 데이터 삭제"):
                    st.dataframe(
                        df_m.sort_values("id", ascending=False),
                        use_container_width=True,
                    )
                    del_id = st.number_input(
                        "삭제할 ID 입력", min_value=0, step=1, key=f"del_{m_eng}"
                    )
                    if st.button("해당 ID 데이터 삭제", key=f"btn_del_{m_eng}"):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            "DELETE FROM mushroom_experiments WHERE id = ?", (del_id,)
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()


def render_fishing():
    st.title("🎣 두두타 낚시 채집 트래커")
    tab1, tab2, tab3 = st.tabs(["데이터 입력", "효율 분석", "데이터 관리(삭제)"])

    locations = [
        "Sea Fishing",
        "Ocean",
        "Zephyr Sea",
        "East Sea",
        "Whale Sea",
        "Old Sea",
        "Forest Lake",
        "Meadow Lake",
        "Suburban Lake",
        "Onsen Mountain Lake",
        "Shallow River",
        "Tranquil River",
        "Giantwood River",
        "Rosy River",
    ]
    time_periods = [
        "2:00 AM ~ 6:00 AM",
        "6:00 AM ~ 7:00 AM",
        "7:00 AM ~ 1:00 PM",
        "1:00 PM ~ 6:00 PM",
        "6:00 PM ~ 7:00 PM",
        "7:00 PM ~ 1:00 AM",
        "1:00 AM ~ 2:00 AM",
    ]
    weather_options = ["맑음 (Clear)", "비 (Rain)", "무지개 (Rainbow)"]

    # --- 실시간 시간대 자동 계산 함수 (KST 기준) ---
    def get_auto_time_index():
        now = datetime.utcnow() + timedelta(hours=9)
        h = now.hour
        if 2 <= h < 6:
            return 0
        elif h == 6:
            return 1
        elif 7 <= h < 13:
            return 2
        elif 13 <= h < 18:
            return 3
        elif h == 18:
            return 4
        elif h >= 19 or h == 0:
            return 5
        elif h == 1:
            return 6
        return 2  # 기본값

    # --- 하토피아 허브 날씨 표(이미지) 파싱 함수 (10분 캐시) ---
    @st.cache_data(ttl=600)
    def fetch_current_weather_index():
        try:
            import requests
            from bs4 import BeautifulSoup
            from datetime import datetime, timedelta
            import re

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            res = requests.get(
                "https://www.heartopia-hub.com/en/map", headers=headers, timeout=5
            )
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")

                # 1. KST 기준 요일 계산 및 6시간 단위 시간대 블록 계산
                now_kst = datetime.utcnow() + timedelta(hours=9)
                day_abbrev = now_kst.strftime("%a")  # 예: Mon, Tue, Wed
                # 0: Dawn(00h), 1: Morning(06h), 2: Day(12h), 3: Night(18h)
                col_idx = now_kst.hour // 6

                # 2. Weather forecast 표에서 현재 요일과 일치하는 텍스트 찾기
                day_elems = soup.find_all(string=re.compile(f"^{day_abbrev}$", re.I))
                for day_elem in day_elems:
                    # 해당 텍스트가 속한 행(tr)이나 컨테이너(div)로 거슬러 올라감
                    row = day_elem.find_parent("tr") or day_elem.find_parent(
                        "div", class_=re.compile("row|flex|grid", re.I)
                    )
                    if not row:
                        row = day_elem.find_parent("div").find_parent("div")

                    if row:
                        # 해당 행에 있는 모든 이미지를 가져옴
                        imgs = row.find_all("img")

                        # 표 구조상 요일 아이콘 등이 섞여 있을 수 있으니 뒷부분 4개를 날씨 이미지로 간주
                        if len(imgs) >= 4:
                            target_img = imgs[-4:][col_idx]
                            # 이미지의 src나 alt 속성을 읽어 날씨 키워드 판별
                            img_data = (
                                target_img.get("src", "") + target_img.get("alt", "")
                            ).lower()

                            if "rainbow" in img_data or "무지개" in img_data:
                                return 2  # 무지개
                            elif "rain" in img_data or "비" in img_data:
                                return 1  # 비
                            else:
                                return 0  # 맑음
        except Exception:
            pass  # 사이트 구조 변경 등 에러 시 기본값(맑음) 반환
        return 0

    with tab1:
        st.info(
            "💡 **시스템 자동화 적용됨:** Heartopia-Hub 예보 표의 이미지를 분석하여 '시간대'와 '날씨'가 현재 KST 시간에 맞게 자동으로 세팅됩니다."
        )

        # 현재 시간 및 파싱된 날씨 인덱스 받아오기
        auto_time_idx = get_auto_time_index()
        auto_weather_idx = fetch_current_weather_index()

        col1, col2 = st.columns([1, 1.5])
        with col1:
            f_location = st.selectbox("📍 낚시터 선택", locations)
            # 파싱된 날씨 인덱스를 기본값으로 지정
            f_weather = st.selectbox("☁️ 날씨", weather_options, index=auto_weather_idx)
            f_time = st.selectbox("⏳ 시간대", time_periods, index=auto_time_idx)

            # 선택된 날씨가 무지개일 경우 버프 체크박스 자동 활성화
            auto_buff = True if f_weather == "무지개 (Rainbow)" else False
            f_buff = st.checkbox("🌈 무지개 버프 적용", value=auto_buff)

            tc1, tc2 = st.columns(2)
            with tc1:
                f_min = st.number_input("분", min_value=0, step=1, key="fish_min")
            with tc2:
                f_sec = st.number_input(
                    "초", min_value=0, max_value=59, step=1, key="fish_sec"
                )

        with col2:
            available_fishes = get_fishes_for_location(f_location, f_weather)
            fish_counts = {}
            for f_data in available_fishes:
                fish_name = f_data[0]
                with st.expander(
                    f"**{fish_name}** | {f_data[1]} | {f_data[2]} | {f_data[3]}"
                ):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    fish_counts[fish_name] = {}
                    with c1:
                        fish_counts[fish_name]["1"] = st.number_input(
                            "1⭐", min_value=0, step=1, key=f"f_{fish_name}_1"
                        )
                    with c2:
                        fish_counts[fish_name]["2"] = st.number_input(
                            "2⭐", min_value=0, step=1, key=f"f_{fish_name}_2"
                        )
                    with c3:
                        fish_counts[fish_name]["3"] = st.number_input(
                            "3⭐", min_value=0, step=1, key=f"f_{fish_name}_3"
                        )
                    with c4:
                        fish_counts[fish_name]["4"] = st.number_input(
                            "4⭐", min_value=0, step=1, key=f"f_{fish_name}_4"
                        )
                    with c5:
                        fish_counts[fish_name]["5"] = st.number_input(
                            "5⭐", min_value=0, step=1, key=f"f_{fish_name}_5"
                        )

        if st.button("낚시 데이터 저장", type="primary", use_container_width=True):
            duration = f_min + (f_sec / 60.0)
            if duration <= 0:
                st.error("진행 시간은 0초보다 커야 합니다.")
            else:
                final_catches = {
                    f: v for f, v in fish_counts.items() if sum(v.values()) > 0
                }
                if final_catches:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO fishing_experiments (location, weather, time_period, rainbow_buff, duration_minutes, catches_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            f_location,
                            f_weather,
                            f_time,
                            f_buff,
                            duration,
                            json.dumps(final_catches),
                            get_kst_now(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success("저장 완료!")

    with tab2:
        conn = get_connection()
        df_fish = pd.read_sql_query("SELECT * FROM fishing_experiments", conn)
        conn.close()
        if not df_fish.empty:
            records = []
            for _, row in df_fish.iterrows():
                try:
                    catches = json.loads(row["catches_json"])
                except:
                    continue
                for fish, counts in catches.items():
                    tot = counts if isinstance(counts, int) else sum(counts.values())
                    if tot > 0:
                        records.append(
                            {
                                "id": row["id"],
                                "duration_minutes": row["duration_minutes"],
                                "fish_name": fish,
                                "count": tot,
                            }
                        )
            if records:
                df_exp = pd.DataFrame(records)
                session_duration = df_exp.drop_duplicates("id").set_index("id")[
                    "duration_minutes"
                ]
                stats = []
                for fish in df_exp["fish_name"].unique():
                    f_data = df_exp[df_exp["fish_name"] == fish]
                    tot_c = f_data["count"].sum()
                    tot_t = session_duration[f_data["id"].unique()].sum()
                    stats.append(
                        {
                            "물고기 이름": fish,
                            "총 포획 수": tot_c,
                            "총 소요시간(분)": round(tot_t, 2),
                            "마리당 소요시간(분)": round(
                                tot_t / tot_c if tot_c > 0 else 0, 2
                            ),
                        }
                    )
                st.dataframe(
                    pd.DataFrame(stats).sort_values("마리당 소요시간(분)"),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab3:
        if not df_fish.empty:
            st.dataframe(
                df_fish.sort_values("id", ascending=False), use_container_width=True
            )
            del_id = st.number_input(
                "삭제할 낚시 ID 입력", min_value=0, step=1, key="del_fish"
            )
            if st.button("데이터 삭제"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM fishing_experiments WHERE id = ?", (del_id,))
                conn.commit()
                conn.close()
                st.rerun()


def render_shop():
    st.title("🏪 마시모 상점 할인 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["오늘의 할인 입력", "상점 단가표 및 할인 확률", "데이터 관리(삭제)"]
    )

    with tab1:
        conn = get_connection()
        ingredients_list = pd.read_sql_query(
            "SELECT ingredient_name FROM store_reference", conn
        )["ingredient_name"].tolist()
        conn.close()

        record_date = st.date_input("기록 날짜", get_kst_date())

        # UI 및 DB 저장에 공통으로 사용할 필터링된 리스트 생성
        filtered_ingredients = [i for i in ingredients_list if "Sugar" not in i]

        discounted_items = st.multiselect(
            "오늘 40% 할인 중인 품목 선택:",
            options=filtered_ingredients,
        )

        if st.button("할인 정보 저장", type="primary"):
            conn = get_connection()
            c = conn.cursor()

            # 전체 리스트(ingredients_list)가 아닌, 사탕이 제외된 리스트(filtered_ingredients)만 돌면서 저장
            for ing in filtered_ingredients:
                c.execute(
                    "INSERT INTO store_discounts (record_date, ingredient_name, is_discounted, timestamp) VALUES (?, ?, ?, ?) ON CONFLICT(record_date, ingredient_name) DO UPDATE SET is_discounted = excluded.is_discounted, timestamp = excluded.timestamp",
                    (str(record_date), ing, ing in discounted_items, get_kst_now()),
                )
            conn.commit()
            conn.close()
            st.success("저장 완료!")

    with tab2:
        conn = get_connection()
        df_analysis = pd.read_sql_query(
            "SELECT d.ingredient_name, COUNT(d.id) as total_days, SUM(CASE WHEN d.is_discounted THEN 1 ELSE 0 END) as discount_days, r.discounted_price, r.base_price FROM store_discounts d JOIN store_reference r ON d.ingredient_name = r.ingredient_name GROUP BY d.ingredient_name",
            conn,
        )
        conn.close()
        if not df_analysis.empty:
            df_analysis["할인 확률(%)"] = (
                df_analysis["discount_days"] / df_analysis["total_days"]
            ) * 100

            # (기본가 * 일반 확률) + (할인가 * 할인 확률)
            df_analysis["평균 구매 단가"] = (
                df_analysis["base_price"]
                * (1 - df_analysis["discount_days"] / df_analysis["total_days"])
            ) + (
                df_analysis["discounted_price"]
                * (df_analysis["discount_days"] / df_analysis["total_days"])
            )
            st.dataframe(
                df_analysis[
                    [
                        "ingredient_name",
                        "base_price",
                        "discounted_price",
                        "total_days",
                        "discount_days",
                        "할인 확률(%)",
                        "평균 구매 단가",
                    ]
                ].style.format({"할인 확률(%)": "{:.1f}%", "평균 구매 단가": "{:.2f}"}),
                use_container_width=True,
            )

    with tab3:
        conn = get_connection()
        df_store_all = pd.read_sql_query(
            "SELECT * FROM store_discounts ORDER BY record_date DESC, id DESC", conn
        )
        conn.close()
        if not df_store_all.empty:
            st.dataframe(df_store_all, use_container_width=True)
            delete_s_id = st.number_input(
                "삭제할 ID 입력", min_value=0, step=1, key="del_store"
            )
            if st.button("데이터 삭제"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("DELETE FROM store_discounts WHERE id = ?", (delete_s_id,))
                conn.commit()
                conn.close()
                st.rerun()


def render_efficiency():
    st.title("📈 두두타 요리 효율 종합 대시보드")
    st.info(
        "💡 모든 레시피의 요리 효율(비용, 채집 시간, 밭 점유 시간, 순이익)을 한눈에 확인할 수 있습니다.\n\n※ 농작물이 포함된 레시피는 사용된 작물의 성급(1~5성)에 따라 `_1` ~ `_5` 버전으로 나뉘어 표시됩니다."
    )

    # --- [수정된 안내 문구] ---
    st.markdown(
        """
        **🌱 밭 점유 시간 계산 방식 안내**
        * 해당 레시피에 필요한 작물을 얻기 위해 **'40칸짜리 밭을 몇 번 수확해야 하는지'**를 기준으로 계산됩니다.
        * **계산 공식:** `[필요 수량 / (작물 1개당 평균 드랍률 × 40)] × 작물별 성장 시간`
        * **평균 드랍률 통제 변인:** 물 5개, 잡초 방치(제거X), 방치 시간 0분
          * **비료 사용(O):** 딸기, 옥수수, 포도, 가지
          * **비료 미사용(X):** 토마토, 감자, 밀, 상추, 파인애플, 당근
        > *예시: 1성 토마토의 드랍률이 1.5개일 경우, 40칸 밭 1회 수확 시 60개를 얻습니다. 요리에 20개가 필요하다면 0.33번의 수확 사이클이 필요하며, 토마토 성장 시간(15분)을 곱해 총 5분의 밭 점유 시간이 산출됩니다.*
        """
    )
    # ----------------------------------

    df_recipes = pd.DataFrame(recipe_raw_data)

    recipe_prices = {}
    for _, r in df_recipes.iterrows():
        recipe_prices[r["name"]] = {
            "1성": r["s1"],
            "2성": r["s2"],
            "3성": r["s3"],
            "4성": r["s4"],
            "5성": r["s5"],
        }

    conn = get_connection()
    df_store = pd.read_sql_query(
        """
        SELECT 
            r.ingredient_name, r.discounted_price, r.base_price,
            COUNT(d.id) as total_days,
            SUM(CASE WHEN d.is_discounted THEN 1 ELSE 0 END) as discount_days
        FROM store_reference r
        LEFT JOIN store_discounts d ON r.ingredient_name = d.ingredient_name
        GROUP BY r.ingredient_name
    """,
        conn,
    )
    df_crop = pd.read_sql_query("SELECT * FROM crop_reference", conn)
    df_cook_exp = pd.read_sql_query("SELECT * FROM cooking_experiments", conn)
    df_forage = pd.read_sql_query("SELECT * FROM foraging_experiments", conn)
    df_rasp = pd.read_sql_query("SELECT * FROM raspberry_experiments", conn)
    df_mush = pd.read_sql_query("SELECT * FROM mushroom_experiments", conn)
    df_yield = pd.read_sql_query(
        "SELECT * FROM experiments",
        conn,
    )
    conn.close()

    with st.expander(
        "📚 현재 등록된 전체 요리 레시피 목록 보기 (클릭하여 열기)", expanded=False
    ):
        st.dataframe(
            df_recipes[["name", "recipe"]].rename(
                columns={"name": "요리 이름", "recipe": "필요 식재료"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    st.divider()

    item_costs = {}
    for _, row in df_store.iterrows():
        if row["total_days"] > 0:
            prob = row["discount_days"] / row["total_days"]
            item_costs[row["ingredient_name"]] = (
                row["base_price"] * (1 - prob) + row["discounted_price"] * prob
            )
        else:
            item_costs[row["ingredient_name"]] = row["base_price"]

    for sugar in [
        "Sugar",
        "Blue Sugar",
        "Indigo Sugar",
        "Violet Sugar",
        "Red Sugar",
        "Yellow Sugar",
        "Orange Sugar",
        "Green Sugar",
    ]:
        if sugar not in item_costs:
            item_costs[sugar] = (
                150 if sugar not in ["Orange Sugar", "Green Sugar"] else 200
            )

    crop_sell_prices = {}
    for _, row in df_crop.iterrows():
        crop_sell_prices[row["crop_name"]] = {
            "1성": row["star_1_price"] or 0,
            "2성": row["star_2_price"] or 0,
            "3성": row["star_3_price"] or 0,
            "4성": row["star_4_price"] or 0,
            "5성": row["star_5_price"] or 0,
        }

    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        use_rainbow = st.toggle("🌈 채집 무지개 버프 데이터 적용", value=False)

    buff_val = 1 if use_rainbow else 0
    forage_speeds = {}

    ab_group = df_forage[df_forage["rainbow_buff"] == buff_val]
    if not ab_group.empty and ab_group["duration_minutes"].sum() > 0:
        mins = ab_group["duration_minutes"].sum()
        forage_speeds["Apple"] = ab_group["apples_count"].sum() / mins
        forage_speeds["Mandarin"] = forage_speeds["Apple"]
        forage_speeds["Blueberry"] = ab_group["blueberries_count"].sum() / mins
    else:
        forage_speeds["Apple"] = forage_speeds["Mandarin"] = forage_speeds[
            "Blueberry"
        ] = 0

    r_group = df_rasp[df_rasp["rainbow_buff"] == buff_val]
    if not r_group.empty and r_group["duration_minutes"].sum() > 0:
        forage_speeds["Raspberry"] = (
            r_group["gathered_count"].sum() / r_group["duration_minutes"].sum()
        )
    else:
        forage_speeds["Raspberry"] = 0

    m_group = df_mush[df_mush["rainbow_buff"] == buff_val]
    for mtype in ["Button", "Oyster", "Penny Bun", "Shiitake", "Truffle"]:
        sub = m_group[m_group["mushroom_type"] == mtype]
        mapped_name = {"Penny Bun": "PennyBun", "Truffle": "BlackTruffle"}.get(
            mtype, mtype
        )
        if not sub.empty and sub["duration_minutes"].sum() > 0:
            forage_speeds[mapped_name] = (
                sub["gathered_count"].sum() / sub["duration_minutes"].sum()
            )
        else:
            forage_speeds[mapped_name] = 0

    m_group = df_mush[df_mush["rainbow_buff"] == buff_val]
    for mtype in ["Button", "Oyster", "Penny Bun", "Shiitake", "Truffle"]:
        sub = m_group[m_group["mushroom_type"] == mtype]
        mapped_name = {"Penny Bun": "PennyBun", "Truffle": "BlackTruffle"}.get(
            mtype, mtype
        )
        if not sub.empty and sub["duration_minutes"].sum() > 0:
            forage_speeds[mapped_name] = (
                sub["gathered_count"].sum() / sub["duration_minutes"].sum()
            )
        else:
            forage_speeds[mapped_name] = 0.0001

    def get_tier(name):
        if name.endswith("_5"):
            return "5성"
        if name.endswith("_4"):
            return "4성"
        if name.endswith("_3"):
            return "3성"
        return "1/2성"

    df_cook_exp["tier"] = df_cook_exp["recipe_name"].apply(get_tier)
    cook_probs = {}
    for tier, group in df_cook_exp.groupby("tier"):
        total = group[["star_1", "star_2", "star_3", "star_4", "star_5"]].sum().sum()
        if total > 0:
            cook_probs[tier] = {
                "s1": group["star_1"].sum() / total,
                "s2": group["star_2"].sum() / total,
                "s3": group["star_3"].sum() / total,
                "s4": group["star_4"].sum() / total,
                "s5": group["star_5"].sum() / total,
            }

    yield_rates = {}
    fertilizer_crops = ["Strawberry", "Corn", "Grapes", "Eggplant"]

    # [수정된 부분] 요구하신 고정 통제 변인 설정 (물 5개, 잡초 제거X, 방치 0분)
    base_condition = (
        (df_yield["water_stars"] == 5)
        & (df_yield["weed_removed"] == 0)
        & (df_yield["unattended_time"] == 0)
    )

    for crop in df_yield["crop_type"].unique():
        # 기본 통제 변인에 작물별 비료 사용 여부를 추가로 묶어서 필터링
        if crop in fertilizer_crops:
            sub_df = df_yield[
                (df_yield["crop_type"] == crop)
                & (df_yield["fertilizer"] == 1)
                & base_condition
            ]
        else:
            sub_df = df_yield[
                (df_yield["crop_type"] == crop)
                & (df_yield["fertilizer"] == 0)
                & base_condition
            ]

        total_planted = sub_df["planted_count"].sum()
        if total_planted > 0:
            yield_rates[crop] = {
                "1성": sub_df["star_1"].sum() / total_planted,
                "2성": sub_df["star_2"].sum() / total_planted,
                "3성": sub_df["star_3"].sum() / total_planted,
                "4성": sub_df["star_4"].sum() / total_planted,
                "5성": sub_df["star_5"].sum() / total_planted,
            }

    # --- [핵심 로직] 작물이나 해산물이 하위 재료에 하나라도 있는지 재귀적으로 확인 ---
    def check_star_dependency(b_name, visited=None):
        if visited is None:
            visited = set()
        if b_name in visited:
            return False
        visited.add(b_name)

        row = df_recipes[df_recipes["name"] == b_name]
        if row.empty:
            return False
        r_str = row.iloc[0]["recipe"]

        for item in r_str.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(" ", 1)
            if len(parts) == 2:
                ing = parts[1]
                if ing == "Coffee" and b_name == "Coffee":
                    ing = "Coffee Beans"

                # 재료 자체가 작물이나 해산물이면 즉시 1~5성 쪼개기 트리거 발동
                if ing in growth_mins or ing in generic_seafood_prices:
                    return True

                # 만약 재료가 완성된 하위 요리라면 재귀 확인
                m_ing = sub_recipe_map.get(ing, ing)
                if m_ing in df_recipes["name"].values:
                    if check_star_dependency(m_ing, visited):
                        return True
        return False

    def format_real_time(mins):
        if pd.isna(mins) or mins == float("inf"):
            return "데이터 부족"
        total_seconds = int(mins * 60)
        m, s = total_seconds // 60, total_seconds % 60
        return f"{m}분 {s}초" if m > 0 else f"{s}초"

    table_data = []

    for _, r in df_recipes.iterrows():
        base_name = r["name"]
        ingredients_str = r["recipe"]
        prices = {
            "s1": r["s1"],
            "s2": r["s2"],
            "s3": r["s3"],
            "s4": r["s4"],
            "s5": r["s5"],
        }

        reqs = {}
        for item in ingredients_str.split(","):
            item = item.strip()
            if not item:
                continue
            parts = item.split(" ", 1)
            if len(parts) == 2 and parts[0].isdigit():
                qty = int(parts[0])
                name = parts[1]

                # CookingOil 띄어쓰기 예외만 남김 (커피콩 관련 땜질 코드 삭제)
                if name == "CookingOil":
                    name = "Cooking Oil"

                reqs[name] = qty

        has_crop_or_seafood = check_star_dependency(base_name)
        tiers_to_generate = (
            ["1성", "2성", "3성", "4성"] if has_crop_or_seafood else ["기본"]
        )

        for t_idx in tiers_to_generate:
            display_name = base_name if t_idx == "기본" else f"{base_name}_{t_idx[0]}"
            prob_tier = "1/2성" if t_idx in ["기본", "1성", "2성"] else t_idx

            total_material_cost = 0
            total_forage_mins = 0
            total_field_mins = 0
            can_calc_field = True

            for ing_name, qty in reqs.items():
                target_tier_for_price = "1성" if t_idx == "기본" else t_idx
                # reqs[name]에서 이미 보정되었으므로 바로 사용 가능합니다.
                actual_store_name = store_alias.get(ing_name, ing_name)
                mapped_recipe_name = sub_recipe_map.get(ing_name, ing_name)

                if actual_store_name in item_costs:
                    total_material_cost += qty * item_costs[actual_store_name]
                elif ing_name in crop_sell_prices:
                    total_material_cost += qty * crop_sell_prices[ing_name].get(
                        target_tier_for_price, 0
                    )
                elif ing_name in generic_seafood_prices:
                    total_material_cost += qty * generic_seafood_prices[ing_name].get(
                        target_tier_for_price, 0
                    )
                elif ing_name in forage_sell_prices:
                    total_material_cost += qty * forage_sell_prices[ing_name]
                elif mapped_recipe_name in recipe_prices:
                    price = recipe_prices[mapped_recipe_name].get(target_tier_for_price)
                    if price is None:
                        price = recipe_prices[mapped_recipe_name].get("1성", 0)
                    total_material_cost += qty * price

                if ing_name in forage_speeds:
                    if forage_speeds[ing_name] > 0:
                        total_forage_mins += qty / forage_speeds[ing_name]
                    else:
                        total_forage_mins = float(
                            "inf"
                        )  # 데이터가 0이면 무한대 처리하여 '데이터 부족'을 띄움

                if ing_name in growth_mins:
                    if ing_name in yield_rates:
                        rate = yield_rates[ing_name].get(target_tier_for_price, 0)
                        if rate > 0:
                            harvests = qty / (rate * 40)
                            total_field_mins += harvests * growth_mins[ing_name]
                        else:
                            can_calc_field = False
                    else:
                        can_calc_field = False

            if prob_tier in cook_probs:
                probs = cook_probs[prob_tier]
                expected_revenue = sum(
                    [
                        probs[s] * prices[s]
                        for s in ["s1", "s2", "s3", "s4", "s5"]
                        if prices[s] is not None
                    ]
                )
                net_profit = expected_revenue - total_material_cost
            else:
                expected_revenue = None
                net_profit = None

            field_time_str = (
                format_real_time(total_field_mins)
                if can_calc_field and any(ing in growth_mins for ing in reqs)
                else (
                    "해당 없음"
                    if not any(ing in growth_mins for ing in reqs)
                    else "데이터 부족"
                )
            )
            forage_time_str = (
                format_real_time(total_forage_mins)
                if total_forage_mins > 0
                else "해당 없음"
            )

            # [수정된 부분] 보정된 reqs의 키값을 리스트로 그대로 저장
            table_data.append(
                {
                    "요리 이름": display_name,
                    "재료 원가": total_material_cost,
                    "평균 판매가": expected_revenue,
                    "순이익": net_profit,
                    "채집 시간": forage_time_str,
                    "밭 점유": field_time_str,
                    "필요 식재료": ingredients_str,
                    "_ing_keys": list(reqs.keys()),
                }
            )

    df_final = pd.DataFrame(table_data)

    def format_currency(x):
        return "데이터 부족" if pd.isna(x) else f"{x:,.1f} G"

    # ==========================================
    # [UI 수정] 정규 레시피와 커스텀(시즌) 레시피를 탭으로 분리하여 DB 연동
    # ==========================================
    tab_main, tab_add, tab_view, tab_manage = st.tabs(
        [
            "📊 정규 요리 효율 대시보드",
            "➕ 커스텀/시즌 요리 추가",
            "📝 커스텀 요리 효율표",
            "🗑️ 커스텀 요리 관리",
        ]
    )

    with tab_main:
        st.subheader("📊 요리 종합 기회비용 및 효율 분석표")

        store_filter_options = [
            item for item in item_costs.keys() if "Sugar" not in item
        ]
        selected_filter_ings = st.multiselect(
            "🛒 상점 재료 필터 (마시모 상점 판매 물품 한정)",
            options=sorted(store_filter_options),
            placeholder="필터링할 상점 재료를 선택하세요 (예: Butter, Cooking Oil, Coffee Beans 등)",
        )

        if selected_filter_ings:
            mask = df_final["_ing_keys"].apply(
                lambda keys: any(item in keys for item in selected_filter_ings)
            )
            df_final = df_final[mask]

        if "_ing_keys" in df_final.columns:
            df_final = df_final.drop(columns=["_ing_keys"])

        st.caption(
            "※ 작물 및 채집물은 상점 씨앗 가격이 아닌 **판매 가격(기회비용)**을 원가로 반영하여 순이익을 계산했습니다."
        )
        st.dataframe(
            df_final.style.format(
                {
                    "재료 원가": format_currency,
                    "평균 판매가": format_currency,
                    "순이익": format_currency,
                }
            ).background_gradient(subset=["순이익"], cmap="Greens"),
            use_container_width=True,
            hide_index=True,
            height=800,
        )

    with tab_add:
        st.subheader("⏳ 커스텀 (시즌 한정) 레시피 추가")
        st.info(
            "입력하신 레시피는 DB에 저장되며, '커스텀 요리 효율표' 탭에서 언제든 효율을 확인할 수 있습니다."
        )

        with st.form("custom_recipe_form", clear_on_submit=True):
            col_c1, col_c2 = st.columns([1, 2])
            with col_c1:
                c_name = st.text_input("요리 이름", placeholder="예: 벚꽃 롤케이크")
            with col_c2:
                c_recipe = st.text_input(
                    "필요 식재료 (쉼표로 구분)",
                    placeholder="예: 2 Strawberry, 1 Milk, 1 Wheat",
                )

            st.write("💰 성급별 판매가 입력 (해당 없는 성급은 0으로 두세요)")
            s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
            with s_col1:
                c_s1 = st.number_input("1성 판매가", min_value=0, value=0)
            with s_col2:
                c_s2 = st.number_input("2성 판매가", min_value=0, value=0)
            with s_col3:
                c_s3 = st.number_input("3성 판매가", min_value=0, value=0)
            with s_col4:
                c_s4 = st.number_input("4성 판매가", min_value=0, value=0)
            with s_col5:
                c_s5 = st.number_input("5성 판매가", min_value=0, value=0)

            c_submit = st.form_submit_button("레시피 DB에 저장하기", type="primary")

        if c_submit:
            if not c_name or not c_recipe:
                st.error("요리 이름과 필요 식재료를 모두 입력해 주세요!")
            else:
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    """INSERT INTO custom_recipes (recipe_name, ingredients, s1_price, s2_price, s3_price, s4_price, s5_price, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (c_name, c_recipe, c_s1, c_s2, c_s3, c_s4, c_s5, get_kst_now()),
                )
                conn.commit()
                conn.close()
                st.success(
                    f"[{c_name}] 레시피가 성공적으로 저장되었습니다! '커스텀 요리 효율표' 탭을 확인해 주세요."
                )

    with tab_view:
        st.subheader("📝 저장된 커스텀 요리 효율표")
        conn = get_connection()
        df_custom = pd.read_sql_query(
            "SELECT * FROM custom_recipes ORDER BY id DESC", conn
        )
        conn.close()

        if df_custom.empty:
            st.info(
                "저장된 커스텀 레시피가 없습니다. 옆의 탭에서 레시피를 추가해 주세요."
            )
        else:
            results = []
            for _, row in df_custom.iterrows():
                db_c_name = row["recipe_name"]
                db_c_recipe = row["ingredients"]
                custom_prices = {
                    "s1": row["s1_price"],
                    "s2": row["s2_price"],
                    "s3": row["s3_price"],
                    "s4": row["s4_price"],
                    "s5": row["s5_price"],
                }

                reqs = {}
                for item in db_c_recipe.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    parts = item.split(" ", 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        name = parts[1]
                        if name == "CookingOil":
                            name = "Cooking Oil"
                        reqs[name] = int(parts[0])

                has_crop_or_seafood = any(
                    ing in growth_mins or ing in generic_seafood_prices for ing in reqs
                )
                tiers_to_generate = (
                    ["1성", "2성", "3성", "4성"] if has_crop_or_seafood else ["기본"]
                )

                for t_idx in tiers_to_generate:
                    display_name = (
                        db_c_name if t_idx == "기본" else f"{db_c_name}_{t_idx[0]}"
                    )
                    prob_tier = "1/2성" if t_idx in ["기본", "1성", "2성"] else t_idx

                    total_material_cost = 0
                    total_forage_mins = 0
                    total_field_mins = 0
                    can_calc_field = True

                    for ing_name, qty in reqs.items():
                        target_tier_for_price = "1성" if t_idx == "기본" else t_idx
                        actual_store_name = store_alias.get(ing_name, ing_name)
                        mapped_recipe_name = sub_recipe_map.get(ing_name, ing_name)

                        if actual_store_name in item_costs:
                            total_material_cost += qty * item_costs[actual_store_name]
                        elif ing_name in crop_sell_prices:
                            total_material_cost += qty * crop_sell_prices[ing_name].get(
                                target_tier_for_price, 0
                            )
                        elif ing_name in generic_seafood_prices:
                            total_material_cost += qty * generic_seafood_prices[
                                ing_name
                            ].get(target_tier_for_price, 0)
                        elif ing_name in forage_sell_prices:
                            total_material_cost += qty * forage_sell_prices[ing_name]
                        elif mapped_recipe_name in recipe_prices:
                            price = recipe_prices[mapped_recipe_name].get(
                                target_tier_for_price
                            )
                            if price is None:
                                price = recipe_prices[mapped_recipe_name].get("1성", 0)
                            total_material_cost += qty * price

                        if ing_name in forage_speeds:
                            if forage_speeds[ing_name] > 0:
                                total_forage_mins += qty / forage_speeds[ing_name]
                            else:
                                total_forage_mins = float("inf")

                        if ing_name in growth_mins:
                            if ing_name in yield_rates:
                                rate = yield_rates[ing_name].get(
                                    target_tier_for_price, 0
                                )
                                if rate > 0:
                                    harvests = qty / (rate * 40)
                                    total_field_mins += harvests * growth_mins[ing_name]
                                else:
                                    can_calc_field = False
                            else:
                                can_calc_field = False

                    if prob_tier in cook_probs:
                        probs = cook_probs[prob_tier]
                        expected_revenue = sum(
                            [
                                probs[s] * custom_prices[s]
                                for s in ["s1", "s2", "s3", "s4", "s5"]
                                if custom_prices[s] > 0
                            ]
                        )
                        net_profit = expected_revenue - total_material_cost
                    else:
                        expected_revenue = None
                        net_profit = None

                    field_time_str = (
                        format_real_time(total_field_mins)
                        if can_calc_field and any(ing in growth_mins for ing in reqs)
                        else (
                            "해당 없음"
                            if not any(ing in growth_mins for ing in reqs)
                            else "데이터 부족"
                        )
                    )
                    forage_time_str = (
                        format_real_time(total_forage_mins)
                        if total_forage_mins > 0
                        else "해당 없음"
                    )

                    results.append(
                        {
                            "요리 이름": display_name,
                            "필요 식재료": db_c_recipe,
                            "재료 원가": total_material_cost,
                            "평균 판매가": expected_revenue,
                            "순이익": net_profit,
                            "채집 시간": forage_time_str,
                            "밭 점유": field_time_str,
                        }
                    )

            st.dataframe(
                pd.DataFrame(results)
                .style.format(
                    {
                        "재료 원가": format_currency,
                        "평균 판매가": format_currency,
                        "순이익": format_currency,
                    }
                )
                .background_gradient(subset=["순이익"], cmap="Greens"),
                use_container_width=True,
                hide_index=True,
            )

    with tab_manage:
        st.subheader("🗑️ 저장된 커스텀 요리 데이터 관리")
        conn = get_connection()
        df_custom_all = pd.read_sql_query(
            "SELECT * FROM custom_recipes ORDER BY id DESC", conn
        )
        conn.close()

        if df_custom_all.empty:
            st.write("삭제할 커스텀 레시피 데이터가 없습니다.")
        else:
            st.dataframe(df_custom_all, use_container_width=True)
            delete_custom_id = st.number_input(
                "삭제할 커스텀 레시피의 ID를 입력하세요",
                min_value=0,
                step=1,
                key="del_custom",
            )
            if st.button("해당 ID 커스텀 레시피 삭제", type="primary"):
                conn = get_connection()
                c = conn.cursor()
                c.execute(
                    "DELETE FROM custom_recipes WHERE id = ?", (delete_custom_id,)
                )
                conn.commit()
                conn.close()
                st.success(
                    f"ID {delete_custom_id} 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()


if app_mode == "🌱 원예 (작물) 실험":
    render_gardening()
elif app_mode == "🍳 요리 실험":
    render_cooking()
elif app_mode == "🍎 과일 채집 실험":
    render_apple()
elif app_mode == "🍓 라즈베리 채집 실험":
    render_raspberry()
elif app_mode == "🍄 버섯 채집 실험":
    render_mushroom()
elif app_mode == "🎣 낚시 실험":
    render_fishing()
elif app_mode == "🏪 상점 할인 트래커":
    render_shop()
elif app_mode == "📈 요리 효율 계산":
    render_efficiency()

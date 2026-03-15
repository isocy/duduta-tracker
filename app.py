import streamlit as st
import sqlite3
import pandas as pd
import math
import plotly.graph_objects as go
from datetime import datetime, timedelta


# --- 한국 시간(KST) 계산 함수 ---
def get_kst_now():
    # 서버 환경(UTC)을 고려해 명시적으로 +9시간을 더해 문자열로 반환
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


# --- 데이터베이스 초기화 및 연결 ---
DB_NAME = "duduta_experiment.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 원예 실험 테이블
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fertilizer BOOLEAN,
            crop_type TEXT,
            water_stars INTEGER,
            weed_bitmap TEXT,
            weed_removed BOOLEAN,
            unattended_time INTEGER,
            planted_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 이전에 잘못 추가되었던 weed_location_map 컬럼이 존재하면 안전하게 삭제하여 DB 원상복구
    c.execute("PRAGMA table_info(experiments)")
    columns = [info[1] for info in c.fetchall()]
    if "weed_location_map" in columns:
        try:
            c.execute("ALTER TABLE experiments DROP COLUMN weed_location_map")
        except sqlite3.OperationalError:
            pass

    # 요리 실험 테이블
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cooking_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_name TEXT,
            cook_count INTEGER,
            star_1 INTEGER,
            star_2 INTEGER,
            star_3 INTEGER,
            star_4 INTEGER,
            star_5 INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # 과일 채집 실험 테이블
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS foraging_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rainbow_buff BOOLEAN,
            duration_minutes FLOAT,
            apples_count INTEGER,
            blueberries_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # [수정됨] 스키마가 변경되었을 때 에러가 나지 않도록 기존 참조 테이블을 먼저 삭제합니다.
    c.execute("DROP TABLE IF EXISTS crop_reference")

    # 작물 메타데이터(시간, 원가 및 성급별 가치) 테이블 새로 생성
    c.execute(
        """
        CREATE TABLE crop_reference (
            crop_name TEXT PRIMARY KEY,
            growth_time TEXT,
            seed_cost INTEGER,
            star_1_price INTEGER,
            star_2_price INTEGER,
            star_3_price INTEGER,
            star_4_price INTEGER,
            star_5_price INTEGER
        )
    """
    )

    # 이미지 기반 초기 작물 데이터 삽입 (레벨 제외, 성장 시간 포함, 5성 값이 없는 경우 None 처리)
    crops_data = [
        ("Tomato", "15m", 10, 30, 40, 50, 60, 70),
        ("Potato", "1h", 30, 90, 120, 150, 180, 210),
        ("Wheat", "4h", 95, 285, 381, 475, 570, 855),
        ("Lettuce", "8h", 145, 435, 582, 726, 870, 1305),
        ("Pineapple", "30m", 15, 52, 69, 86, 104, None),
        ("Carrot", "2h", 50, 155, 207, 258, 310, None),
        ("Strawberry", "6h", 125, 375, 502, 626, 750, 1125),
        ("Corn", "12h", 170, 515, 690, 860, 1030, 1545),
        ("Grapes", "10h", 160, 480, 643, 801, 960, None),
        ("Eggplant", "7h", 135, 406, 544, 678, 812, 1218),
    ]

    c.executemany(
        """
        INSERT OR REPLACE INTO crop_reference 
        (crop_name, growth_time, seed_cost, star_1_price, star_2_price, star_3_price, star_4_price, star_5_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        crops_data,
    )

    conn.commit()
    conn.close()


init_db()


# --- 윌슨 점수 신뢰구간(Wilson Score Interval) 계산 ---
def calculate_wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return p, max(0.0, center - spread), min(1.0, center + spread)


# --- UI 설정 ---
st.set_page_config(page_title="두두타 원예 & 요리 실험 데이터베이스", layout="wide")

# 사이드바에서 모드 선택
app_mode = st.sidebar.radio(
    "📊 실험 트래커 선택", ["🌱 원예 (작물) 실험", "🍳 요리 실험", "🍎 과일 채집 실험"]
)

if app_mode == "🌱 원예 (작물) 실험":
    st.title("🌱 두두타 원예 실험 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["데이터 입력", "데이터 분석 및 필터링", "데이터 관리(삭제)"]
    )

    with tab1:
        st.header("새로운 원예 실험 결과 입력")

        if "show_success" in st.session_state:
            st.success(st.session_state["show_success"])
            del st.session_state["show_success"]

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

            st.write("잡초 생성 비트맵 (3-bit)")
            w_col1, w_col2, w_col3 = st.columns(3)
            with w_col1:
                w1 = st.checkbox("1단계 잡초", key="g_w1")
            with w_col2:
                w2 = st.checkbox("2단계 잡초", key="g_w2")
            with w_col3:
                w3 = st.checkbox("3단계 잡초", key="g_w3")
            weed_bitmap_val = f"{int(w1)}{int(w2)}{int(w3)}"

            weed_removed = st.checkbox("잡초 제거 여부", key="g_weed_rm")
            unattended_time = st.number_input(
                "성장 후 방치 시간 (30분 단위 정수)", min_value=0, step=1, key="g_time"
            )

        with col2:
            st.subheader("수확 결과")
            planted_count = st.number_input(
                "심은 작물 개수", min_value=1, step=1, key="g_planted"
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

        for i in range(3):
            for z in range(5):
                for r in range(3):
                    for c in range(3):
                        wkey = f"wmap_{i}_{z}_{r}_{c}"
                        if wkey not in st.session_state:
                            st.session_state[wkey] = False

        map_col1, map_col2 = st.columns(2)

        with map_col1:
            w_tabs = st.tabs(["1차 잡초", "2차 잡초", "3차 잡초"])
            for i in range(3):
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
            st.markdown("👀 **누적 잡초 (자동반영)**")
            st.caption(
                "1차 ~ 3차에 걸쳐 생성된 **모든 잡초가 누적된 실제 밭의 모습**입니다."
            )
            for z in range(5):
                st.markdown(f"**[{z+1} 구역]**")
                for r in range(3):
                    cell_cols = st.columns([0.5, 0.5, 0.5, 3])
                    for c in range(3):
                        is_center = r == 1 and c == 1
                        is_weed_here = (
                            st.session_state.get(f"wmap_0_{z}_{r}_{c}", False)
                            or st.session_state.get(f"wmap_1_{z}_{r}_{c}", False)
                            or st.session_state.get(f"wmap_2_{z}_{r}_{c}", False)
                        )

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
        for i in range(3):
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
                # KST 시간을 직접 넣어줌
                c.execute(
                    """
                    INSERT INTO experiments 
                    (fertilizer, crop_type, water_stars, weed_bitmap, weed_removed, unattended_time, 
                     planted_count, star_1, star_2, star_3, star_4, star_5, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fertilizer,
                        crop_type,
                        water_stars,
                        weed_bitmap_val,
                        weed_removed,
                        unattended_time,
                        planted_count,
                        star_1,
                        star_2,
                        star_3,
                        star_4,
                        star_5,
                        get_kst_now(),  # 한국 시간
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
            f_fert = st.sidebar.selectbox("비료 유무", ["전체", "사용(O)", "미사용(X)"])
            f_crop = st.sidebar.selectbox(
                "작물 종류", ["전체"] + list(df["crop_type"].unique())
            )
            f_water = st.sidebar.multiselect(
                "물 별 개수", options=[1, 2, 3, 4, 5], default=[1, 2, 3, 4, 5]
            )
            f_weed_map = st.sidebar.selectbox(
                "잡초 생성 비트맵 (3-bit)", ["전체"] + list(df["weed_bitmap"].unique())
            )
            f_weed_rm = st.sidebar.selectbox(
                "잡초 제거", ["전체", "제거함(O)", "방치함(X)"]
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
        df_all = pd.read_sql_query(
            "SELECT * FROM experiments ORDER BY id DESC",
            conn,
        )
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

elif app_mode == "🍳 요리 실험":
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
                st.write("완성된 요리의 성급별 개수를 입력하세요.")
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
                    # KST 시간을 직접 넣어줌
                    c.execute(
                        """
                        INSERT INTO cooking_experiments 
                        (recipe_name, cook_count, star_1, star_2, star_3, star_4, star_5, timestamp) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            final_recipe_name,
                            cook_count,
                            c_star_1,
                            c_star_2,
                            c_star_3,
                            c_star_4,
                            c_star_5,
                            get_kst_now(),  # 한국 시간
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
            f_recipe = st.sidebar.selectbox(
                "레시피 이름", ["전체"] + list(df_cook["recipe_name"].unique())
            )

            filtered_cook = df_cook.copy()
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
            "SELECT * FROM cooking_experiments ORDER BY id DESC",
            conn,
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

elif app_mode == "🍎 과일 채집 실험":
    st.title("🍎 두두타 과일 채집 효율 트래커")
    tab1, tab2, tab3 = st.tabs(
        ["채집 데이터 입력", "채집 효율 분석", "채집 데이터 관리(삭제)"]
    )

    def save_foraging_data():
        duration_m = st.session_state["f_min"]
        duration_s = st.session_state["f_sec"]
        duration = duration_m + (duration_s / 60.0)

        if duration <= 0:
            st.session_state["f_error"] = "소요 시간은 0초보다 길어야 합니다!"
            return

        conn = get_connection()
        c = conn.cursor()
        # KST 시간을 직접 넣어줌
        c.execute(
            """
            INSERT INTO foraging_experiments 
            (rainbow_buff, duration_minutes, apples_count, blueberries_count, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                st.session_state["f_rainbow"],
                duration,
                st.session_state["f_apples"],
                st.session_state["f_blue"],
                get_kst_now(),  # 한국 시간
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
            total_m = int(total_time)
            total_s = int(round((total_time - total_m) * 60))

            total_apples = df_foraging["apples_count"].sum()
            total_blueberries = df_foraging["blueberries_count"].sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("총 누적 채집 시간", f"{total_m}분 {total_s}초")
            c2.metric("총 획득 사과", f"{total_apples:,} 개")
            c3.metric("총 획득 블루베리", f"{total_blueberries:,} 개")

            st.divider()
            st.subheader("📊 버프 유무에 따른 분당 획득량 비교")

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

            def format_time(minutes_float):
                m = int(minutes_float)
                s = int(round((minutes_float - m) * 60))
                return f"{m}분 {s}초"

            grouped["formatted_time"] = grouped["duration_minutes"].apply(format_time)

            display_df = grouped[
                [
                    "buff_status",
                    "formatted_time",
                    "apples_count",
                    "blueberries_count",
                    "apple_per_min",
                    "blueberry_per_min",
                    "total_per_min",
                ]
            ].copy()

            display_df.rename(
                columns={
                    "buff_status": "무지개 버프",
                    "formatted_time": "총 소요 시간",
                    "apples_count": "총 사과(개)",
                    "blueberries_count": "총 블루베리(개)",
                    "apple_per_min": "사과 효율 (개/분)",
                    "blueberry_per_min": "블루베리 효율 (개/분)",
                    "total_per_min": "전체 효율 (개/분)",
                },
                inplace=True,
            )

            st.dataframe(
                display_df.style.format(
                    {
                        "사과 효율 (개/분)": "{:.2f}",
                        "블루베리 효율 (개/분)": "{:.2f}",
                        "전체 효율 (개/분)": "{:.2f}",
                    }
                ),
                use_container_width=True,
            )

            fig_f = go.Figure()
            fig_f.add_trace(
                go.Bar(
                    x=grouped["buff_status"],
                    y=grouped["apple_per_min"],
                    name="사과 (개/분)",
                    marker_color="#FF6347",
                    text=[f"{v:.2f}개/분" for v in grouped["apple_per_min"]],
                    textposition="auto",
                )
            )
            fig_f.add_trace(
                go.Bar(
                    x=grouped["buff_status"],
                    y=grouped["blueberry_per_min"],
                    name="블루베리 (개/분)",
                    marker_color="#4682B4",
                    text=[f"{v:.2f}개/분" for v in grouped["blueberry_per_min"]],
                    textposition="auto",
                )
            )
            fig_f.update_layout(
                title="무지개 버프 상태별 분당 채집 효율 비교",
                xaxis_title="버프 상태",
                yaxis_title="효율 (개/분)",
                barmode="group",
            )
            st.plotly_chart(fig_f, use_container_width=True)

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
                st.success(
                    f"ID {delete_f_id} 채집 데이터가 삭제되었습니다. 새로고침을 해주세요."
                )
                st.rerun()

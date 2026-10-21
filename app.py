import pandas as pd
import streamlit as st
import plotly.express as px

# 1. 화면 기본 설정
st.set_page_config(
    page_title="철도 데이터 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = "/content/drive/MyDrive/데이터분석/analysis_result.csv"
DEFAULT_NOTE = "센서 상태와 운전 조건을 확인한 후 담당자 검토가 필요합니다."


# 2. 데이터 읽기: 반복 조회 시 CSV를 매번 다시 읽지 않도록 캐시
@st.cache_data(show_spinner=False)
def load_data(path):
    data = pd.read_csv(path)

    required = [
        "설비ID", "측정시각", "목표시각", "AI결과",
        "온도_C", "다음온도_C", "AI예측온도_C",
    ]

    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError("필수 열이 없습니다: " + ", ".join(missing))

    for column in ["측정시각", "목표시각"]:
        data[column] = pd.to_datetime(data[column], errors="coerce")

    for column in ["온도_C", "다음온도_C", "AI예측온도_C"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        data[column] = data[column].replace(
            [float("inf"), float("-inf")], float("nan")
        )

    return data


# 표의 높이와 너비를 통일
def show_table(data, height=260):
    st.dataframe(
        data,
        height=height,
        hide_index=True,
        use_container_width=True,
    )


# 그래프의 높이와 여백을 통일
def show_chart(fig):
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=35, b=10),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.12,
            x=0,
            title_text="",
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


# 3. 제목과 사이드바
st.title("철도 데이터 분석 대시보드")
st.caption("교육용 가상 자료입니다. AI 확인후보는 고장 확정이 아닙니다.")

st.sidebar.header("조회 조건")

if st.sidebar.button("데이터 새로 읽기"):
    load_data.clear()

st.sidebar.caption("CSV 파일을 수정한 뒤에는 위 버튼을 눌러 주세요.")

try:
    df = load_data(DATA_PATH)
except (OSError, ValueError, pd.errors.ParserError) as error:
    st.error(f"데이터를 읽을 수 없습니다: {error}")
    st.stop()

# 조회에 필요한 기본 정보가 없는 행 제외
invalid_rows = df["설비ID"].isna() | df["측정시각"].isna()

if invalid_rows.any():
    st.sidebar.warning(
        f"설비ID 또는 측정시각이 없는 {invalid_rows.sum():,}행은 조회에서 제외했습니다."
    )

df = df.loc[~invalid_rows].copy()

if df.empty:
    st.warning("조회할 수 있는 데이터가 없습니다. CSV 파일을 확인하세요.")
    st.stop()

# 설비 선택
equipment = st.sidebar.selectbox(
    "설비 선택",
    df["설비ID"].unique(),
)

equipment_view = df[df["설비ID"] == equipment].copy()

min_date = equipment_view["측정시각"].min().date()
max_date = equipment_view["측정시각"].max().date()

# 설비와 자료 범위가 달라지면 해당 범위로 날짜 선택을 초기화
date_key = f"{equipment}_{min_date}_{max_date}"
start_key = f"start_{date_key}"
end_key = f"end_{date_key}"

if st.sidebar.button("전체 기간으로 초기화"):
    st.session_state[start_key] = min_date
    st.session_state[end_key] = max_date

start = st.sidebar.date_input(
    "시작일",
    value=min_date,
    min_value=min_date,
    max_value=max_date,
    key=start_key,
)

end = st.sidebar.date_input(
    "종료일",
    value=max_date,
    min_value=min_date,
    max_value=max_date,
    key=end_key,
)

if start is None or end is None:
    st.sidebar.warning("시작일과 종료일을 모두 선택하세요.")
    st.stop()

if start > end:
    st.sidebar.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

st.sidebar.caption(f"자료 보유 기간: {min_date} ~ {max_date}")
st.sidebar.caption(
    "기간은 측정시각 기준이며, 시작일과 종료일을 모두 포함합니다."
)

# 선택한 기간 조회
dates = equipment_view["측정시각"].dt.date

view = equipment_view[
    (dates >= start) & (dates <= end)
].sort_values("측정시각").copy()

st.caption(
    f"선택 설비: {equipment}  |  조회 기간: {start} ~ {end}"
)

if view.empty:
    st.warning("조회 결과가 없습니다. 사이드바에서 날짜를 다시 선택하세요.")
    st.stop()


# 4. 공통 계산과 상단 요약 지표
candidates = view[view["AI결과"] == "확인후보"].copy()

pred = view.dropna(
    subset=["다음온도_C", "AI예측온도_C"]
).copy()

pred["절대오차_C"] = (
    pred["다음온도_C"] - pred["AI예측온도_C"]
).abs()

mae = pred["절대오차_C"].mean() if not pred.empty else None
mae_text = f"{mae:.2f} ℃" if mae is not None else "계산 불가"

candidate_rate = len(candidates) / len(view) * 100

m1, m2, m3, m4 = st.columns(4)

m1.metric("조회 건수", f"{len(view):,}건")
m2.metric("AI 확인후보", f"{len(candidates):,}건")

m3.metric(
    "확인후보 비율",
    f"{candidate_rate:.1f}%",
    help="조회 행 중 확인후보인 행의 비율입니다. 고장 확률이 아닙니다.",
)

m4.metric(
    "온도 예측 MAE",
    mae_text,
    help=f"실제 온도와 예측 온도가 모두 있는 {len(pred):,}건을 비교했습니다.",
)

# 기존 3개 탭 유지
tab1, tab2, tab3 = st.tabs([
    "AI 점검 후보",
    "다음 1시간 온도 예측",
    "업무 검토 및 저장",
])


# 5. 탭 1: 그래프와 결과 요약을 가로 배치
with tab1:
    chart_col, summary_col = st.columns([3, 1])

    with chart_col:
        st.markdown("**온도 추이와 AI 확인후보**")

        if view["온도_C"].notna().any():
            fig = px.line(
                view,
                x="측정시각",
                y="온도_C",
                labels={
                    "측정시각": "측정 시각",
                    "온도_C": "온도 (℃)",
                },
            )

            fig.add_scatter(
                x=candidates["측정시각"],
                y=candidates["온도_C"],
                mode="markers",
                name="확인후보",
                marker=dict(color="red", size=9),
            )

            show_chart(fig)

        else:
            st.info("그래프에 표시할 온도 자료가 없습니다.")

    with summary_col:
        st.markdown("**AI 결과별 건수**")

        counts = (
            view["AI결과"]
            .fillna("미분류")
            .value_counts()
            .rename_axis("AI결과")
            .reset_index(name="건수")
        )

        show_table(counts, height=200)

        if candidates.empty:
            st.info("선택 기간에 AI 확인후보가 없습니다.")

        else:
            last_candidate = candidates["측정시각"].max()
            st.caption(
                f"최근 확인후보: {last_candidate:%Y-%m-%d %H:%M}"
            )

    # 상세 표는 기본적으로 접어두기
    with st.expander(
        f"AI 점검 후보 상세 보기 · {len(candidates):,}건"
    ):
        show_table(candidates)


# 6. 탭 2: 그래프와 오차 요약을 가로 배치
with tab2:
    st.caption(
        "CSV에 저장된 실제·예측 값을 비교합니다. "
        "조회 기준은 측정시각이고, 그래프의 가로축은 목표시각입니다."
    )

    if pred.empty:
        st.info(
            "실제 온도와 예측 온도가 모두 있는 자료가 없어 MAE를 계산할 수 없습니다."
        )

    else:
        chart_col, summary_col = st.columns([3, 1])

        plot_pred = (
            pred.dropna(subset=["목표시각"])
            .sort_values("목표시각")
        )

        with chart_col:
            st.markdown("**실제 온도와 AI 예측 온도**")

            if plot_pred.empty:
                st.info(
                    "유효한 목표시각이 없어 그래프를 표시할 수 없습니다."
                )

            else:
                plot_data = plot_pred.rename(columns={
                    "다음온도_C": "실제 온도",
                    "AI예측온도_C": "AI 예측 온도",
                })

                fig2 = px.line(
                    plot_data,
                    x="목표시각",
                    y=["실제 온도", "AI 예측 온도"],
                    markers=True,
                    labels={
                        "목표시각": "예측 대상 시각",
                        "value": "온도 (℃)",
                        "variable": "구분",
                    },
                )

                show_chart(fig2)

        with summary_col:
            st.markdown("**예측 비교 요약**")

            st.metric("비교 자료", f"{len(pred):,}건")
            st.metric(
                "최대 절대 오차",
                f"{pred['절대오차_C'].max():.2f} ℃",
            )

            if len(plot_pred) < len(pred):
                st.caption(
                    f"목표시각이 없는 {len(pred) - len(plot_pred):,}건은 "
                    "그래프에서만 제외했습니다. MAE에는 포함됩니다."
                )

        with st.expander(
            f"실제·예측 비교 데이터 보기 · {len(pred):,}건"
        ):
            show_table(
                pred[[
                    "측정시각",
                    "목표시각",
                    "다음온도_C",
                    "AI예측온도_C",
                    "절대오차_C",
                ]].sort_values("목표시각")
            )


# 7. 탭 3: 메모와 보고서 나란히 표시
with tab3:
    note_col, report_col = st.columns(2)

    # 현재 세션에서 설비별 메모 유지
    notes = st.session_state.setdefault("equipment_notes", {})

    with note_col:
        note = st.text_area(
            "확인할 사항 및 조치 제안",
            value=notes.get(str(equipment), DEFAULT_NOTE),
            height=240,
            key=f"note_{equipment}",
            help="메모 수정 후 입력창 밖을 클릭하면 보고서에 반영됩니다.",
        )

        notes[str(equipment)] = note

        st.caption(
            "메모는 현재 세션에서 유지됩니다. "
            "영구 보관은 보고서 TXT를 이용하세요."
        )

    report = f"""설비: {equipment}
조회 기간: {start} ~ {end} (측정시각 기준, 양 끝 날짜 포함)
조회 건수: {len(view):,}건
AI 확인후보: {len(candidates):,}건 ({candidate_rate:.1f}%)
온도 예측 MAE: {mae_text} ({len(pred):,}건 비교)

업무 메모:
{note}

교육용 가상 자료이며, 확인후보는 고장 확정이 아닙니다."""

    with report_col:
        st.text_area(
            "보고서 미리보기",
            value=report,
            height=240,
            disabled=True,
        )

    # 다운로드 버튼 가로 배치
    # CSV는 현재 조회 결과의 전체 열을 저장
    d1, d2, d3 = st.columns(3)

    d1.download_button(
        "조회 결과 CSV",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="dashboard_result.csv",
        mime="text/csv",
        use_container_width=True,
    )

    d2.download_button(
        "점검 후보 CSV",
        data=candidates.to_csv(index=False).encode("utf-8-sig"),
        file_name="inspection_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )

    d3.download_button(
        "보고서 TXT",
        data=report.encode("utf-8-sig"),
        file_name="dashboard_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # 전체 데이터는 메모와 저장 작업을 방해하지 않도록 아래에 배치
    with st.expander(
        f"전체 조회 결과 보기 · {len(view):,}건"
    ):
        show_table(view)

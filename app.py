import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ── ページ設定 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ARK Dashboard",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── モバイル最適化スタイル ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
      html, body, [class*="css"] {
        font-family: 'SF Pro Display', 'Helvetica Neue', sans-serif;
      }

      .block-container {
        padding: 1.5rem 1.2rem 4rem 1.2rem;
        max-width: 480px;
      }

      .date-heading {
        font-size: 1.05rem;
        font-weight: 600;
        color: #8b8b8b;
        letter-spacing: 0.06em;
        margin-bottom: 0.2rem;
      }

      .category-card {
        background: #f8f8f8;
        border-radius: 14px;
        padding: 1rem 1.1rem 0.6rem 1.1rem;
        margin-bottom: 0.9rem;
        border: 1px solid #efefef;
      }

      .category-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: #aaa;
        text-transform: uppercase;
        margin-bottom: 0.55rem;
      }

      .stCheckbox label {
        font-size: 0.97rem !important;
        color: #1a1a1a;
      }

      div[data-testid="stButton"] > button {
        width: 100%;
        padding: 0.85rem 0;
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        border-radius: 14px;
        background: #1a1a1a;
        color: #ffffff;
        border: none;
        margin-top: 0.5rem;
        transition: opacity 0.15s;
      }
      div[data-testid="stButton"] > button:hover {
        opacity: 0.82;
      }

      .stSpinner { text-align: center; }

      div[data-testid="stSuccess"] {
        border-radius: 12px;
      }

      /* タブ */
      button[data-baseweb="tab"] {
        font-size: 0.9rem;
        font-weight: 600;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 設定 ────────────────────────────────────────────────────────────────────
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID  = st.secrets["DATABASE_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

CATEGORIES = [
    {
        "key":         "W",
        "plan_prop":   "【W】予定タスク",
        "actual_prop": "【W】実績",
        "score_prop":  "【W】スコア",
        "label":       "Wellness",
        "color":       "#4C9BE8",
    },
    {
        "key":         "C",
        "plan_prop":   "【C】予定タスク",
        "actual_prop": "【C】実績",
        "score_prop":  "【C】スコア",
        "label":       "Communication",
        "color":       "#56C4A0",
    },
    {
        "key":         "Ca",
        "plan_prop":   "【Ca】予定タスク",
        "actual_prop": "【Ca】実績",
        "score_prop":  "【Ca】スコア",
        "label":       "Career",
        "color":       "#F4A261",
    },
    {
        "key":         "I",
        "plan_prop":   "【I】予定タスク",
        "actual_prop": "【I】実績",
        "score_prop":  "【I】スコア",
        "label":       "Input",
        "color":       "#E07FA0",
    },
]

# ── ユーティリティ ──────────────────────────────────────────────────────────

def get_today_str() -> str:
    return datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d")


def fetch_today_page(today: str) -> dict | None:
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Date",
            "title": {"equals": today},
        },
        "page_size": 1,
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def fetch_week_pages(today: str) -> list[dict]:
    """今日を含む過去7日間のページを全件取得する。"""
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    dates = [
        (today_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    # title equals は OR でまとめられないため、該当ページを一括取得して Python 側でフィルタ
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    pages: list[dict] = []
    has_more = True
    cursor = None

    while has_more:
        payload: dict = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for page in data.get("results", []):
            title_items = (
                page.get("properties", {})
                    .get("Date", {})
                    .get("title", [])
            )
            date_str = title_items[0]["plain_text"] if title_items else ""
            if date_str in dates:
                pages.append(page)
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    return pages


def get_multiselect_names(page: dict, prop_name: str) -> list[str]:
    prop = page.get("properties", {}).get(prop_name, {})
    return [item["name"] for item in prop.get("multi_select", [])]


def get_number(page: dict, prop_name: str) -> float | None:
    prop = page.get("properties", {}).get(prop_name, {})
    return prop.get("number")


def save_actuals(page_id: str, actuals: dict[str, list[str]]) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {
        prop: {"multi_select": [{"name": name} for name in names]}
        for prop, names in actuals.items()
    }
    resp = requests.patch(url, headers=HEADERS, json={"properties": properties}, timeout=10)
    resp.raise_for_status()


# ── タブ1: 実績入力 ──────────────────────────────────────────────────────────

def render_input_tab(today: str) -> None:
    with st.spinner("Notionと同期中…"):
        try:
            page = fetch_today_page(today)
        except requests.RequestException as e:
            st.error(f"Notion API エラー: {e}")
            return

    if page is None:
        st.warning("今日のページが見つかりません。\nNotionデータベースを確認してください。")
        return

    page_id = page["id"]

    st.markdown("**今日の予定タスク**")
    st.markdown("")

    checked: dict[str, list[str]] = {}
    has_any_task = False

    for cat in CATEGORIES:
        tasks = get_multiselect_names(page, cat["plan_prop"])
        if not tasks:
            continue

        has_any_task = True
        checked[cat["actual_prop"]] = []

        st.markdown(
            f'<div class="category-card">'
            f'<div class="category-label">{cat["label"]}</div>',
            unsafe_allow_html=True,
        )
        for task in tasks:
            if st.checkbox(task, key=f"{cat['key']}_{task}"):
                checked[cat["actual_prop"]].append(task)
        st.markdown("</div>", unsafe_allow_html=True)

    if not has_any_task:
        st.info("今日の予定タスクはありません。")
        return

    st.markdown("")
    if st.button("SAVE　→　実績を記録"):
        with st.spinner("保存中…"):
            try:
                save_actuals(page_id, checked)
            except requests.RequestException as e:
                st.error(f"保存に失敗しました: {e}")
                return
        st.success("実績を記録しました！")
        st.balloons()


# ── タブ2: 週間レポート ───────────────────────────────────────────────────────

def render_report_tab(today: str) -> None:
    with st.spinner("週間データを取得中…"):
        try:
            pages = fetch_week_pages(today)
        except requests.RequestException as e:
            st.error(f"Notion API エラー: {e}")
            return

    if not pages:
        st.info("過去7日間のデータがありません。")
        return

    # カテゴリごとにスコアを集計
    scores: dict[str, list[float]] = {cat["label"]: [] for cat in CATEGORIES}
    for page in pages:
        for cat in CATEGORIES:
            val = get_number(page, cat["score_prop"])
            if val is not None:
                scores[cat["label"]].append(val)

    # 平均スコアを計算
    averages: dict[str, float | None] = {
        cat["label"]: (
            round(sum(scores[cat["label"]]) / len(scores[cat["label"]]), 1)
            if scores[cat["label"]] else None
        )
        for cat in CATEGORIES
    }

    st.markdown(f"**集計期間:** 過去7日間（{len(pages)}件）")
    st.markdown("")

    # ── メトリクスカード（2×2グリッド）
    col1, col2 = st.columns(2)
    cols = [col1, col2, col1, col2]

    for i, cat in enumerate(CATEGORIES):
        avg = averages[cat["label"]]
        display = f"{avg}" if avg is not None else "—"
        with cols[i]:
            st.metric(
                label=f"**{cat['label']}** スコア（平均）",
                value=display,
            )

    st.markdown("")
    st.divider()

    # ── バーチャート
    st.markdown("**カテゴリ別 平均スコア**")

    chart_data: dict[str, list] = {"カテゴリ": [], "平均スコア": []}
    for cat in CATEGORIES:
        avg = averages[cat["label"]]
        if avg is not None:
            chart_data["カテゴリ"].append(cat["label"])
            chart_data["平均スコア"].append(avg)

    if chart_data["カテゴリ"]:
        import pandas as pd
        df = pd.DataFrame(chart_data).set_index("カテゴリ")
        st.bar_chart(df, use_container_width=True, height=220)
    else:
        st.info("スコアデータがまだ記録されていません。")

    # ── 日別スコア詳細テーブル
    st.markdown("")
    st.divider()
    st.markdown("**日別スコア詳細**")

    rows = []
    for page in sorted(
        pages,
        key=lambda p: (
            p.get("properties", {}).get("Date", {}).get("title", [{}])[0].get("plain_text", "")
        ),
        reverse=True,
    ):
        title_items = page.get("properties", {}).get("Date", {}).get("title", [])
        date_str = title_items[0]["plain_text"] if title_items else "—"
        row = {"日付": date_str}
        for cat in CATEGORIES:
            val = get_number(page, cat["score_prop"])
            row[cat["label"]] = val if val is not None else "—"
        rows.append(row)

    if rows:
        import pandas as pd
        st.dataframe(
            pd.DataFrame(rows).set_index("日付"),
            use_container_width=True,
        )


# ── メインアプリ ─────────────────────────────────────────────────────────────

def main():
    today = get_today_str()

    st.markdown(f'<p class="date-heading">{today}</p>', unsafe_allow_html=True)
    st.markdown("## ARK Dashboard 🌿")
    st.divider()

    tab_input, tab_report = st.tabs(["✅ 今日の実績入力", "📊 週間レポート"])

    with tab_input:
        render_input_tab(today)

    with tab_report:
        render_report_tab(today)


if __name__ == "__main__":
    main()

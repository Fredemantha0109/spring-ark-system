import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="ARK Dashboard", page_icon="🌿", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  html, body, [class*="css"] { font-family: 'SF Pro Display', 'Helvetica Neue', sans-serif; }
  .block-container { padding: 1.5rem 1.2rem 4rem 1.2rem; max-width: 480px; }
  .date-heading { font-size: 1.05rem; font-weight: 600; color: #8b8b8b; letter-spacing: 0.06em; margin-bottom: 0.2rem; }
  .category-label { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; color: #aaa; text-transform: uppercase; margin-bottom: 0.4rem; }
  .stCheckbox label { font-size: 0.97rem !important; color: #1a1a1a; }
  div[data-testid="stButton"] > button { width: 100%; padding: 0.85rem 0; font-size: 1rem; font-weight: 700; letter-spacing: 0.1em; border-radius: 14px; background: #1a1a1a; color: #ffffff; border: none; margin-top: 0.5rem; transition: opacity 0.15s; }
  div[data-testid="stButton"] > button:hover { opacity: 0.82; }
  div[data-testid="stSuccess"] { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID  = st.secrets["DATABASE_ID"]
HEADERS = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

CATEGORIES = [
    {"key": "W",  "plan_prop": "【W】予定タスク",  "actual_prop": "【W】実績",  "label": "Wellness"},
    {"key": "C",  "plan_prop": "【C】予定タスク",  "actual_prop": "【C】実績",  "label": "Communication"},
    {"key": "Ca", "plan_prop": "【Ca】予定タスク", "actual_prop": "【Ca】実績", "label": "Career"},
    {"key": "I",  "plan_prop": "【I】予定タスク",  "actual_prop": "【I】実績",  "label": "Input"},
]

def get_today_str():
    return datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d")

def fetch_today_page(today):
    resp = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=HEADERS,
        json={"filter": {"property": "Date", "title": {"equals": today}}, "page_size": 1},
        timeout=10
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None

def fetch_select_options(plan_prop):
    """Notionデータベースから指定プロパティのselect選択肢一覧を取得"""
    resp = requests.get(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}",
        headers=HEADERS,
        timeout=10
    )
    resp.raise_for_status()
    props = resp.json().get("properties", {})
    options = props.get(plan_prop, {}).get("multi_select", {}).get("options", [])
    return [o["name"] for o in options]

def get_base_name(name):
    """🔥を除いたベース名を返す"""
    return name.lstrip("🔥").strip()

def filter_available(options, tasks):
    """追加済みタスクと、その🔥ペアを除外した選択肢を返す"""
    added_bases = {get_base_name(t) for t in tasks}
    return [o for o in options if get_base_name(o) not in added_bases]

def get_multiselect_names(page, prop_name):
    return [item["name"] for item in page.get("properties", {}).get(prop_name, {}).get("multi_select", [])]

def save_plan_and_actuals(page_id, plans, actuals):
    properties = {}
    for prop, names in {**plans, **actuals}.items():
        properties[prop] = {"multi_select": [{"name": n} for n in names]}
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"properties": properties},
        timeout=10
    )
    resp.raise_for_status()

def main():
    today = get_today_str()
    st.markdown(f'<p class="date-heading">{today}</p>', unsafe_allow_html=True)
    st.markdown("## ARK Dashboard 🌿")
    st.divider()

    with st.spinner("Notionと同期中…"):
        try:
            page = fetch_today_page(today)
        except requests.RequestException as e:
            st.error(f"Notion API エラー: {e}")
            return

    if page is None:
        st.warning("今日のページが見つかりません。Notionデータベースを確認してください。")
        return

    page_id = page["id"]

    # セッションステート初期化（初回のみ）
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        for cat in CATEGORIES:
            st.session_state[f"tasks_{cat['key']}"]   = get_multiselect_names(page, cat["plan_prop"])
            st.session_state[f"actuals_{cat['key']}"] = set(get_multiselect_names(page, cat["actual_prop"]))
            # Notionから選択肢を取得
            st.session_state[f"options_{cat['key']}"] = fetch_select_options(cat["plan_prop"])

    st.markdown("**今日のタスク**")
    st.markdown("")

    for cat in CATEGORIES:
        tasks   = st.session_state[f"tasks_{cat['key']}"]
        actuals = st.session_state[f"actuals_{cat['key']}"]
        options = st.session_state[f"options_{cat['key']}"]

        # 追加済みタスクと🔥ペアを除いた選択肢
        available = filter_available(options, tasks)

        st.markdown(f'<div class="category-label">{cat["label"]}</div>', unsafe_allow_html=True)

        # タスク一覧（チェック＋削除）
        for task in list(tasks):
            col_chk, col_del = st.columns([5, 1])
            with col_chk:
                checked = st.checkbox(task, value=(task in actuals), key=f"chk_{cat['key']}_{task}")
                if checked:
                    actuals.add(task)
                else:
                    actuals.discard(task)
            with col_del:
                if st.button("✕", key=f"del_{cat['key']}_{task}"):
                    tasks.remove(task)
                    actuals.discard(task)
                    st.rerun()

        # タスク追加（Notionの選択肢からドロップダウン、なければテキスト入力）
        col_sel, col_add = st.columns([5, 1])
        if available:
            with col_sel:
                selected = st.selectbox(
                    "追加",
                    options=["-- タスクを選択 --"] + available,
                    key=f"sel_{cat['key']}",
                    label_visibility="collapsed"
                )
            with col_add:
                if st.button("＋", key=f"add_{cat['key']}"):
                    if selected != "-- タスクを選択 --":
                        tasks.append(selected)
                        st.rerun()
        else:
            with col_sel:
                new_task = st.text_input("追加", key=f"input_{cat['key']}", label_visibility="collapsed", placeholder=f"{cat['label']}のタスクを追加…")
            with col_add:
                if st.button("＋", key=f"add_{cat['key']}"):
                    if new_task.strip() and new_task.strip() not in tasks:
                        tasks.append(new_task.strip())
                        st.rerun()

        st.markdown("---")

    if st.button("SAVE　→　実績を記録"):
        with st.spinner("保存中…"):
            try:
                plans   = {cat["plan_prop"]:  st.session_state[f"tasks_{cat['key']}"] for cat in CATEGORIES}
                actuals = {cat["actual_prop"]: list(st.session_state[f"actuals_{cat['key']}"]) for cat in CATEGORIES}
                save_plan_and_actuals(page_id, plans, actuals)
            except requests.RequestException as e:
                st.error(f"保存に失敗しました: {e}")
                return
        st.success("実績を記録しました！")
        st.balloons()
        del st.session_state["initialized"]

if __name__ == "__main__":
    main()
"""
calc_score.py — 昨日のカテゴリスコアを算出してNotionに書き込む

実行タイミング:
  朝のiOSショートカット → GitHub /dispatches (trigger_scoring)
  → main.yml 内で scoring.py の後に実行される

スコアリング仕様:
  - 🔥絵文字が含まれるタスクは「優先タスク」(配点2倍)
  - 基準配点 = 100 / (通常数 + 優先数 * 2)
  - 予定タスクが0の日はスコア書き込みをスキップ (N/A)
  - 実績が予定を超えても上限100点
  - 小数第1位までに丸める

CLI実行時は「昨日」のスコアを確定させる。
関数は純関数として切り出してあるので、将来的に app.py からも再利用可能。
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ── 環境変数 ────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["DATABASE_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ── カテゴリ定義 (app.py と同じ構造) ─────────────────────────────────────────
CATEGORIES = [
    {"key": "W",  "plan_prop": "【W】予定タスク",  "actual_prop": "【W】実績",  "score_prop": "【W】スコア",  "label": "Wellness"},
    {"key": "C",  "plan_prop": "【C】予定タスク",  "actual_prop": "【C】実績",  "score_prop": "【C】スコア",  "label": "Communication"},
    {"key": "Ca", "plan_prop": "【Ca】予定タスク", "actual_prop": "【Ca】実績", "score_prop": "【Ca】スコア", "label": "Career"},
    {"key": "I",  "plan_prop": "【I】予定タスク",  "actual_prop": "【I】実績",  "score_prop": "【I】スコア",  "label": "Input"},
]

PRIORITY_EMOJI = "🔥"


# ── 純関数: スコア計算ロジック ──────────────────────────────────────────────

def is_priority(task_name: str) -> bool:
    """タスク名に🔥絵文字が含まれていれば優先タスク。"""
    return PRIORITY_EMOJI in task_name


def calculate_category_score(
    plan_tasks: list[str],
    actual_tasks: list[str],
) -> float:
    """
    単一カテゴリのスコアを算出する純関数。

    Args:
        plan_tasks: 予定タスク名のリスト
        actual_tasks: 実績タスク名のリスト

    Returns:
        0〜100の数値。予定が空の場合は None (N/A)。
    """
    # 予定0の日はN/A
    if not plan_tasks:
        return None

    # 優先タスクと通常タスクに分ける
    priority_plans = [t for t in plan_tasks if is_priority(t)]
    normal_plans = [t for t in plan_tasks if not is_priority(t)]

    # 按分の分母
    denominator = len(normal_plans) + len(priority_plans) * 2
    if denominator == 0:  # 理論上ここには来ないが安全策
        return None

    base_point = 100 / denominator
    priority_point = base_point * 2

    # 実績セット(文字列完全一致で判定)
    actual_set = set(actual_tasks)

    score = 0.0
    for task in priority_plans:
        if task in actual_set:
            score += priority_point
    for task in normal_plans:
        if task in actual_set:
            score += base_point

    # 上限100点・小数第1位
    return round(min(score, 100.0), 1)


# ── Notion API ラッパー ─────────────────────────────────────────────────────

def get_page_by_date(date_str: str) -> dict:
    """指定日付(YYYY-MM-DD)のページを取得。"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {"property": "Date", "title": {"equals": date_str}},
        "page_size": 1,
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def get_multiselect_names(page: dict, prop_name: str) -> list[str]:
    prop = page.get("properties", {}).get(prop_name, {})
    return [item["name"] for item in prop.get("multi_select", [])]


def update_page_scores(page_id: str, scores: dict[str, float]) -> None:
    """
    指定ページの複数スコアプロパティを一括更新。

    Args:
        page_id: Notion ページID
        scores: {"【W】スコア": 75.0, "【C】スコア": 33.3, ...}
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    properties = {
        prop_name: {"number": value}
        for prop_name, value in scores.items()
    }
    resp = requests.patch(url, headers=HEADERS, json={"properties": properties}, timeout=10)
    resp.raise_for_status()


# ── メイン処理 ──────────────────────────────────────────────────────────────

def update_scores_for_date(date_str: str) -> dict:
    """
    指定日のページを取得し、4カテゴリのスコアを計算してNotionに書き込む。

    Returns:
        {"Wellness": 75.0, "Communication": None, ...} 形式
    """
    page = get_page_by_date(date_str)
    if page is None:
        print(f"[WARN] {date_str} のページが見つかりません。")
        return {}

    page_id = page["id"]
    results: dict = {}
    scores_to_write: dict = {}

    for cat in CATEGORIES:
        plan = get_multiselect_names(page, cat["plan_prop"])
        actual = get_multiselect_names(page, cat["actual_prop"])
        score = calculate_category_score(plan, actual)

        results[cat["label"]] = score

        # N/A(None)は書き込まない。それ以外は上書き
        if score is not None:
            scores_to_write[cat["score_prop"]] = score

    if scores_to_write:
        update_page_scores(page_id, scores_to_write)

    return results


def main():
    # 昨日の日付(SGT基準)
    yesterday = (datetime.now(ZoneInfo("Asia/Singapore")) - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[INFO] スコア計算対象日: {yesterday}")

    try:
        results = update_scores_for_date(yesterday)
    except requests.RequestException as e:
        print(f"[ERROR] Notion API エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 予期せぬエラー: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("[WARN] 該当ページがないため処理をスキップしました。")
        return

    # 結果ログ
    print(f"[OK] {yesterday} のスコアを更新しました:")
    for label, score in results.items():
        display = f"{score}点" if score is not None else "N/A (予定なし)"
        print(f"  - {label}: {display}")


if __name__ == "__main__":
    main()

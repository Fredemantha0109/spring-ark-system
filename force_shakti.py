"""
force_shakti.py — 今日のNotionページの【MIND】予定タスクに🔥Shaktiを強制追加する

GitHub Actions (force_shakti.yml) から呼び出される。
- 「Shakti」が既にあれば削除して「🔥Shakti」を追加
- 「🔥Shakti」が既にあれば何もしない
- どちらもなければ「🔥Shakti」を追加
"""

import os
import sys
import requests

from ark_config import HABIT_PLAN_PROPS, today_jst

NOTION_TOKEN = os.environ["NOTION_API_TOKEN"]
DATABASE_ID  = os.environ["NOTION_DATABASE_ID"]
PROP_KEY     = HABIT_PLAN_PROPS["mind"]  # 【MIND】予定タスク

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

today = today_jst()

# ── 今日のページを取得 ────────────────────────────
res = requests.post(
    f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
    headers=HEADERS,
    json={"filter": {"property": "Date", "title": {"equals": today}}}
)
pages = res.json().get("results", [])
if not pages:
    print(f"[WARN] {today} のページが見つかりません")
    sys.exit(1)

page    = pages[0]
page_id = page["id"]
props   = page["properties"]

# ── 現在の【MIND】予定タスクを取得 ─────────────────
current_tasks = [t["name"] for t in props.get(PROP_KEY, {}).get("multi_select", [])]
print(f"[INFO] 現在の{PROP_KEY}: {current_tasks}")

# ── 既に🔥Shaktiが入っていれば何もしない ──────────
if "\U0001f525Shakti" in current_tasks:
    print("[INFO] 🔥Shakti は既に設定済みです。スキップします。")
    sys.exit(0)

# ── 新しいタスクリストを構築 ──────────────────────
new_tasks = [t for t in current_tasks if t != "Shakti"]  # 「Shakti」を除去
new_tasks.append("\U0001f525Shakti")                       # 🔥Shaktiを追加

# ── Notion PATCH ──────────────────────────────────
patch_res = requests.patch(
    f"https://api.notion.com/v1/pages/{page_id}",
    headers=HEADERS,
    json={
        "properties": {
            PROP_KEY: {
                "multi_select": [{"name": t} for t in new_tasks]
            }
        }
    }
)

if patch_res.status_code == 200:
    print(f"[OK] 🔥Shakti を{PROP_KEY}に追加しました: {new_tasks}")
else:
    print(f"[ERROR] PATCH失敗: {patch_res.status_code} {patch_res.text}")
    sys.exit(1)
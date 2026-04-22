"""
force_priority.py — 指定タスクを🔥付きで該当カテゴリの予定タスクに追加する

GitHub Actions (force_priority.yml) から呼び出される。
client_payload に task_name と category (W/C/Ca/I) を受け取る。
- 同名タスクが既にあれば削除して🔥タスクとして追加
- 🔥タスクが既にあれば何もしない
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta

NOTION_TOKEN = os.environ["NOTION_API_TOKEN"]
DATABASE_ID  = os.environ["NOTION_DATABASE_ID"]
TASK_NAME    = os.environ["TASK_NAME"]      # GitHub Actions経由で渡される
CATEGORY     = os.environ["CATEGORY"]       # W / C / Ca / I

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

PROP_KEY = f"\u3010{CATEGORY}\u3011\u4e88\u5b9a\u30bf\u30b9\u30af"  # 【X】予定タスク
FIRE_TASK = f"\U0001f525{TASK_NAME}"  # 🔥タスク名

sgt   = timezone(timedelta(hours=8))
today = datetime.now(sgt).strftime("%Y-%m-%d")

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

# ── 現在の予定タスクを取得 ────────────────────────
current_tasks = [t["name"] for t in props.get(PROP_KEY, {}).get("multi_select", [])]
print(f"[INFO] 現在の{PROP_KEY}: {current_tasks}")

# 既に🔥タスクが入っていれば何もしない
if FIRE_TASK in current_tasks:
    print(f"[INFO] {FIRE_TASK} は既に設定済みです。スキップします。")
    sys.exit(0)

# 同名タスク（🔥なし）を削除して🔥タスクを追加
new_tasks = [t for t in current_tasks if t != TASK_NAME and t != FIRE_TASK]
new_tasks.append(FIRE_TASK)

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
    print(f"[OK] {FIRE_TASK} を{PROP_KEY}に追加しました: {new_tasks}")
else:
    print(f"[ERROR] PATCH失敗: {patch_res.status_code} {patch_res.text}")
    sys.exit(1)
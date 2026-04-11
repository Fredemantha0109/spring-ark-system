import os
import requests
from datetime import datetime, timedelta, timezone

# Notion API設定
NOTION_TOKEN = os.environ.get("NOTION_API_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# マスター・スケジュール定義（0:月曜 〜 6:日曜）
WEEKLY_TEMPLATE = {
    0: { # 月曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング"],
        "C": ["Scrambled", "SB（月定着）", "Reuse", "OP（月定着）", "語彙（月定着）", "リスニング（月定着）", "Youtube", "シャドーイング（月定着）", "瞬間英作文（月定着）", "定着学習（その他）"],
        "Ca": [],
        "I": ["NewsPicks"]
    },
    1: { # 火曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング"],
        "C": ["ライアン", "SB（火）", "Reuse", "OP（火）", "語彙（火）", "リスニング（火）", "英会話", "瞬間英作文（火）", "Youtube", "語彙（水）", "リスニング（水）", "瞬間英作文（水）"],
        "Ca": [],
        "I": ["NewsPicks"]
    },
    2: { # 水曜
        "W": ["瞑想", "ジャーナリング", "ウォーキング", "Shakti"],
        "C": ["Soccer", "SB（水）", "Reuse", "OP（水）", "Youtube"],
        "Ca": ["AI学習①", "AI学習②"],
        "I": ["NewsPicks"]
    },
    3: { # 木曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング"],
        "C": ["Scrambled", "SB（木）", "Reuse", "OP（木）", "英会話", "語彙（木）", "リスニング（木）", "瞬間英作文（木）", "Youtube", "英会話振り返り"],
        "Ca": [],
        "I": ["NewsPicks"]
    },
    4: { # 金曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング"],
        "C": ["ライアン", "SB（金）", "Reuse", "OP（金）", "語彙（土）", "リスニング（土）", "瞬間英作文（土）", "Youtube"],
        "Ca": [],
        "I": ["NewsPicks"]
    },
    5: { # 土曜
        "W": ["ウォーキング"],
        "C": ["SB（土）", "Reuse", "OP（土）", "OP（日定着）", "語彙（日定着）"],
        "Ca": [],
        "I": ["NewsPicks"]
    },
    6: { # 日曜
        "W": ["ウォーキング"],
        "C": ["SB（日定着）", "リスニング（日定着）", "シャドーイング（日定着）", "瞬間英作文（日定着）"],
        "Ca": [],
        "I": []
    }
}

def create_notion_page(date_str, tasks):
    url = "https://api.notion.com/v1/pages"
    
    # マルチセレクト用のJSON構造を生成するヘルパー関数
    def make_multi_select(task_list):
        return {"multi_select": [{"name": task} for task in task_list]}

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Date": {
                "title": [{"text": {"content": date_str}}]
            },
            "【W】予定タスク": make_multi_select(tasks["W"]),
            "【C】予定タスク": make_multi_select(tasks["C"]),
            "【Ca】予定タスク": make_multi_select(tasks["Ca"]),
            "【I】予定タスク": make_multi_select(tasks["I"])
        }
    }
    
    response = requests.post(url, json=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"✅ Success: {date_str} のページを作成しました。")
    else:
        print(f"❌ Error for {date_str}: {response.status_code}")
        print(response.text)

def main():
    # 実行日の「次の月曜日」を算出
    today = datetime.now(timezone(timedelta(hours=8))) # シンガポール時間(SGT)
    days_ahead = 0 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)

    print(f"🚀 SPRING ARK 週次プランナー自動生成を開始します。({next_monday.date()}の週)")

    # 月曜(0)から日曜(6)までの7日分をループで生成
    for i in range(7):
        target_date = next_monday + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        day_index = target_date.weekday()
        
        # テンプレートからその日のタスクを取得してNotion作成関数に渡す
        tasks = WEEKLY_TEMPLATE[day_index]
        create_notion_page(date_str, tasks)

if __name__ == "__main__":
    main()

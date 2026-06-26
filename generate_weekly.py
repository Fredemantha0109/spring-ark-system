import os
import requests
from datetime import timedelta

from ark_config import (
    ARK_NAME,
    CATEGORIES,
    HABIT_CATEGORIES,
    category_display,
    classify_routine_subcategory,
    now_jst,
)

_SUBCATEGORY_TO_HABIT_KEY = {c["subcategory"]: c["key"] for c in HABIT_CATEGORIES}
_HABIT_PLAN_PROPS = {c["key"]: f"【{c['label']}】予定タスク" for c in HABIT_CATEGORIES}


def split_routine_tasks(w_tasks):
    """WEEKLY_TEMPLATE の Routine タスクを習慣4分類の予定タスク用バケットに振り分ける。"""
    buckets = {c["key"]: [] for c in HABIT_CATEGORIES}
    for task in w_tasks:
        subcat = classify_routine_subcategory(task)
        habit_key = _SUBCATEGORY_TO_HABIT_KEY.get(subcat)
        if habit_key is None:
            raise ValueError(
                f"Routine task {task!r} is unclassified (subcategory={subcat!r}). "
                "Update ark_config.ROUTINE_SUBCATEGORIES or WEEKLY_TEMPLATE."
            )
        buckets[habit_key].append(task)
    return buckets

# Notion API設定
NOTION_TOKEN = os.environ.get("NOTION_API_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# マスター・スケジュール定義（0:月曜 〜 6:日曜）
# Summer Ark 柱定義: W=Routine(トレ・TOEIC・英語学習・振り返り) / C=Belonging(人間関係・家族)
#                    Ca=Career(収益基盤・起業) / I=AI(AIスクール・frog・卒業制作)
WEEKLY_TEMPLATE = {
    0: { # 月曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング", "Scrambled", "Youtube", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    1: { # 火曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング", "ライアン", "Youtube", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    2: { # 水曜
        "W": ["瞑想", "ジャーナリング", "ウォーキング", "Shakti", "Youtube", "Soccer", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    3: { # 木曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング", "Scrambled", "Youtube", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    4: { # 金曜
        "W": ["瞑想", "ジャーナリング", "ジム", "Shakti", "ウォーキング", "ライアン", "Youtube", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    5: { # 土曜
        "W": ["ウォーキング", "NewsPicks"],
        "C": [],
        "Ca": [],
        "I": []
    },
    6: { # 日曜
        "W": ["ウォーキング"],
        "C": [],
        "Ca": [],
        "I": []
    }
}

def create_notion_page(date_str, tasks):
    url = "https://api.notion.com/v1/pages"
    
    def make_multi_select(task_list):
        return {"multi_select": [{"name": task} for task in task_list]}

    # --- 新規追加：ページ本文（チェックリスト）を作る処理 ---
    children_blocks = []
    
    # カテゴリの表示名（絵文字つきで見やすくしています）
    categories = [
        (c["key"], category_display(c["key"]))
        for c in CATEGORIES
    ]
    
    for key, title in categories:
        if tasks[key]: # その日にタスクが1つ以上ある場合のみ実行
            # 見出しブロックを追加
            children_blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": title}}]
                }
            })
            # ToDo（チェックボックス）ブロックを追加
            for task in tasks[key]:
                children_blocks.append({
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": task}}],
                        "checked": False # 初期状態は未チェック
                    }
                })

    habit_tasks = split_routine_tasks(tasks["W"])

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Date": {
                "title": [{"text": {"content": date_str}}]
            },
            **{
                _HABIT_PLAN_PROPS[key]: make_multi_select(habit_tasks[key])
                for key in _HABIT_PLAN_PROPS
            },
            "【C】予定タスク": make_multi_select(tasks["C"]),
            "【Ca】予定タスク": make_multi_select(tasks["Ca"]),
            "【I】予定タスク": make_multi_select(tasks["I"]),
        },
        # 本文エリア（children）に作成したブロックリストを渡す
        "children": children_blocks
    }
    
    response = requests.post(url, json=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"✅ Success: {date_str} のページを作成しました。")
    else:
        print(f"❌ Error for {date_str}: {response.status_code}")
        print(response.text)

def main():
    today = now_jst()
    days_ahead = 0 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)

    print(f"🚀 {ARK_NAME} 週次プランナー自動生成を開始します。({next_monday.date()}の週)")

    for i in range(7):
        target_date = next_monday + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        day_index = target_date.weekday()
        
        tasks = WEEKLY_TEMPLATE[day_index]
        create_notion_page(date_str, tasks)

if __name__ == "__main__":
    main()

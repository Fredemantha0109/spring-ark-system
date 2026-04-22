import os
import requests
from datetime import datetime, timedelta

# 環境変数の取得（Secretで設定したもの）
NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['DATABASE_ID']

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_page_by_date(date_str):
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query = {"filter": {"property": "Date", "title": {"equals": date_str}}}
    response = requests.post(url, headers=headers, json=query).json()
    return response['results'][0] if response['results'] else None

def analyze():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    y_page = get_page_by_date(yesterday)
    t_page = get_page_by_date(today)
    
    if not y_page:
        print("昨日のページが見つかりません。スキップします。")
        return
    if not t_page:
        print("今日のページがまだ作成されていません。ショートカット実行後に再試行してください。")
        return

    categories = [
        {"prefix": "W", "name": "Wellness"},
        {"prefix": "C", "name": "Communication"},
        {"prefix": "Ca", "name": "Career"},
        {"prefix": "I", "name": "Input"}
    ]
    
    unfinished = []
    for cat in categories:
        props = y_page['properties']
        sched = [t['name'] for t in props[f"【{cat['prefix']}】予定タスク"]['multi_select']]
        act = [t['name'] for t in props[f"【{cat['prefix']}】実績"]['multi_select']]
        diff = set(sched) - set(act)
        for task in diff:
            unfinished.append(f"{cat['name']}: {task}")

    # メッセージ作成
    if not unfinished:
        msg = "昨日は全タスク達成！完璧です。このリズムを崩さず、今日もARKを加速させましょう。"
    else:
        task_list = "\n・".join(unfinished)
        msg = f"昨日の未達タスクがあります：\n・{task_list}\nこれらを今日の優先タスクに設定し、優先的に消化しましょう。"
    
    # 今日のページに書き込み
    update_url = f"https://api.notion.com/v1/pages/{t_page['id']}"
    data = {"properties": {"AI提案・作戦": {"rich_text": [{"text": {"content": msg}}]}}}
    requests.patch(update_url, headers=headers, json=data)
    print(f"Update complete: {msg}")

if __name__ == "__main__":
    analyze()
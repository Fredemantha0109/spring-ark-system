import os
import requests
from datetime import datetime, timedelta

# 環境変数の取得
NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['DATABASE_ID']

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_yesterday_data():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query = {"filter": {"property": "Date", "title": {"equals": yesterday}}}
    response = requests.post(url, headers=headers, json=query).json()
    return response['results'][0] if response['results'] else None

def analyze_and_propose(yesterday_page):
    # カテゴリ設定
    categories = [
        {"prefix": "W", "name": "Wellness"},
        {"prefix": "C", "name": "Communication"},
        {"prefix": "Ca", "name": "Career"},
        {"prefix": "I", "name": "Input"}
    ]
    
    unfinished_tasks = []
    for cat in categories:
        scheduled = [t['name'] for t in yesterday_page['properties'][f"【{cat['prefix']}】予定タスク"]['multi_select']]
        actual = [t['name'] for t in yesterday_page['properties'][f"【{cat['prefix']}】実績"]['multi_select']]
        
        # 予定にあって実績にないものを抽出
        diff = set(scheduled) - set(actual)
        for task in diff:
            unfinished_tasks.append(f"{cat['name']}: {task}")

    # 作戦の組み立て
    if not unfinished_tasks:
        proposal = "昨日は完璧な達成でした！この調子で今日もARKを加速させましょう。"
    else:
        task_list = "\n・".join(unfinished_tasks)
        proposal = f"昨日の残りタスクがあります：\n・{task_list}\nこれらを今日の優先タスク（🔥）に設定し、午前中に片付ける作戦を推奨します。"
    
    return proposal

def update_today_proposal(proposal):
    today = datetime.now().strftime('%Y-%m-%d')
    # 今日のページを探して更新
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query = {"filter": {"property": "Date", "title": {"equals": today}}}
    pages = requests.post(url, headers=headers, json=query).json()
    
    if pages['results']:
        page_id = pages['results'][0]['id']
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        data = {"properties": {"AI提案・作戦": {"rich_text": [{"text": {"content": proposal}}]}}}
        requests.patch(update_url, headers=headers, json=data)

if __name__ == "__main__":
    yesterday_page = get_yesterday_data()
    if yesterday_page:
        proposal = analyze_and_propose(yesterday_page)
        update_today_proposal(proposal)

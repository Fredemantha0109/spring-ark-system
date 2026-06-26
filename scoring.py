import os
import requests

from ark_config import CATEGORIES, LABEL_BY_KEY, today_jst, yesterday_jst

# 日付は JST 基準。旧実装の datetime.now()（タイムゾーン未指定）は GitHub Actions
# ランナー（UTC）上で日付境界がずれる既存バグがあった。今回の修正で解消する。
# ※過去のスコア確定データの遡及修正は不要。今後の計算から正しくなる。

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
    yesterday = yesterday_jst()
    today = today_jst()
    
    y_page = get_page_by_date(yesterday)
    t_page = get_page_by_date(today)
    
    if not y_page:
        print("昨日のページが見つかりません。スキップします。")
        return
    if not t_page:
        print("今日のページがまだ作成されていません。ショートカット実行後に再試行してください。")
        return

    categories = [
        {"prefix": c["key"], "name": LABEL_BY_KEY[c["key"]]}
        for c in CATEGORIES
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
import os
import requests
from datetime import datetime, timedelta, timezone

NOTION_TOKEN = os.environ.get("NOTION_API_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_yesterday_page():
    # 実行時（朝）から見て「昨日」の日付を取得
    jst = timezone(timedelta(hours=9))
    yesterday = (datetime.now(jst) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query = {
        "filter": {
            "property": "Date",
            "title": {"equals": yesterday}
        }
    }
    res = requests.post(url, json=query, headers=HEADERS).json()
    if res["results"]:
        return res["results"][0]
    return None

def calculate_category_score(page_id, priority_tasks):
    # ページ内のブロック（チェックボックス）を取得
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks = requests.get(url, headers=HEADERS).json().get("results", [])
    
    total_weight = 0
    earned_weight = 0
    
    # 簡易的なカテゴリ判定（見出しの下にあるToDoをカウント）
    # 実際はより詳細な判定が可能ですが、まずは全体のチェック率で計算します
    for block in blocks:
        if block["type"] == "to_do":
            text = block["to_do"]["rich_text"][0]["plain_text"]
            is_checked = block["to_do"]["checked"]
            
            # 優先タスクなら重み2、それ以外は1
            weight = 2 if text in priority_tasks else 1
            total_weight += weight
            if is_checked:
                earned_weight += weight
                
    return (earned_weight / total_weight * 100) if total_weight > 0 else 0

def main():
    page = get_yesterday_page()
    if not page:
        print("Yesterday's page not found.")
        return

    props = page["properties"]
    
    # 各カテゴリの優先タスク（タグ）を取得
    def get_priority(prop_name):
        return [t["name"] for t in props.get(prop_name, {}).get("multi_select", [])]

    w_priority = get_priority("【W】優先タスク")
    c_priority = get_priority("【C】優先タスク")
    # ... 他のカテゴリも同様

    # 本来はカテゴリごとにブロックを分けるべきですが、まずはシンプルに全体集計の例
    score = calculate_category_score(page["id"], w_priority + c_priority)
    
    # Notionの数値プロパティを更新
    update_url = f"https://api.notion.com/v1/pages/{page['id']}"
    update_data = {
        "properties": {
            "Wellness": {"number": score}, # ここに計算した各スコアを入れる
            "総合": {"number": score} 
        }
    }
    requests.patch(update_url, json=update_data, headers=HEADERS)
    print(f"Scoring complete for {page['id']}")

if __name__ == "__main__":
    main()

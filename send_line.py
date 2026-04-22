import os
import requests
import json
from datetime import datetime, timezone, timedelta

def send_line_message(message: str) -> bool:
    token = os.environ.get("LINE_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if not token or not user_id:
        print("LINE credentials not found")
        return False
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print("LINE通知送信成功")
        return True
    else:
        print(f"LINE通知送信失敗: {response.status_code} {response.text}")
        return False

if __name__ == "__main__":
    # Notionから今日のデータを取得
    notion_token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("DATABASE_ID")
    
    # 今日の日付(SGT = UTC+8)
    sgt = timezone(timedelta(hours=8))
    today = (datetime.now(sgt) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Notionクエリ
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    query = {
        "filter": {
            "property": "Date",
            "title": {"equals": today}
        }
    }
    
    res = requests.post(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        headers=headers,
        json=query
    )
    
    pages = res.json().get("results", [])
    if not pages:
        send_line_message(f"⚠️ {today} のデータが見つかりません")
        exit(1)
    
    props = pages[0]["properties"]
    
    # 各スコアを取得
    score_total = props.get("総合スコア", {}).get("formula", {}).get("number", 0) or 0
    score_w = props.get("【W】スコア", {}).get("formula", {}).get("number", 0) or 0
    score_c = props.get("【C】スコア", {}).get("formula", {}).get("number", 0) or 0
    score_ca = props.get("【Ca】スコア", {}).get("formula", {}).get("number", 0) or 0
    score_i = props.get("【I】スコア", {}).get("formula", {}).get("number", 0) or 0
    weight = props.get("体重", {}).get("number")
    sleep = props.get("睡眠時間", {}).get("number")
    condition = props.get("体調", {}).get("select", {})
    condition_name = condition.get("name", "-") if condition else "-"
    
    # 判定絵文字
    if score_total >= 80:
        judge = "🟢 GOOD"
    elif score_total >= 50:
        judge = "🟡 CAUTION"
    else:
        judge = "🔴 ALERT"
    
    # メッセージ作成
    message = f"""🌱 Spring Ark Daily Report
{today} {judge}

📊 総合スコア: {score_total}点
  W: {score_w} / C: {score_c} / Ca: {score_ca} / I: {score_i}

💪 体重: {weight if weight else '-'}kg
😴 睡眠: {sleep if sleep else '-'}h
🌡 体調: {condition_name}"""

    dashboard_url = f"https://{os.environ.get('SURGE_DOMAIN', '')}"
    message += f"\n\n📊 詳細レポート\n{dashboard_url}"
    send_line_message(message)
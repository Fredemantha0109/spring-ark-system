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
    notion_token = os.environ.get("NOTION_TOKEN")
    database_id  = os.environ.get("DATABASE_ID")

    # 日付(SGT = UTC+8) — 今日・昨日の2ページ使い分け
    sgt       = timezone(timedelta(hours=8))
    today     = datetime.now(sgt).strftime("%Y-%m-%d")
    yesterday = (datetime.now(sgt) - timedelta(days=1)).strftime("%Y-%m-%d")

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    def fetch_props(date_str):
        res = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=headers,
            json={"filter": {"property": "Date", "title": {"equals": date_str}}}
        )
        results = res.json().get("results", [])
        return results[0]["properties"] if results else None

    props_today     = fetch_props(today)
    props_yesterday = fetch_props(yesterday)

    if not props_yesterday:
        send_line_message(f"⚠️ {yesterday} のデータが見つかりません")
        exit(1)
    if not props_today:
        props_today = props_yesterday

    # スコアは昨日のページから
    score_total = props_yesterday.get("総合スコア", {}).get("formula", {}).get("number", 0) or 0
    score_w     = props_yesterday.get("【W】スコア",  {}).get("formula", {}).get("number", 0) or 0
    score_c     = props_yesterday.get("【C】スコア",  {}).get("formula", {}).get("number", 0) or 0
    score_ca    = props_yesterday.get("【Ca】スコア", {}).get("formula", {}).get("number", 0) or 0
    score_i     = props_yesterday.get("【I】スコア",  {}).get("formula", {}).get("number", 0) or 0

    # 体重・睡眠・体調は今日のページから
    weight         = props_today.get("体重", {}).get("number")
    sleep_val      = props_today.get("睡眠時間", {}).get("number")
    condition_obj  = props_today.get("体調", {}).get("select") or {}
    condition_name = condition_obj.get("name", "-")

    # 判定（睡眠 × 体調）
    s = sleep_val if isinstance(sleep_val, (int, float)) else 0
    if (s >= 7 and condition_name in ("好調", "普通")) or (5.5 <= s < 7 and condition_name == "好調"):
        judge = "🟢 良好"
    elif (5.5 <= s < 7 and condition_name == "不調") or (s < 5.5 and condition_name in ("普通", "不調")):
        judge = "🔴 危険"
    else:
        judge = "🟡 要注意"

    # メッセージ作成（日付は今日を表示）
    sleep_str  = f"{sleep_val}h" if sleep_val is not None else "-"
    weight_str = f"{weight}kg"   if weight    is not None else "-"

    message = (
        f"🌱 Spring Ark Daily Report\n"
        f"{today} {judge}\n"
        f"\n"
        f"📊 総合スコア: {score_total}点\n"
        f"  W: {score_w} / C: {score_c} / Ca: {score_ca} / I: {score_i}\n"
        f"\n"
        f"💪 体重: {weight_str}\n"
        f"😴 睡眠: {sleep_str}\n"
        f"🌡 体調: {condition_name}"
    )

    dashboard_url = f"https://{os.environ.get('SURGE_DOMAIN', '')}"
    message += f"\n\n📊 詳細レポート\n{dashboard_url}"

    send_line_message(message)
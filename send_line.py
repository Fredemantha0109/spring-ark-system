import os
import requests
import json

from ark_config import now_jst, today_jst, yesterday_jst

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

    # 日付（JST）— 今日・昨日の2ページ使い分け
    today     = today_jst()
    yesterday = yesterday_jst()

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

    # ── デバッグ出力 ──────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[DEBUG] today={today}, yesterday={yesterday}")
    print(f"[DEBUG] props_today  取得: {'OK' if props_today else 'None（ページなし）'}")
    print(f"[DEBUG] props_yesterday 取得: {'OK' if props_yesterday else 'None（ページなし）'}")

    if props_today:
        print(f"\n[DEBUG] ── props_today の全プロパティ ──")
        for key, val in props_today.items():
            vtype = val.get("type", "?")
            # 型ごとに値を取り出す
            if vtype == "number":
                v = val.get("number")
            elif vtype == "select":
                v = (val.get("select") or {}).get("name")
            elif vtype == "formula":
                v = val.get("formula", {}).get("number") or val.get("formula", {}).get("string")
            elif vtype == "title":
                v = "".join(t.get("plain_text","") for t in val.get("title", []))
            elif vtype == "rich_text":
                v = "".join(t.get("plain_text","") for t in val.get("rich_text", []))
            elif vtype == "date":
                v = (val.get("date") or {}).get("start")
            elif vtype == "checkbox":
                v = val.get("checkbox")
            else:
                v = f"(type={vtype})"
            print(f"  [{vtype}] {key!r}: {v!r}")

    if props_yesterday:
        print(f"\n[DEBUG] ── props_yesterday の全プロパティ ──")
        for key, val in props_yesterday.items():
            vtype = val.get("type", "?")
            if vtype == "number":
                v = val.get("number")
            elif vtype == "select":
                v = (val.get("select") or {}).get("name")
            elif vtype == "formula":
                v = val.get("formula", {}).get("number") or val.get("formula", {}).get("string")
            elif vtype == "title":
                v = "".join(t.get("plain_text","") for t in val.get("title", []))
            elif vtype == "rich_text":
                v = "".join(t.get("plain_text","") for t in val.get("rich_text", []))
            elif vtype == "date":
                v = (val.get("date") or {}).get("start")
            elif vtype == "checkbox":
                v = val.get("checkbox")
            else:
                v = f"(type={vtype})"
            print(f"  [{vtype}] {key!r}: {v!r}")
    print(f"{'='*60}\n")
    # ── デバッグ出力ここまで ──────────────────────────

    if not props_yesterday:
        send_line_message(f"⚠️ {yesterday} のデータが見つかりません")
        exit(1)
    if not props_today:
        props_today = props_yesterday

    # 予定タスク件数（昨日ページ）
    def plan_count(key):
        return len(props_yesterday.get(key, {}).get("multi_select", []))

    # スコアは昨日のページから（予定タスク0件のカテゴリは None = 総合スコアから除外）
    def get_score_or_none(score_key, plan_key):
        if plan_count(plan_key) == 0:
            return None
        return props_yesterday.get(score_key, {}).get("formula", {}).get("number", 0) or 0

    score_w  = get_score_or_none("【W】スコア",  "【W】予定タスク")
    score_c  = get_score_or_none("【C】スコア",  "【C】予定タスク")
    score_ca = get_score_or_none("【Ca】スコア", "【Ca】予定タスク")
    score_i  = get_score_or_none("【I】スコア",  "【I】予定タスク")
    _valid = [s for s in [score_w, score_c, score_ca, score_i] if s is not None]
    score_total = round(sum(_valid) / len(_valid)) if _valid else 0

    def fmt(s): return str(int(s)) if s is not None else "-"

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
        f"  W: {fmt(score_w)} / C: {fmt(score_c)} / Ca: {fmt(score_ca)} / I: {fmt(score_i)}\n"
        f"\n"
        f"💪 体重: {weight_str}\n"
        f"😴 睡眠: {sleep_str}\n"
        f"🌡 体調: {condition_name}"
    )

    dashboard_url = f"https://{os.environ.get('SURGE_DOMAIN', '')}"
    message += f"\n\n📊 詳細レポート\n{dashboard_url}"

    send_line_message(message)
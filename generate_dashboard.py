"""
generate_dashboard.py — Notionからデータを取得してHTMLダッシュボードを生成し、Surgeにデプロイする
v3: トレーニングログDB連携追加（Daily/Weekly/Monthlyに筋トレ進捗を表示）

実行タイミング:
    GitHub Actions内でcalc_score.pyの後に実行される
"""

import os
import json
import subprocess
import requests
from datetime import datetime, timezone, timedelta

# ── 環境変数 ──────────────────────────────────────
NOTION_TOKEN         = os.environ["NOTION_TOKEN"]
DATABASE_ID          = os.environ["DATABASE_ID"]
SURGE_TOKEN          = os.environ["SURGE_TOKEN"]
SURGE_DOMAIN         = os.environ["SURGE_DOMAIN"]
CALENDAR_DATABASE_ID = os.environ.get("CALENDAR_DATABASE_ID", "")
JOURNAL_DATABASE_ID          = os.environ.get("JOURNAL_DATABASE_ID", "")
JOURNAL_WEEKLY_DATABASE_ID   = os.environ.get("JOURNAL_WEEKLY_DATABASE_ID", "")
JOURNAL_MONTHLY_DATABASE_ID  = os.environ.get("JOURNAL_MONTHLY_DATABASE_ID", "")
TRAINING_DATABASE_ID         = os.environ.get("TRAINING_DATABASE_ID", "")
TOPIC_CARD_DATABASE_ID       = os.environ.get("TOPIC_CARD_DATABASE_ID", "")
REUSE_LOG_DATABASE_ID        = os.environ.get("REUSE_LOG_DATABASE_ID", "")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ── 日付(SGT = UTC+8) ────────────────────────────
sgt       = timezone(timedelta(hours=8))
today     = datetime.now(sgt).strftime("%Y-%m-%d")
yesterday = (datetime.now(sgt) - timedelta(days=1)).strftime("%Y-%m-%d")

def fetch_page(date_str):
    res = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=HEADERS,
        json={"filter": {"property": "Date", "title": {"equals": date_str}}}
    )
    results = res.json().get("results", [])
    if not results:
        return None, None
    return results[0]["id"], results[0]["properties"]

# ── ▼ ジャーナリング取得ユーティリティ ──────────────
def _get_rich_text(props, key):
    """Notion rich_text プロパティからプレーンテキストを取得する"""
    items = props.get(key, {}).get("rich_text", [])
    return "".join([t.get("plain_text", "") for t in items])


def fetch_journal_entries(start_date_str, end_date_str):
    if not JOURNAL_DATABASE_ID:
        print("[INFO] JOURNAL_DATABASE_ID が未設定のためジャーナリング取得をスキップ")
        return []

    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{JOURNAL_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "and": [
                        {"property": "日付元", "date": {"on_or_after":  start_date_str}},
                        {"property": "日付元", "date": {"on_or_before": end_date_str}},
                    ]
                },
                "sorts": [{"property": "日付元", "direction": "ascending"}],
            },
            timeout=15,
        )
        if not res.ok:
            print(f"[WARN] Daily Journal APIエラー詳細: {res.status_code} {res.text[:500]}")
            return []
        entries = []
        for page in res.json().get("results", []):
            props = page["properties"]
            date_val = (props.get("日付元", {}).get("date") or {}).get("start", "")
            entries.append({
                "date":      date_val,
                "discharge": _get_rich_text(props, "放電ログ")[:300],
                "charge":    _get_rich_text(props, "充電ログ")[:300],
                "emotion":   _get_rich_text(props, "感情と観察")[:300],
                "needs":     _get_rich_text(props, "奥にあるニーズ"),
                "message":   _get_rich_text(props, "今日への一言")[:100],
            })
        print(f"[OK] ジャーナリング取得: {len(entries)}件 ({start_date_str} 〜 {end_date_str})")
        return entries

    except Exception as e:
        print(f"[WARN] ジャーナリング取得エラー: {e}")
        return []


def fetch_weekly_journal_entries(start_date_str, end_date_str):
    if not JOURNAL_WEEKLY_DATABASE_ID:
        print("[INFO] JOURNAL_WEEKLY_DATABASE_ID が未設定のためWeeklyジャーナリング取得をスキップ")
        return []

    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{JOURNAL_WEEKLY_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "and": [
                        {"property": "日付元", "date": {"on_or_after":  start_date_str}},
                        {"property": "日付元", "date": {"on_or_before": end_date_str}},
                    ]
                },
                "sorts": [{"property": "日付元", "direction": "ascending"}],
            },
            timeout=15,
        )
        if not res.ok:
            print(f"[WARN] Weekly Journal APIエラー詳細: {res.status_code} {res.text[:500]}")
            return []
        entries = []
        for page in res.json().get("results", []):
            props = page["properties"]
            date_prop = props.get("日付元", {}).get("date") or {}
            start = date_prop.get("start", "")
            end   = date_prop.get("end", "")
            entries.append({
                "date_range":      f"{start}〜{end}" if end else start,
                "emotion_pattern": _get_rich_text(props, "感情パターン"),
                "needs":           _get_rich_text(props, "奥にあるニーズ"),
                "env_relation":    _get_rich_text(props, "環境・状況との関係")[:200],
                "next_question":   _get_rich_text(props, "来週への一つの問い"),
            })
        print(f"[OK] Weekly Journal取得: {len(entries)}件 ({start_date_str} 〜 {end_date_str})")
        return entries

    except Exception as e:
        print(f"[WARN] Weekly Journal取得エラー: {e}")
        return []


def fetch_monthly_journal_entries(yymm_str):
    if not JOURNAL_MONTHLY_DATABASE_ID:
        print("[INFO] JOURNAL_MONTHLY_DATABASE_ID が未設定のためMonthlyジャーナリング取得をスキップ")
        return []

    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{JOURNAL_MONTHLY_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "property": "YYMM",
                    "title": {"equals": yymm_str}
                },
            },
            timeout=15,
        )
        res.raise_for_status()
        entries = []
        for page in res.json().get("results", []):
            props = page["properties"]
            date_prop = props.get("日付", {}).get("date") or {}
            start = date_prop.get("start", "")
            end   = date_prop.get("end", "")
            entries.append({
                "date_range":        f"{start}〜{end}" if end else start,
                "emotion_structure": _get_rich_text(props, "感情パターン"),
                "charge_discharge":  _get_rich_text(props, "放電感情") + " / " + _get_rich_text(props, "充電感情"),
                "needs_priority":    _get_rich_text(props, "ニーズの優先順位"),
                "habit_emotion":     _get_rich_text(props, "行動と感情の相関"),
                "next_experiment":   _get_rich_text(props, "来月への設計提案"),
            })
        print(f"[OK] Monthly Journal取得: {len(entries)}件")
        return entries

    except Exception as e:
        print(f"[WARN] Monthly Journal取得エラー: {e}")
        return []


def build_weekly_journal_section(weekly_entries):
    if not weekly_entries:
        return ""
    lines = []
    for e in weekly_entries:
        parts = []
        if e["emotion_pattern"]: parts.append(f"感情パターン:{e['emotion_pattern']}")
        if e["needs"]:           parts.append(f"ニーズ:{e['needs']}")
        if e["env_relation"]:    parts.append(f"環境との関係:{e['env_relation']}")
        if e["next_question"]:   parts.append(f"来週への問い:{e['next_question']}")
        if parts:
            lines.append(f"[{e['date_range']}] " + " / ".join(parts))
    if not lines:
        return ""
    return (
        "\n【週次ジャーナリングまとめ（NVC観点）】\n"
        + "\n".join(lines)
        + "\n"
    )


def build_monthly_journal_section(monthly_entries):
    if not monthly_entries:
        return ""
    lines = []
    for e in monthly_entries:
        parts = []
        if e["emotion_structure"]: parts.append(f"感情構造:{e['emotion_structure'][:120]}")
        if e["charge_discharge"]:  parts.append(f"充放電:{e['charge_discharge'][:120]}")
        if e["needs_priority"]:    parts.append(f"ニーズ優先度:{e['needs_priority']}")
        if e["next_experiment"]:   parts.append(f"来月実験:{e['next_experiment'][:80]}")
        if parts:
            lines.append(f"[{e['date_range']}] " + " / ".join(parts))
    if not lines:
        return ""
    return (
        "\n【月次ジャーナリングまとめ】\n"
        + "\n".join(lines)
        + "\n"
    )


def build_journal_prompt_section(entries, max_days=7):
    if not entries:
        return ""

    lines = []
    for e in entries[:max_days]:
        parts = []
        if e["discharge"]: parts.append(f"放電:{e['discharge'][:80]}")
        if e["charge"]:    parts.append(f"充電:{e['charge'][:80]}")
        if e["needs"]:     parts.append(f"ニーズ:{e['needs']}")
        if e["emotion"]:   parts.append(f"感情:{e['emotion']}")
        if parts:
            lines.append(f"[{e['date']}] " + " / ".join(parts))

    if not lines:
        return ""

    return (
        "\n【今週のジャーナリング(NVC観点)】\n"
        + "\n".join(lines)
        + "\n"
    )


def build_journal_monthly_section(entries):
    if not entries:
        return ""

    chunks = [entries[i:i+7] for i in range(0, len(entries), 7)]
    lines = []
    for week_idx, chunk in enumerate(chunks, 1):
        discharges = [e["discharge"][:40] for e in chunk if e["discharge"]]
        charges    = [e["charge"][:40]    for e in chunk if e["charge"]]
        needs_list = [e["needs"][:40]     for e in chunk if e["needs"]]
        if discharges or needs_list:
            lines.append(
                f"[Week{week_idx}] "
                f"放電:{' / '.join(discharges[:3])} | "
                f"充電:{' / '.join(charges[:3])} | "
                f"ニーズ:{' / '.join(needs_list[:3])}"
            )

    if not lines:
        return ""

    return (
        "\n【今月のジャーナリング週次サマリー(NVC観点)】\n"
        + "\n".join(lines)
        + "\n"
    )
# ── ▲ ジャーナリング取得ユーティリティ ここまで ──────


# ── ▼ トレーニングログ取得ユーティリティ ─────────────
def fetch_training_data(target_date_str):
    """指定日のトレーニングデータを取得"""
    if not TRAINING_DATABASE_ID:
        return []
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{TRAINING_DATABASE_ID}/query",
            headers=HEADERS,
            json={"filter": {"property": "日付", "date": {"equals": target_date_str}}},
            timeout=10
        )
        results = res.json().get("results", [])
        sessions = []
        for r in results:
            p = r.get("properties", {})
            shumoku_prop = p.get("種目", {}).get("select")
            shumoku = shumoku_prop.get("name", "") if isinstance(shumoku_prop, dict) else ""
            sessions.append({
                "種目":    shumoku,
                "目標":    p.get("目標", {}).get("number"),
                "実績":    p.get("実績", {}).get("number"),
                "回数":    p.get("回数", {}).get("number"),
                "セット数": p.get("セット数", {}).get("number"),
            })
        return [s for s in sessions if s.get("種目", "")]
    except Exception as e:
        print(f"[WARN] Training fetch error: {e}")
        return []


def fetch_training_period(start_str, end_str):
    """指定期間の実績ありトレーニングデータを取得"""
    if not TRAINING_DATABASE_ID:
        return []
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{TRAINING_DATABASE_ID}/query",
            headers=HEADERS,
            json={"filter": {"and": [
                {"property": "日付", "date": {"on_or_after": start_str}},
                {"property": "日付", "date": {"on_or_before": end_str}},
                
            ]}},
            timeout=10
        )
        results = res.json().get("results", [])
        sessions = []
        for r in results:
            p = r.get("properties", {})
            shumoku_prop = p.get("種目", {}).get("select")
            shumoku = shumoku_prop.get("name", "") if isinstance(shumoku_prop, dict) else ""
            sessions.append({
                "日付":    p.get("日付", {}).get("date", {}).get("start", ""),
                "種目":    shumoku,
                "目標":    p.get("目標", {}).get("number"),
                "実績":    p.get("実績", {}).get("number"),
                "回数":    p.get("回数", {}).get("number"),
                "セット数": p.get("セット数", {}).get("number"),
            })
        filtered = sorted([s for s in sessions if s.get("種目", "")], key=lambda x: x["日付"])
        print(f"[OK] トレーニング取得: {len(filtered)}件 ({start_str}〜{end_str})")
        return filtered
    except Exception as e:
        print(f"[WARN] Training period fetch error: {e}")
        return []


def _training_rows_html(sessions):
    rows = ""
    for s in sessions:
        shumoku = s.get("種目", "")
        mokuhyo = s.get("目標")
        jisseki = s.get("実績")
        kaisuu = s.get("回数")
        setto = s.get("セット数")
        set_info = f"{kaisuu}回×{setto}セット" if kaisuu and setto else ""
        if jisseki and mokuhyo:
            diff = round(jisseki - mokuhyo, 1)
            clr = "text-green-400" if diff > 0 else ("text-red-400" if diff < 0 else "text-white/40")
            sign = "+" if diff > 0 else ""
            diff_html = f'<span class="text-[9px] {clr} font-bold ml-1">{sign}{diff}kg</span>'
            w = f'<span class="text-sm font-black text-white">{jisseki}kg</span><span class="text-[9px] text-ark-muted ml-1">/目標{mokuhyo}kg</span>{diff_html}'
        elif mokuhyo is not None and mokuhyo > 0 and not jisseki:
            w = f'<span class="text-sm font-black text-white/40">{mokuhyo}kg</span><span class="text-[9px] text-ark-muted ml-1">未実施</span>'
        elif jisseki:
            w = f'<span class="text-sm font-black text-white">{jisseki}kg</span>'
        else:
            w = '<span class="text-sm text-ark-muted">-</span>'
        rows += (
            f'<div class="flex items-center justify-between py-1.5 border-b border-ark-border/30 last:border-0">'
            f'<div><p class="text-xs font-bold text-white/80">{shumoku}</p>'
            f'<p class="text-[10px] text-ark-muted">{set_info}</p></div>'
            f'<div class="text-right">{w}</div></div>'
        )
    return rows


def training_card_html(sessions, title):
    """Daily用：今日のトレーニングカード"""
    if not sessions:
        return ""
    rows = _training_rows_html(sessions)
    if not rows:
        return ""
    return (
        '<div class="stripe bg-ark-card border border-violet-500/15 rounded-2xl p-4 mt-3">'
        '<div class="flex items-center gap-2 mb-2">'
        '<svg class="w-3.5 h-3.5 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>'
        f'<p class="text-[10px] font-black text-violet-400 tracking-[.15em]">{title}</p>'
        '</div>' + rows + '</div>'
    )


def training_summary_html(sessions, period_label):
    """Weekly/Monthly用：種目別ベスト記録カード"""
    if not sessions:
        return ""
    best = {}
    for s in sessions:
        shumoku = s.get("種目","")
        jisseki = s.get("実績")
        if shumoku and jisseki is not None:
            if shumoku not in best or jisseki > best[shumoku]["実績"]:
                best[shumoku] = s
    if not best:
        return ""
    rows = _training_rows_html(list(best.values()))
    return (
        '<div class="stripe bg-ark-card border border-violet-500/15 rounded-2xl p-4 mt-3">'
        '<div class="flex items-center gap-2 mb-2">'
        '<svg class="w-3.5 h-3.5 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>'
        f'<p class="text-[10px] font-black text-violet-400 tracking-[.15em]">TRAINING {period_label} BEST</p>'
        '</div>' + rows + '</div>'
    )
# ── ▲ トレーニングログ取得ユーティリティ ここまで ───

# ── ▼ 英語学習データ取得ユーティリティ ─────────────
def fetch_topic_cards():
    """トピックカードDBから全カードを取得"""
    if not TOPIC_CARD_DATABASE_ID:
        return []
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{TOPIC_CARD_DATABASE_ID}/query",
            headers=HEADERS,
            json={"sorts": [{"property": "最終練習日", "direction": "descending"}]},
            timeout=10
        )
        results = res.json().get("results", [])
        cards = []
        for r in results:
            p = r.get("properties", {})
            topic = ""
            title_items = p.get("トピック名", {}).get("title", [])
            if title_items:
                topic = title_items[0].get("plain_text", "")
            group_prop = p.get("グループ", {}).get("select")
            group = group_prop.get("name", "") if isinstance(group_prop, dict) else ""
            score_prop = p.get("話せる度", {}).get("number")
            score = score_prop if score_prop is not None else 0
            last_date = (p.get("最終練習日", {}).get("date") or {}).get("start", "")
            stuck = ""
            stuck_items = p.get("詰まったフレーズ", {}).get("rich_text", [])
            if stuck_items:
                stuck = stuck_items[0].get("plain_text", "")[:100]
            if topic:
                cards.append({
                    "topic": topic,
                    "group": group,
                    "score": score,
                    "last_date": last_date,
                    "stuck": stuck,
                })
        print(f"[OK] トピックカード取得: {len(cards)}件")
        return cards
    except Exception as e:
        print(f"[WARN] Topic card fetch error: {e}")
        return []


def fetch_reuse_log_period(start_str, end_str):
    """指定期間のフレーズログを取得"""
    if not REUSE_LOG_DATABASE_ID:
        return []
    try:
        res = requests.post(
            f"https://api.notion.com/v1/databases/{REUSE_LOG_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "and": [
                        {"property": "日付", "date": {"on_or_after": start_str}},
                        {"property": "日付", "date": {"on_or_before": end_str}},
                    ]
                },
                "sorts": [{"property": "日付", "direction": "ascending"}],
            },
            timeout=10
        )
        results = res.json().get("results", [])
        logs = []
        for r in results:
            p = r.get("properties", {})
            phrase = ""
            title_items = p.get("対象表現", {}).get("title", [])
            if not title_items:
                title_items = p.get("Name", {}).get("title", [])
            if title_items:
                phrase = title_items[0].get("plain_text", "")
            tool_prop = p.get("ツール", {}).get("select")
            tool = tool_prop.get("name", "") if isinstance(tool_prop, dict) else ""
            used = p.get("見ずに使えた（BC）", {}).get("checkbox", False)
            date_val = (p.get("日付", {}).get("date") or {}).get("start", "")
            if phrase:
                logs.append({
                    "phrase": phrase,
                    "tool": tool,
                    "used": used,
                    "date": date_val,
                })
        print(f"[OK] フレーズログ取得: {len(logs)}件 ({start_str}〜{end_str})")
        return logs
    except Exception as e:
        print(f"[WARN] Reuse log fetch error: {e}")
        return []


def build_english_prompt_section(topic_cards, reuse_logs):
    """Claude APIに渡す英語学習セクションを構築"""
    if not topic_cards and not reuse_logs:
        return ""

    lines = []

    if topic_cards:
        lines.append("【英語学習：トピックカード状況】")
        for c in topic_cards[:10]:
            last = c["last_date"] or "未練習"
            stuck_str = f" / 詰まり:{c['stuck'][:30]}" if c["stuck"] else ""
            lines.append(f"・{c['topic']}（{c['group']}）: 話せる度{c['score']}/5 最終練習:{last}{stuck_str}")

    if reuse_logs:
        total = len(reuse_logs)
        used_count = sum(1 for l in reuse_logs if l["used"])
        used_rate = round(used_count / total * 100) if total > 0 else 0
        lines.append(f"【英語学習：フレーズログ】")
        lines.append(f"・今期記録数: {total}件 / 見ずに使えた率: {used_rate}%")
        recent = reuse_logs[-3:]
        for l in recent:
            lines.append(f"・{l['date']} [{l['tool']}] {l['phrase'][:30]}")

    return "\n" + "\n".join(lines) + "\n"
# ── ▲ 英語学習データ取得ユーティリティ ここまで ─────

# ── ▼ 英語学習AI分析 ─────────────────────────────
def generate_english_analysis(topic_cards, reuse_logs, score_c):
    """英語学習専用のAI分析を生成"""
    if not ANTHROPIC_API_KEY or (not topic_cards and not reuse_logs):
        return "", "", ""

    total = len(reuse_logs)
    used_count = sum(1 for l in reuse_logs if l["used"])
    used_rate = round(used_count / total * 100) if total > 0 else 0

    patapra_count = sum(1 for l in reuse_logs if l["tool"] == "PataPra")
    sb_count = sum(1 for l in reuse_logs if l["tool"] == "SpeakBuddy")

    cards_str = ""
    for c in topic_cards:
        last = c["last_date"] or "未練習"
        stuck_str = f"／詰まり:{c['stuck'][:20]}" if c["stuck"] else ""
        cards_str += f"・{c['topic']}（{c['group']}）: {c['score']}/5 最終:{last}{stuck_str}\n"

    prompt = (
        "あなたはSpring Arkプロジェクトの英語学習コーチです。\n"
        "以下のデータをもとに、英語学習分析を3つのセクションに分けてJSON形式で出力してください。\n\n"
        f"【COMMUNICATIONスコア】{score_c}/100\n\n"
        f"【トピックカード状況】\n{cards_str}\n"
        f"【フレーズログ】\n"
        f"・記録数: {total}件\n"
        f"・見ずに使えた率: {used_rate}%\n"
        f"・PataPra: {patapra_count}件 / SpeakBuddy: {sb_count}件\n\n"
        "【出力形式】必ずJSONオブジェクトのみ出力してください。\n"
        "{\n"
        '  "overall": "今期の英語学習の総合評価（80字以内）",\n'
        '  "retention": "フレーズ定着率の傾向と考察（80字以内）",\n'
        '  "priority": "今後優先すべき練習トピックと理由（80字以内）"\n'
        "}"
    )

    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        import json as _j
        text = res.json()["content"][0]["text"].strip()
        start_j, end_j = text.find("{"), text.rfind("}") + 1
        if start_j >= 0 and end_j > start_j:
            parsed = _j.loads(text[start_j:end_j])
            overall   = str(parsed.get("overall",   "")).strip()[:120]
            retention = str(parsed.get("retention", "")).strip()[:120]
            priority  = str(parsed.get("priority",  "")).strip()[:120]
            return overall, retention, priority
    except Exception as e:
        print(f"[WARN] English analysis error: {e}")
    return "", "", ""
# ── ▲ 英語学習AI分析 ここまで ───────────────────────


# ── 今日のページ（体重・睡眠・体調）+ 昨日のページ（スコア・タスク）──
today_page_id,     props_today     = fetch_page(today)
yesterday_page_id, props_yesterday = fetch_page(yesterday)

if not props_yesterday:
    print(f"[WARN] {yesterday} のページが見つかりません")
    exit(1)

if not props_today:
    print(f"[INFO] {today} のページが未作成のため昨日のデータで代用")
    props_today   = props_yesterday
    today_page_id = yesterday_page_id

# ── データ抽出 ────────────────────────────────────
def get_score(key):
    return props_yesterday.get(key, {}).get("formula", {}).get("number", 0) or 0

def get_tasks(key):
    return [t["name"] for t in props_yesterday.get(key, {}).get("multi_select", [])]

score_w  = get_score("【W】スコア")
score_c  = get_score("【C】スコア")
score_ca = get_score("【Ca】スコア")
score_i  = get_score("【I】スコア")
score_total = round((score_w + score_c + score_ca + score_i) / 4)

weight    = props_today.get("体重", {}).get("number") or "-"
sleep     = props_today.get("睡眠時間", {}).get("number") or "-"
condition = (props_today.get("体調", {}).get("select") or {}).get("name", "-")

# ── Claude APIで推奨作戦を生成 ──────────────────────
import json as _json

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── JSON出力バリデーション ─────────────────────────
def validate_strategy(item):
    if not isinstance(item, dict):
        return {"title": "今日も着実に前進", "detail": "基本タスクを1つずつ丁寧に実施する"}
    title  = str(item.get("title", "")).strip()
    detail = str(item.get("detail", "")).strip()
    if not title:  title  = "今日も着実に前進"
    if not detail: detail = "基本タスクを1つずつ丁寧に実施する"
    if len(title)  > 20: title  = title[:20]
    if len(detail) > 50: detail = detail[:50]
    return {"title": title, "detail": detail}

def validate_strategies(raw):
    if not isinstance(raw, list):
        raw = []
    validated = [validate_strategy(item) for item in raw[:3]]
    defaults = [
        {"title": "基本タスクを実施", "detail": "今日の予定タスクを1つずつ確実にこなす"},
        {"title": "コンディション維持", "detail": "睡眠・食事・運動のバランスを意識する"},
        {"title": "振り返りを記録", "detail": "夜に今日の実績をNotionに記録する"},
    ]
    while len(validated) < 3:
        validated.append(defaults[len(validated)])
    return validated

def validate_weekly_monthly(parsed):
    if not isinstance(parsed, dict):
        parsed = {}
    summaries = parsed.get("summaries", [])
    if not isinstance(summaries, list):
        summaries = []
    validated_summaries = []
    for s in summaries[:3]:
        if not isinstance(s, dict):
            continue
        t = str(s.get("title", "")).strip()[:20] or "分析中"
        d = str(s.get("detail", "")).strip()[:50] or "データを確認中です"
        validated_summaries.append({"title": t, "detail": d})
    while len(validated_summaries) < 3:
        validated_summaries.append({"title": "データ収集中", "detail": "記録が蓄積されると詳細な分析が表示されます"})
    analysis = str(parsed.get("analysis", "")).strip()
    if not analysis:
        analysis = "データが蓄積されると詳細な総合分析が表示されます。毎日の記録を続けることで精度が上がります。"
    if len(analysis) > 600:
        analysis = analysis[:600]
    return validated_summaries, analysis

def generate_strategy(sleep_val, cond, judge, scores, missed_tasks, weight_val="-"):
    if not ANTHROPIC_API_KEY:
        return []
    missed_str = "\n".join([f"・{cat}: {task}" for task, cat in missed_tasks]) or "なし"
    score_str  = f"W:{scores[0]} / C:{scores[1]} / Ca:{scores[2]} / I:{scores[3]}"
    prompt = (
        "あなたはSpring Arkプロジェクトのパーソナルコーチです。\n"
        "以下のデータをもとに、今日の具体的な推奨作戦を3つ、JSON形式で出力してください。\n\n"
        f"【今日のコンディション】\n"
        f"- 睡眠: {sleep_val}h\n"
        f"- 体調: {cond}\n"
        f"- 体重: {weight_val}kg\n"
        f"- 総合判定: {judge}\n"
        f"- スコア: {score_str}\n\n"
        f"【昨日の未達タスク】\n{missed_str}\n\n"
        "【出力形式】必ずJSON配列のみ出力してください。他のテキストは一切不要。\n"
        '[\n'
        '  {"title": "作戦タイトル(15文字以内)", "detail": "具体的な行動(30文字以内)"},\n'
        '  {"title": "作戦タイトル(15文字以内)", "detail": "具体的な行動(30文字以内)"},\n'
        '  {"title": "作戦タイトル(15文字以内)", "detail": "具体的な行動(30文字以内)"}\n'
        ']'
    )
    import json as _j
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]},
            timeout=20
        )
        text = res.json()["content"][0]["text"].strip()
        start, end = text.find("["), text.rfind("]") + 1
        if start >= 0 and end > start:
            raw = _j.loads(text[start:end])
            return validate_strategies(raw)
    except Exception as e:
        print(f"[WARN] Claude API error: {e}")
    return validate_strategies([])

plan_w  = get_tasks("【W】予定タスク")
plan_c  = get_tasks("【C】予定タスク")
plan_ca = get_tasks("【Ca】予定タスク")
plan_i  = get_tasks("【I】予定タスク")
done_w  = get_tasks("【W】実績")
done_c  = get_tasks("【C】実績")
done_ca = get_tasks("【Ca】実績")
done_i  = get_tasks("【I】実績")

missed_tasks_all = []
for task in plan_w:
    clean = task.lstrip("🔥")
    if clean not in [d.lstrip("🔥") for d in done_w]:
        missed_tasks_all.append((clean, "Wellness"))
for task in plan_c:
    clean = task.lstrip("🔥")
    if clean not in [d.lstrip("🔥") for d in done_c]:
        missed_tasks_all.append((clean, "Communication"))
for task in plan_ca:
    clean = task.lstrip("🔥")
    if clean not in [d.lstrip("🔥") for d in done_ca]:
        missed_tasks_all.append((clean, "Career"))
for task in plan_i:
    clean = task.lstrip("🔥")
    if clean not in [d.lstrip("🔥") for d in done_i]:
        missed_tasks_all.append((clean, "Input"))

# ── 判定（睡眠時間 × 体調）────────────────────────
def calc_judge(sleep_val, cond):
    s = sleep_val if isinstance(sleep_val, (int, float)) else 0
    if (s >= 7 and cond in ("好調", "普通")) or (5.5 <= s < 7 and cond == "好調"):
        return "良好", "green"
    if (5.5 <= s < 7 and cond == "不調") or (s < 5.5 and cond in ("普通", "不調")):
        return "危険", "red"
    return "要注意", "amber"

judge_label, judge_color = calc_judge(sleep, condition)

ai_note = ""
ai_strategies = generate_strategy(
    sleep, condition, judge_label,
    [score_w, score_c, score_ca, score_i],
    missed_tasks_all[:8],
    weight_val=weight
)

# ── 過去5日間の優先タスク候補を集計 ──────────────────
CATEGORIES = {
    'W':  ('【W】予定タスク',  '【W】実績'),
    'C':  ('【C】予定タスク',  '【C】実績'),
    'Ca': ('【Ca】予定タスク', '【Ca】実績'),
    'I':  ('【I】予定タスク',  '【I】実績'),
}

def fetch_past_pages(n=5):
    pages_data = []
    for i in range(1, n + 1):
        d = (datetime.now(sgt) - timedelta(days=i)).strftime("%Y-%m-%d")
        _, p = fetch_page(d)
        if p:
            pages_data.append((d, p))
    return pages_data

past_pages = fetch_past_pages(5)

miss_count = {}
for date_str, p in past_pages:
    for cat, (plan_key, done_key) in CATEGORIES.items():
        plan = [t["name"] for t in p.get(plan_key, {}).get("multi_select", [])]
        done = [t["name"] for t in p.get(done_key, {}).get("multi_select", [])]
        plan_clean = [t.lstrip("🔥") for t in plan]
        done_clean = [t.lstrip("🔥") for t in done]
        for task in plan_clean:
            if task not in done_clean:
                key = (task, cat)
                miss_count[key] = miss_count.get(key, 0) + 1

candidate_1 = None
if miss_count:
    top = sorted(miss_count.items(), key=lambda x: -x[1])[0]
    candidate_1 = (top[0][0], top[0][1], top[1])

last_done = {}
for date_str, p in past_pages:
    for cat, (plan_key, done_key) in CATEGORIES.items():
        done = [t["name"].lstrip("🔥") for t in p.get(done_key, {}).get("multi_select", [])]
        plan = [t["name"].lstrip("🔥") for t in p.get(plan_key, {}).get("multi_select", [])]
        for task in plan:
            key = (task, cat)
            if task in done:
                if key not in last_done or date_str > last_done[key]:
                    last_done[key] = date_str
            else:
                if key not in last_done:
                    last_done[key] = "never"

candidate_2 = None
if last_done:
    def sort_key(x):
        return x[1] if x[1] != "never" else "0000-00-00"
    oldest = sorted(last_done.items(), key=lambda x: sort_key(x))[0]
    for item in sorted(last_done.items(), key=lambda x: sort_key(x)):
        if candidate_1 is None or item[0][0] != candidate_1[0]:
            candidate_2 = (item[0][0], item[0][1], item[1])
            break
    if candidate_2 is None and last_done:
        candidate_2 = (oldest[0][0], oldest[0][1], oldest[1])


# ── タスク行HTML生成 ──────────────────────────────
def task_rows_html(plan_tasks, done_tasks):
    if not plan_tasks:
        return '<p class="text-xs italic py-1" style="color:rgba(74,90,114,0.7)">本日タスクなし</p>'
    items = []
    for task in plan_tasks:
        done = task in done_tasks
        if done:
            icon = (
                '<div class="w-3.5 h-3.5 rounded-full flex-shrink-0 bg-green-500/25 border border-green-400/60'
                ' flex items-center justify-center">'
                '<svg class="w-2 h-2 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                '<polyline stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="20 6 9 17 4 12"/>'
                '</svg></div>'
            )
        else:
            icon = '<div class="w-3.5 h-3.5 rounded-full flex-shrink-0 border border-white/15 bg-white/5"></div>'
        name_class = "text-white/40 line-through" if done else "text-white/80"
        row_class  = "priority-row" if "🔥" in task else ""
        items.append(
            '<div class="flex items-center gap-1.5 py-[3px] ' + row_class + '">'
            + icon
            + '<span class="text-xs flex-1 leading-tight ' + name_class + '">' + task + '</span>'
            + '</div>'
        )
    return '<div class="grid grid-cols-2 gap-x-3 gap-y-0.5">' + "\n".join(items) + '</div>'

def category_card(name, subtitle, icon_svg, color, score, plan_tasks, done_tasks):
    color_map = {
        "green": ("text-green-400", "bg-green-500/10 border-green-500/20", "border-ark-border",   "from-green-600 to-emerald-400"),
        "amber": ("text-amber-400", "bg-amber-500/10 border-amber-500/20", "border-amber-500/20", "from-amber-500 to-yellow-400"),
        "rose":  ("text-rose-400",  "bg-rose-500/10 border-rose-500/20",   "border-rose-500/25",  "from-rose-600 to-red-400"),
        "sky":   ("text-sky-400",   "bg-sky-500/10 border-sky-500/20",     "border-sky-500/20",   "from-sky-500 to-cyan-400"),
    }
    text_c, icon_wrap, card_border, bar_grad = color_map[color]
    rows = task_rows_html(plan_tasks, done_tasks)
    return (
        '<div class="ark-card bg-ark-card border ' + card_border + ' rounded-2xl p-4 min-h-[120px]">'
        '<div class="flex items-start justify-between mb-3">'
        '<div class="flex items-center gap-2.5">'
        '<div class="w-8 h-8 rounded-xl ' + icon_wrap + ' border flex items-center justify-center flex-shrink-0">'
        '<span class="' + text_c + '">' + icon_svg + '</span>'
        '</div>'
        '<div>'
        '<p class="text-xs font-black ' + text_c + ' tracking-[.15em]">' + name + '</p>'
        '<p class="text-xs text-ark-muted">' + subtitle + '</p>'
        '</div></div>'
        '<p class="text-xl font-black ' + text_c + '">' + str(score)
        + '<span class="text-sm text-ark-muted font-normal">/100点</span></p>'
        '</div>'
        '<div class="mb-3">'
        '<div class="h-1.5 bg-ark-dim rounded-full overflow-hidden">'
        '<div class="h-full rounded-full bg-gradient-to-r ' + bar_grad + ' bar" style="width:' + str(score) + '%"></div>'
        '</div></div>'
        + rows
        + '</div>'
    )

ICON_W  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/></svg>'
ICON_C  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
ICON_CA = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>'
ICON_I  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'

ai_html = ""
if ai_note:
    lines = ai_note.strip().split("\n")
    items = []
    for i, line in enumerate(lines[1:], 1):
        if line.strip():
            items.append(
                '<div class="flex items-start gap-2.5 bg-violet-500/6 border border-violet-500/15 rounded-xl px-3 py-2.5">'
                '<span class="w-4 h-4 rounded-full bg-violet-500/20 border border-violet-500/30 text-[9px] font-black'
                ' text-violet-400 flex items-center justify-center flex-shrink-0 mt-0.5">' + str(i) + '</span>'
                '<p class="text-xs text-white/80">' + line.strip().lstrip("・") + '</p>'
                '</div>'
            )
    ai_html = "\n".join(items)

ai_section_inner = ai_html if ai_html else '<p class="text-xs text-ark-muted text-center py-4">昨日の未達タスクなし 🎉</p>'

strategy_html = ""
if ai_strategies:
    items_html = []
    for i, s in enumerate(ai_strategies, 1):
        items_html.append(
            '<div class="flex items-start gap-3 bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">' +
            '<span class="w-5 h-5 rounded-full bg-violet-500/25 border border-violet-500/35 text-[9px] font-black text-violet-300 flex items-center justify-center flex-shrink-0 mt-0.5">' + str(i) + '</span>' +
            '<div><p class="text-xs font-black text-white">' + s.get("title", "") + '</p>' +
            '<p class="text-[10px] text-ark-muted mt-0.5">' + s.get("detail", "") + '</p></div>' +
            '</div>'
        )
    strategy_html = (
        '<div class="bg-ark-card border border-violet-500/15 rounded-2xl p-4 mt-4">' +
        '<div class="flex items-center gap-2 mb-3">' +
        '<svg class="w-4 h-4 text-violet-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>' +
        '<p class="text-[10px] font-black text-violet-400 tracking-[.15em]">今日の推奨作戦</p>' +
        '</div>' +
        '<div class="flex flex-col gap-2">' +
        "\n".join(items_html) +
        '</div></div>'
    )

# ── カレンダーDB取得 ──────────────────────────────
calendar_events = []
if CALENDAR_DATABASE_ID:
    try:
        today_start = today + "T00:00:00+08:00"
        today_end   = today + "T23:59:59+08:00"
        cal_res = requests.post(
            f"https://api.notion.com/v1/databases/{CALENDAR_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "and": [
                        {"property": "日付", "date": {"on_or_after": today_start}},
                        {"property": "日付", "date": {"on_or_before": today_end}}
                    ]
                },
                "sorts": [{"property": "日付", "direction": "ascending"}]
            }
        )
        cal_data = cal_res.json()
        print(f"[DEBUG] Calendar status: {cal_res.status_code}, count: {len(cal_data.get('results', []))}")
        for page in cal_data.get("results", []):
            props = page["properties"]
            name = ""
            name_prop = props.get("名前", {})
            if name_prop.get("title"):
                name = name_prop["title"][0].get("plain_text", "")
            date_prop = props.get("日付", {}).get("date", {}) or {}
            start = date_prop.get("start", "")
            end   = date_prop.get("end", "")
            if "T" in start:
                start_time = start[11:16]
                end_time   = end[11:16] if end and "T" in end else ""
                if name:
                    calendar_events.append({"name": name, "start": start_time, "end": end_time})
    except Exception as e:
        print(f"[WARN] Calendar fetch error: {e}")

calendar_html = ""
if calendar_events:
    rows = []
    for ev in calendar_events:
        duration = ""
        if ev["end"]:
            try:
                sh, sm = int(ev["start"][:2]), int(ev["start"][3:])
                eh, em = int(ev["end"][:2]),   int(ev["end"][3:])
                mins = (eh * 60 + em) - (sh * 60 + sm)
                duration = f"{mins}分" if mins > 0 else ""
            except:
                pass
        rows.append(
            f'<div class="flex items-center gap-3 bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2">'
            f'<span class="text-[11px] font-black text-sky-400 w-10 flex-shrink-0">{ev["start"]}</span>'
            f'<div class="w-px h-4 bg-ark-border flex-shrink-0"></div>'
            f'<p class="text-xs text-white/85 flex-1">{ev["name"]}</p>'
            f'<span class="text-[9px] text-ark-muted">{duration}</span>'
            f'</div>'
        )
    calendar_html = (
        '<div class="bg-ark-card border border-sky-500/20 rounded-2xl p-4 mt-4">'
        '<div class="flex items-center gap-2 mb-3">'
        '<svg class="w-4 h-4 text-sky-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
        '<p class="text-[10px] font-black text-sky-400 tracking-[.15em]">TODAY\'S CALENDAR</p>'
        '</div>'
        '<div class="flex flex-col gap-2">' + "\n".join(rows) + '</div>'
        '</div>'
    )

GH_PAT   = os.environ.get("GH_PAT", "")
GH_REPO  = "Fredemantha0109/spring-ark-system"

def calc_load_mode(events):
    total_mins = 0
    for ev in events:
        if ev.get("end"):
            try:
                sh, sm = int(ev["start"][:2]), int(ev["start"][3:])
                eh, em = int(ev["end"][:2]),   int(ev["end"][3:])
                total_mins += (eh * 60 + em) - (sh * 60 + sm)
            except:
                pass
    count = len(events)
    if count >= 3 or total_mins >= 120:
        return "🔴 多忙日", "red",   "習慣は最小限で"
    elif count >= 1 or total_mins >= 60:
        return "🟡 通常日", "amber", "いつも通りで"
    else:
        return "🟢 余裕日", "green", "習慣を積み上げるチャンス"

load_label, load_color, load_sub = calc_load_mode(calendar_events)

def fetch_load_for_date(date_str):
    if not CALENDAR_DATABASE_ID:
        return "通常日"
    try:
        day_start = date_str + "T00:00:00+08:00"
        day_end   = date_str + "T23:59:59+08:00"
        res = requests.post(
            f"https://api.notion.com/v1/databases/{CALENDAR_DATABASE_ID}/query",
            headers=HEADERS,
            json={"filter": {"and": [
                {"property": "日付", "date": {"on_or_after": day_start}},
                {"property": "日付", "date": {"on_or_before": day_end}}
            ]}},
            timeout=10
        )
        evs = []
        for page in res.json().get("results", []):
            props = page["properties"]
            date_prop = props.get("日付", {}).get("date", {}) or {}
            start = date_prop.get("start", "")
            end   = date_prop.get("end", "")
            if "T" in start:
                evs.append({"start": start[11:16], "end": end[11:16] if end and "T" in end else ""})
        label, _, _ = calc_load_mode(evs)
        return label
    except:
        return "通常日"

def majority_load(date_list, suffix):
    counts = {}
    for d in date_list:
        lbl = fetch_load_for_date(d)
        key = lbl.split(" ")[-1].replace("日", "")
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        top_key = "通常"
    else:
        top_key = sorted(counts.items(), key=lambda x: -x[1])[0][0]
    color_map = {"多忙": ("red", "🔴"), "通常": ("amber", "🟡"), "余裕": ("green", "🟢")}
    color, emoji = color_map.get(top_key, ("amber", "🟡"))
    badge_color_map = {
        "red":   ("text-red-400",   "bg-red-500/10 border-red-500/30"),
        "amber": ("text-amber-300", "bg-amber-500/10 border-amber-500/30"),
        "green": ("text-green-400", "bg-green-500/10 border-green-500/30"),
    }
    tc, bc = badge_color_map[color]
    label = f"{emoji} {top_key}{suffix}"
    return (
        f'<div class="inline-flex items-center gap-1.5 {bc} rounded-full px-3 py-1.5 ml-2">'
        f'<div class="w-1.5 h-1.5 rounded-full bg-{color}-400 animate-pulse-slow"></div>'
        f'<span class="text-[11px] font-bold {tc}">{label}</span>'
        f'</div>'
    )

load_color_map = {
    "red":   ("text-red-400",   "bg-red-500/10 border-red-500/30"),
    "amber": ("text-amber-300", "bg-amber-500/10 border-amber-500/30"),
    "green": ("text-green-400", "bg-green-500/10 border-green-500/30"),
}
load_text_c, load_badge_cls = load_color_map[load_color]
load_badge_html = (
    f'<div class="inline-flex items-center gap-1.5 {load_badge_cls} rounded-full px-3 py-1.5 ml-2">'
    f'<div class="w-1.5 h-1.5 rounded-full bg-{load_color}-400 animate-pulse-slow"></div>'
    f'<span class="text-[11px] font-bold {load_text_c}">{load_label}</span>'
    f'</div>'
)

system_trigger_html = ""
if judge_label == "危険":
    system_trigger_html = (
        '<div class="bg-red-500/8 border border-red-500/25 rounded-2xl p-4 mt-4">'
        '<div class="flex items-center gap-2 mb-3">'
        '<svg class="w-4 h-4 text-red-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
        '<p class="text-[10px] font-black text-red-400 tracking-[.15em]">SYSTEM TRIGGER</p>'
        '</div>'
        '<div class="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 flex items-center justify-between gap-3">'
        '<div>'
        '<div class="flex items-center gap-2 mb-1">'
        '<p class="text-sm font-black text-white">Shaktiマット リカバリー</p>'
        '<span class="text-[9px] font-black text-red-400 bg-red-500/20 border border-red-500/30 rounded px-1.5 py-0.5">FORCED</span>'
        '</div>'
        '<p class="text-[10px] text-red-300/70">15分・本日必須・スキップ不可</p>'
        '</div>'
        f'<button onclick="forceSHakti()" class="flex-shrink-0 bg-red-500/20 hover:bg-red-500/35 border border-red-500/40 text-red-300 text-xs font-black rounded-xl px-4 py-2 transition-all cursor-pointer">'
        '今日に追加 →</button>'
        '</div>'
        '</div>'
        f'<script>'
        f'async function forceSHakti(){{'
        f'  const btn = event.target;'
        f'  btn.textContent = "送信中...";'
        f'  btn.disabled = true;'
        f'  try {{'
        f'    const res = await fetch("https://api.github.com/repos/{GH_REPO}/dispatches",{{'
        f'      method:"POST",'
        f'      headers:{{"Authorization":"Bearer {GH_PAT}","Accept":"application/vnd.github+json","Content-Type":"application/json"}},'
        f'      body:JSON.stringify({{"event_type":"force_shakti"}})'
        f'    }});'
        f'    if(res.status===204){{btn.textContent="✅ 追加完了"; btn.style.borderColor="#22c55e"; btn.style.color="#4ade80";}}'
        f'    else{{btn.textContent="❌ エラー"; btn.disabled=false;}}'
        f'  }}catch(e){{btn.textContent="❌ エラー"; btn.disabled=false;}}'
        f'}}'
        f'</script>'
    )

def make_candidate_card(rank, task_name, category, reason, gh_pat, gh_repo):
    cat_colors = {
        "W":  ("text-green-400",  "bg-green-500/10 border-green-500/25",  "WELLNESS"),
        "C":  ("text-amber-400",  "bg-amber-500/10 border-amber-500/25",  "COMMUNICATION"),
        "Ca": ("text-rose-400",   "bg-rose-500/10 border-rose-500/25",    "CAREER"),
        "I":  ("text-sky-400",    "bg-sky-500/10 border-sky-500/25",      "INPUT"),
    }
    text_c, badge_cls, cat_label = cat_colors.get(category, ("text-white", "bg-ark-dim", category))
    fn = f"forcePriority{rank}"
    return (
        f'<div class="bg-ark-card border border-ark-border rounded-xl p-3">'
        f'<div class="flex items-start justify-between gap-2">'
        f'<div class="flex-1 min-w-0">'
        f'<div class="flex items-center gap-1.5 mb-1">'
        f'<span class="text-[9px] font-black {text_c} {badge_cls} border rounded px-1.5 py-0.5">{cat_label}</span>'
        f'</div>'
        f'<p class="text-sm font-black text-white truncate">{task_name}</p>'
        f'<p class="text-[9px] text-ark-muted mt-0.5">{reason}</p>'
        f'</div>'
        f'<button onclick="{fn}()" class="flex-shrink-0 bg-violet-500/15 hover:bg-violet-500/30 border border-violet-500/30 text-violet-300 text-[10px] font-black rounded-lg px-3 py-1.5 transition-all cursor-pointer">'
        f'⚡ 優先設定</button>'
        f'</div></div>'
        f'<script>'
        f'async function {fn}(){{'
        f'  const btn=event.target;btn.textContent="送信中...";btn.disabled=true;'
        f'  try{{'
        f'    const r=await fetch("https://api.github.com/repos/{gh_repo}/dispatches",{{'
        f'      method:"POST",'
        f'      headers:{{"Authorization":"Bearer {gh_pat}","Accept":"application/vnd.github+json","Content-Type":"application/json"}},'
        f'      body:JSON.stringify({{"event_type":"force_priority","client_payload":{{"task_name":"{task_name}","category":"{category}"}}}}),'
        f'    }});'
        f'    if(r.status===204){{btn.textContent="✅ 追加完了";btn.style.borderColor="#22c55e";btn.style.color="#4ade80";}}'
        f'    else{{btn.textContent="❌ エラー";btn.disabled=false;}}'
        f'  }}catch(e){{btn.textContent="❌ エラー";btn.disabled=false;}}'
        f'}}</script>'
    )

priority_candidates_html = ""
cards = []
if candidate_1:
    reason1 = f"過去5日間で{candidate_1[2]}回未達"
    cards.append(make_candidate_card(1, candidate_1[0], candidate_1[1], reason1, GH_PAT, GH_REPO))
if candidate_2:
    last = candidate_2[2] if candidate_2[2] != "never" else "期間内未完了"
    reason2 = f"最終完了日: {last}"
    cards.append(make_candidate_card(2, candidate_2[0], candidate_2[1], reason2, GH_PAT, GH_REPO))

if cards:
    priority_candidates_html = (
        '<div class="bg-ark-card border border-amber-500/20 rounded-2xl p-4 mt-4">'
        '<div class="flex items-center gap-2 mb-3">'
        '<svg class="w-4 h-4 text-amber-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>'
        '<p class="text-[10px] font-black text-violet-400 tracking-[.15em]">PRIORITY CANDIDATES</p>'
        '</div>'
        '<div class="flex flex-col gap-2">'
        + "\n".join(cards) +
        '</div></div>'
    )

judge_colors = {
    "green": ("text-green-400", "border-green-500/25"),
    "amber": ("text-amber-300", "border-amber-500/25"),
    "red":   ("text-red-400",   "border-red-500/25"),
}
judge_text_c, judge_border = judge_colors[judge_color]
cond_text_c = {"好調": "text-green-400", "普通": "text-amber-400", "不調": "text-red-400"}.get(condition, "text-amber-400")
sleep_c = "text-amber-300" if isinstance(sleep, float) and sleep < 7 else "text-white"

good_dot_size     = "w-8 h-8" if judge_label == "良好"   else "w-5 h-5"
caution_dot_size  = "w-8 h-8" if judge_label == "要注意" else "w-5 h-5"
alert_dot_size    = "w-8 h-8" if judge_label == "危険"   else "w-5 h-5"
good_dot_style    = "bg-green-400 shadow-[0_0_14px_rgba(34,197,94,.75)]"    if judge_label == "良好"   else "bg-green-500/15 border border-green-500/20"
caution_dot_style = "bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,.75)]"   if judge_label == "要注意" else "bg-amber-500/15 border border-amber-500/20"
alert_dot_style   = "bg-red-400 shadow-[0_0_14px_rgba(239,68,68,.75)]"      if judge_label == "危険"   else "bg-red-500/15 border border-red-500/20"
good_text_style    = "text-green-400 font-black"  if judge_label == "良好"   else "text-green-500/40 font-bold"
caution_text_style = "text-amber-400 font-black"  if judge_label == "要注意" else "text-amber-500/40 font-bold"
alert_text_style   = "text-red-400 font-black"    if judge_label == "危険"   else "text-red-500/40 font-bold"

generated_at = datetime.now(sgt).strftime("%H:%M")

PROJECT_START = datetime(2026, 4, 6, tzinfo=sgt)
target_date   = datetime.strptime(yesterday, "%Y-%m-%d").replace(tzinfo=sgt)
delta_days    = (target_date - PROJECT_START).days
week_num      = max(1, delta_days // 7 + 1)

month = target_date.month
if month <= 3:
    quarter, q_start_month = 1, 1
elif month <= 6:
    quarter, q_start_month = 2, 4
elif month <= 9:
    quarter, q_start_month = 3, 7
else:
    quarter, q_start_month = 4, 10
q_start = datetime(target_date.year, q_start_month, 1, tzinfo=sgt)
q_day   = (target_date - q_start).days + 1

header_date = f"{yesterday}\u00a0·\u00a0Week\u00a0{week_num}\u00a0·\u00a0Q{quarter}-Day\u00a0{q_day}"


# ── Weekly集計（先週月〜日）────────────────────────
_today = datetime.now(sgt)
_last_monday = _today - timedelta(days=_today.weekday() + 7)
_last_sunday  = _last_monday + timedelta(days=6)
w_period = f"{_last_monday.strftime('%m/%d')}（月）〜{_last_sunday.strftime('%m/%d')}（日）"
weekly_pages = []
for i in range(7):
    d = (_last_monday + timedelta(days=i)).strftime("%Y-%m-%d")
    _, p = fetch_page(d)
    if p:
        weekly_pages.append((d, p))

def w_avg(key):
    vals = []
    for _, p in weekly_pages:
        v = p.get(key, {}).get("formula", {}).get("number")
        if v is not None:
            vals.append(v)
    return round(sum(vals) / len(vals)) if vals else 0

w_score_w  = w_avg("【W】スコア")
w_score_c  = w_avg("【C】スコア")
w_score_ca = w_avg("【Ca】スコア")
w_score_i  = w_avg("【I】スコア")
w_score_total = round((w_score_w + w_score_c + w_score_ca + w_score_i) / 4)

w_weights = [p.get("体重", {}).get("number") for _, p in weekly_pages if p.get("体重", {}).get("number")]
w_sleeps  = [p.get("睡眠時間", {}).get("number") for _, p in weekly_pages if p.get("睡眠時間", {}).get("number")]
w_conds   = [p.get("体調", {}).get("select", {}) for _, p in weekly_pages]
w_cond_names = [c.get("name", "") for c in w_conds if c]

w_weight_avg = round(sum(w_weights) / len(w_weights), 2) if w_weights else "-"
w_sleep_avg  = round(sum(w_sleeps)  / len(w_sleeps),  2) if w_sleeps  else "-"
cond_counts = {}
for c in w_cond_names:
    cond_counts[c] = cond_counts.get(c, 0) + 1
if cond_counts:
    top_cond = sorted(cond_counts.items(), key=lambda x: -x[1])[0]
    w_cond_summary = f"{top_cond[0]}（{top_cond[1]}日）"
else:
    w_cond_summary = "-"

task_done_count = {}
cat_map = {
    "W":  ("【W】実績",  "Wellness"),
    "C":  ("【C】実績",  "Communication"),
    "Ca": ("【Ca】実績", "Career"),
    "I":  ("【I】実績",  "Input"),
}
import re as _re
TASK_ALIASES = {
    "ライアン": "動画視聴",
    "Soccer":    "動画視聴",
    "Scrambled": "動画視聴",
    "Youtube":   "動画視聴",
}
def normalize_task(name):
    base = _re.sub(r"（[^）]*）", "", name).strip()
    return TASK_ALIASES.get(base, base)

for _, p in weekly_pages:
    for cat_key, (done_key, cat_name) in cat_map.items():
        tasks = [t["name"].lstrip("🔥") for t in p.get(done_key, {}).get("multi_select", [])]
        for task in tasks:
            normalized = normalize_task(task)
            k = (normalized, cat_key)
            task_done_count[k] = task_done_count.get(k, 0) + 1

weekly_task_rows = {}
for cat_key in ["W", "C", "Ca", "I"]:
    rows = [(t, c) for (t, c), cnt in sorted(task_done_count.items(), key=lambda x: -x[1]) if c == cat_key]
    weekly_task_rows[cat_key] = rows

# ── Monthly集計（先月1日〜末日）────────────────────────
_first_this_month = _today.replace(day=1)
_last_month_end   = _first_this_month - timedelta(days=1)
_last_month_start = _last_month_end.replace(day=1)
m_period = _last_month_start.strftime("%Y年%-m月")
monthly_pages = []
_d = _last_month_start
while _d <= _last_month_end:
    _, p = fetch_page(_d.strftime("%Y-%m-%d"))
    if p:
        monthly_pages.append((_d.strftime("%Y-%m-%d"), p))
    _d += timedelta(days=1)

def m_avg(key):
    vals = []
    for _, p in monthly_pages:
        v = p.get(key, {}).get("formula", {}).get("number")
        if v is not None:
            vals.append(v)
    return round(sum(vals) / len(vals)) if vals else 0

m_score_w  = m_avg("【W】スコア")
m_score_c  = m_avg("【C】スコア")
m_score_ca = m_avg("【Ca】スコア")
m_score_i  = m_avg("【I】スコア")
m_score_total = round((m_score_w + m_score_c + m_score_ca + m_score_i) / 4)

m_weights = [p.get("体重", {}).get("number") for _, p in monthly_pages if p.get("体重", {}).get("number")]
m_sleeps  = [p.get("睡眠時間", {}).get("number") for _, p in monthly_pages if p.get("睡眠時間", {}).get("number")]
m_conds   = [p.get("体調", {}).get("select", {}) for _, p in monthly_pages]
m_cond_names = [c.get("name", "") for c in m_conds if c]

m_weight_avg = round(sum(m_weights) / len(m_weights), 2) if m_weights else "-"
m_sleep_avg  = round(sum(m_sleeps)  / len(m_sleeps),  2) if m_sleeps  else "-"
m_cond_counts = {}
for c in m_cond_names:
    m_cond_counts[c] = m_cond_counts.get(c, 0) + 1
if m_cond_counts:
    m_top_cond = sorted(m_cond_counts.items(), key=lambda x: -x[1])[0]
    m_cond_summary = f"{m_top_cond[0]}（{m_top_cond[1]}日）"
else:
    m_cond_summary = "-"

m_task_done_count = {}
for _, p in monthly_pages:
    for cat_key, (done_key, cat_name) in cat_map.items():
        tasks = [t["name"].lstrip("🔥") for t in p.get(done_key, {}).get("multi_select", [])]
        for task in tasks:
            normalized = normalize_task(task)
            k = (normalized, cat_key)
            m_task_done_count[k] = m_task_done_count.get(k, 0) + 1

monthly_task_rows = {}
for cat_key in ["W", "C", "Ca", "I"]:
    rows = [(t, c) for (t, c), cnt in sorted(m_task_done_count.items(), key=lambda x: -x[1]) if c == cat_key]
    monthly_task_rows[cat_key] = rows

if m_score_total >= 80:
    m_judge_label, m_judge_color = "🏅絶好調", "green"
elif m_score_total >= 50:
    m_judge_label, m_judge_color = "📊成長中", "amber"
else:
    m_judge_label, m_judge_color = "🔄要改善", "red"

m_judge_colors = {
    "green": ("text-green-400", "border-green-500/25"),
    "amber": ("text-amber-300", "border-amber-500/25"),
    "red":   ("text-red-400",   "border-red-500/25"),
}
m_judge_text_c, m_judge_border = m_judge_colors[m_judge_color]

w_badge_html = majority_load([d for d, _ in weekly_pages], "週")
m_badge_html = majority_load([d for d, _ in monthly_pages], "月")


# ── ▼ ジャーナリングデータ取得（Weekly・Monthly）─────
w_journal_entries = fetch_journal_entries(
    _last_monday.strftime("%Y-%m-%d"),
    _last_sunday.strftime("%Y-%m-%d"),
)
w_journal_weekly_entries = fetch_weekly_journal_entries(
    _last_monday.strftime("%Y-%m-%d"),
    _last_sunday.strftime("%Y-%m-%d"),
)

m_journal_entries = fetch_journal_entries(
    _last_month_start.strftime("%Y-%m-%d"),
    _last_month_end.strftime("%Y-%m-%d"),
)
m_journal_weekly_entries = fetch_weekly_journal_entries(
    _last_month_start.strftime("%Y-%m-%d"),
    _last_month_end.strftime("%Y-%m-%d"),
)
_last_month_yymm = _last_month_start.strftime("%y%m")
m_journal_monthly_entries = fetch_monthly_journal_entries(_last_month_yymm)
# ── ▲ ジャーナリングデータ取得ここまで ─────────────


# ── ▼ トレーニングデータ取得 ─────────────────────
today_training   = fetch_training_data(yesterday)
weekly_training  = fetch_training_period(_last_monday.strftime("%Y-%m-%d"), _last_sunday.strftime("%Y-%m-%d"))
monthly_training = fetch_training_period(_last_month_start.strftime("%Y-%m-%d"), _last_month_end.strftime("%Y-%m-%d"))
today_training_html   = training_card_html(today_training,  "YESTERDAY'S TRAINING")
weekly_training_html  = training_summary_html(weekly_training,  "WEEKLY")
monthly_training_html = training_summary_html(monthly_training, "MONTHLY")
# ── ▲ トレーニングデータ取得ここまで ─────────────

# ── ▼ 英語学習データ取得 ─────────────────────────
topic_cards = fetch_topic_cards()
weekly_reuse_logs  = fetch_reuse_log_period(
    _last_monday.strftime("%Y-%m-%d"),
    _last_sunday.strftime("%Y-%m-%d")
)
monthly_reuse_logs = fetch_reuse_log_period(
    _last_month_start.strftime("%Y-%m-%d"),
    _last_month_end.strftime("%Y-%m-%d")
)
# ── ▲ 英語学習データ取得ここまで ─────────────────

# ── ▼ 英語学習AI分析実行 ─────────────────────────
w_english_overall, w_english_retention, w_english_priority = generate_english_analysis(
    topic_cards, weekly_reuse_logs, w_score_c
)
m_english_overall, m_english_retention, m_english_priority = generate_english_analysis(
    topic_cards, monthly_reuse_logs, m_score_c
)
# ── ▲ 英語学習AI分析実行ここまで ─────────────────


# ── ▼ generate_weekly_comment（ジャーナリング統合版）──
def generate_weekly_comment(
    w_score_w, w_score_c, w_score_ca, w_score_i, w_score_total,
    w_weight_avg, w_sleep_avg, w_cond_summary, task_done_count,
    journal_entries=None,
    journal_weekly_entries=None,
    topic_cards=None,
    reuse_logs=None,
):
    if not ANTHROPIC_API_KEY:
        return [], ""

    top_tasks = sorted(task_done_count.items(), key=lambda x: -x[1])[:10]
    done_str = "\n".join([f"・{t}({c}): {cnt}回" for (t, c), cnt in top_tasks]) or "なし"

    missed_tasks_w = []
    for _, p in weekly_pages:
        for cat_key, (done_key, cat_name) in cat_map.items():
            plan_key = f"【{cat_key}】予定タスク"
            plan = [t["name"].lstrip("🔥") for t in p.get(plan_key, {}).get("multi_select", [])]
            done = [t["name"].lstrip("🔥") for t in p.get(done_key, {}).get("multi_select", [])]
            for task in plan:
                if task not in done:
                    missed_tasks_w.append(f"{cat_name}: {task}")
    missed_str = "\n".join(list(dict.fromkeys(missed_tasks_w))[:8]) or "なし"

    journal_section = build_journal_prompt_section(journal_entries or [])
    english_section = build_english_prompt_section(topic_cards or [], reuse_logs or [])
    weekly_journal_section = build_weekly_journal_section(journal_weekly_entries or [])

    has_journal = bool(journal_section or weekly_journal_section)
    journal_instruction = (
        "\nジャーナリングデータも踏まえ、以下を分析に含めてください:\n"
        "・今週繰り返し現れた放電源・充電源のパターン\n"
        "・最も強く出ていたNVCのニーズ（安心・つながり・自律・承認 等）\n"
        "・感情と行動習慣（タスク達成）の相関\n"
    ) if has_journal else ""

    analysis_instruction = (
        "体重・睡眠・体調・完了タスク・未達タスク"
        + ("・ジャーナリング(感情パターン・ニーズ・放電充電)" if has_journal else "")
        + "を総合的に踏まえた今週の総合評価・考察・改善提案を200字程度で記載。来週への具体的アクションも含めること。"
    )

    prompt = (
        "あなたはSpring Arkプロジェクトのパーソナルコーチです。\n"
        "以下の週次データをもとに、分析レポートをJSON形式で出力してください。\n\n"
        f"【今週のコンディション】\n"
        f"- 体重平均: {w_weight_avg}kg\n"
        f"- 睡眠平均: {w_sleep_avg}h\n"
        f"- 体調: {w_cond_summary}\n"
        f"- 週平均スコア: W:{w_score_w} / C:{w_score_c} / Ca:{w_score_ca} / I:{w_score_i} / 総合:{w_score_total}\n\n"
        f"【実施できた主なタスク】\n{done_str}\n\n"
        f"【未達が多かったタスク】\n{missed_str}\n"
        + weekly_journal_section
        + journal_section
        + english_section
        + journal_instruction
        + f"\n【総合分析の指示】{analysis_instruction}\n"
        + "\n【出力形式】必ずJSONオブジェクトのみ出力してください。他のテキストは一切不要。\n"
        "{\n"
        '  "summaries": [\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"},\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"},\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"}\n'
        "  ],\n"
        '  "analysis": "ここに総合分析を記載"\n'
        "}"
    )

    import json as _j
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 3000, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        text = res.json()["content"][0]["text"].strip()
        start_j, end_j = text.find("{"), text.rfind("}") + 1
        if start_j >= 0 and end_j > start_j:
            parsed = _j.loads(text[start_j:end_j])
            return validate_weekly_monthly(parsed)
    except Exception as e:
        print(f"[WARN] Weekly Claude API error: {e}")
    return validate_weekly_monthly({})
# ── ▲ generate_weekly_comment ここまで ──────────────


# ── ▼ generate_monthly_comment（ジャーナリング統合版）─
def generate_monthly_comment(
    m_score_w, m_score_c, m_score_ca, m_score_i, m_score_total,
    m_weight_avg, m_sleep_avg, m_cond_summary, m_task_done_count,
    journal_entries=None,
    journal_weekly_entries=None,
    journal_monthly_entries=None,
    topic_cards=None,
    reuse_logs=None,
):
    if not ANTHROPIC_API_KEY:
        return [], ""

    top_tasks = sorted(m_task_done_count.items(), key=lambda x: -x[1])[:12]
    done_str = "\n".join([f"・{t}({c}): {cnt}回" for (t, c), cnt in top_tasks]) or "なし"

    monthly_journal_section = build_monthly_journal_section(journal_monthly_entries or [])
    weekly_journal_section  = build_weekly_journal_section(journal_weekly_entries or [])
    daily_journal_section   = build_journal_monthly_section(journal_entries or [])
    english_section = build_english_prompt_section(topic_cards or [], reuse_logs or [])
    has_journal = bool(monthly_journal_section or weekly_journal_section or daily_journal_section)
    journal_instruction = (
        "\nジャーナリングデータも踏まえ、以下を月次分析に含めてください:\n"
        "・月を通じて繰り返された放電パターンと根本ニーズ\n"
        "・最も頻出したNVCのニーズとその充足度の変化\n"
        "・習慣（タスク達成）と感情エネルギーの相関\n"
        "・来月に向けた具体的な一つの実験提案\n"
    ) if has_journal else ""

    analysis_instruction = (
        "体重・睡眠・体調・完了タスク"
        + ("・ジャーナリング(感情パターン・ニーズの変化・放電充電の傾向)" if has_journal else "")
        + "を総合的に踏まえた今月の総合評価・考察・改善提案を200字程度で記載。来月への具体的な一つの実験も含めること。"
    )

    prompt = (
        "あなたはSpring Arkプロジェクトのパーソナルコーチです。\n"
        "以下の月次データをもとに、月次分析レポートをJSON形式で出力してください。\n\n"
        f"【今月のコンディション】\n"
        f"- 体重平均: {m_weight_avg}kg\n"
        f"- 睡眠平均: {m_sleep_avg}h\n"
        f"- 体調: {m_cond_summary}\n"
        f"- 月平均スコア: W:{m_score_w} / C:{m_score_c} / Ca:{m_score_ca} / I:{m_score_i} / 総合:{m_score_total}\n\n"
        f"【実施できた主なタスク（上位）】\n{done_str}\n"
        + monthly_journal_section
        + weekly_journal_section
        + daily_journal_section
        + english_section
        + journal_instruction
        + f"\n【総合分析の指示】{analysis_instruction}\n"
        + "\n【出力形式】必ずJSONオブジェクトのみ出力してください。他のテキストは一切不要。\n"
        "{\n"
        '  "summaries": [\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"},\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"},\n'
        '    {"title": "要点タイトル(15文字以内)", "detail": "具体的分析(40文字以内)"}\n'
        "  ],\n"
        '  "analysis": "ここに総合分析を記載"\n'
        "}"
    )

    import json as _j
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        text = res.json()["content"][0]["text"].strip()
        start_j, end_j = text.find("{"), text.rfind("}") + 1
        if start_j >= 0 and end_j > start_j:
            parsed = _j.loads(text[start_j:end_j])
            return validate_weekly_monthly(parsed)
    except Exception as e:
        print(f"[WARN] Monthly Claude API error: {e}")
    return validate_weekly_monthly({})
# ── ▲ generate_monthly_comment ここまで ─────────────


# ── Weekly/Monthly AIコメント生成 ─────────────────

# ── ▼ 英語分析パネルHTML ─────────────────────────
def make_english_panel_html(overall, retention, priority, reuse_logs, topic_cards):
    if not overall and not retention and not priority:
        return '<p class="text-xs text-ark-muted text-center py-4">英語学習データがありません</p>'

    total = len(reuse_logs)
    used_count = sum(1 for l in reuse_logs if l["used"])
    used_rate = round(used_count / total * 100) if total > 0 else 0

    cards_html = ""
    for c in topic_cards:
        score = c["score"]
        bar_w = score * 20
        last = c["last_date"][-5:] if c["last_date"] else "未練習"
        cards_html += (
            f'<div class="flex items-center gap-2 py-1.5 border-b border-ark-border/30 last:border-0">'
            f'<div class="flex-1 min-w-0">'
            f'<p class="text-xs text-white/80 truncate">{c["topic"]}</p>'
            f'<p class="text-[9px] text-ark-muted">{c["group"]} · 最終:{last}</p>'
            f'</div>'
            f'<div class="flex items-center gap-1.5 flex-shrink-0">'
            f'<div class="w-16 h-1.5 bg-ark-dim rounded-full overflow-hidden">'
            f'<div class="h-full bg-amber-400/70 rounded-full" style="width:{bar_w}%"></div>'
            f'</div>'
            f'<span class="text-[9px] text-amber-400 font-black w-6 text-right">{score}/5</span>'
            f'</div></div>'
        )

    sections = []
    if overall:
        sections.append(
            f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
            f'<p class="text-[9px] font-black text-amber-400 mb-1">総合評価</p>'
            f'<p class="text-xs text-white/80 leading-relaxed">{overall}</p>'
            f'</div>'
        )
    if retention:
        sections.append(
            f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
            f'<p class="text-[9px] font-black text-amber-400 mb-1">フレーズ定着率　{used_rate}%（{used_count}/{total}件）</p>'
            f'<p class="text-xs text-white/80 leading-relaxed">{retention}</p>'
            f'</div>'
        )
    if priority:
        sections.append(
            f'<div class="bg-ark-dim/40 border border-teal-500/20 rounded-xl px-3 py-2.5">'
            f'<p class="text-[9px] font-black text-teal-400 mb-1">優先練習トピック</p>'
            f'<p class="text-xs text-white/80 leading-relaxed">{priority}</p>'
            f'</div>'
        )
    if cards_html:
        sections.append(
            f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
            f'<p class="text-[9px] font-black text-amber-400 mb-1.5">トピックカード</p>'
            + cards_html +
            f'</div>'
        )

    return '<div class="flex flex-col gap-2">' + "\n".join(sections) + '</div>'

w_english_panel_html = make_english_panel_html(
    w_english_overall, w_english_retention, w_english_priority,
    weekly_reuse_logs, topic_cards
)
m_english_panel_html = make_english_panel_html(
    m_english_overall, m_english_retention, m_english_priority,
    monthly_reuse_logs, topic_cards
)
# ── ▲ 英語分析パネルHTML ここまで ──────────────────

monthly_summaries, monthly_analysis = generate_monthly_comment(
    m_score_w, m_score_c, m_score_ca, m_score_i, m_score_total,
    m_weight_avg, m_sleep_avg, m_cond_summary, m_task_done_count,
    journal_entries=m_journal_entries,
    journal_weekly_entries=m_journal_weekly_entries,
    journal_monthly_entries=m_journal_monthly_entries,
    topic_cards=topic_cards,
    reuse_logs=monthly_reuse_logs,
)

monthly_comment_html = ""
if monthly_summaries or monthly_analysis:
    m_items = []
    for i, s in enumerate(monthly_summaries, 1):
        m_items.append(
            f'<div class="flex items-start gap-3 bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
            f'<span class="w-5 h-5 rounded-full bg-violet-500/25 border border-violet-500/35 text-[9px] font-black text-violet-300 flex items-center justify-center flex-shrink-0 mt-0.5">{i}</span>'
            f'<div><p class="text-xs font-black text-white">{s.get("title","")}</p>'
            f'<p class="text-[10px] text-ark-muted mt-0.5">{s.get("detail","")}</p></div>'
            f'</div>'
        )
    m_analysis_html = (
        f'<div class="bg-ark-dim/30 border border-ark-border rounded-xl px-3 py-3 mt-1">'
        f'<p class="text-[10px] font-black text-violet-400 mb-1.5">総合分析</p>'
        f'<p class="text-xs text-white/75 leading-relaxed">{monthly_analysis}</p>'
        f'</div>'
    ) if monthly_analysis else ""

    m_score_panel = (
        '<div class="flex flex-col gap-2">' + "\n".join(m_items) + m_analysis_html + '</div>'
    )

    m_journal_panel = (
        '<div class="flex flex-col gap-2">'
        '<p class="text-xs text-ark-muted text-center py-4">ジャーナリングデータがありません</p>'
        '</div>'
    )
    if m_journal_monthly_entries:
        mj_items = []
        for e in m_journal_monthly_entries:
            if e.get("emotion_structure"):
                mj_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">感情パターン</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["emotion_structure"]}</p>'
                    f'</div>'
                )
            if e.get("charge_discharge"):
                mj_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">放電 / 充電</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["charge_discharge"]}</p>'
                )
            if e.get("needs_priority"):
                mj_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">ニーズの優先順位</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["needs_priority"]}</p>'
                    f'</div>'
                )
            if e.get("habit_emotion"):
                mj_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">行動と感情の相関</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["habit_emotion"]}</p>'
                    f'</div>'
                )
            if e.get("next_experiment"):
                mj_items.append(
                    f'<div class="bg-ark0 rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">来月への設計提案</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["next_experiment"]}</p>'
                    f'</div>'
                )
        if mj_items:
            m_journal_panel = '<div class="flex flex-col gap-2">' + "\n".join(mj_items) + '</div>'

    monthly_comment_html = (
        '<div class="stripe bg-ark-card border border-violet-500/20 rounded-2xl p-4 glow-violet">'
        '<div class="flex items-center justify-between mb-4">'
        '<div class="inline-flex bg-ark-dim rounded-full p-0.5 gap-0.5">'
        '<button id="m-tab-score" onclick="switchMTab(\'score\')" '
        'class="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border">'
        'AI分析</button>'
        '<button id="m-tab-english" onclick="switchMTab(\'english\')" '
        'class="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '📊 英語分析</button>'
        '<button id="m-tab-journal" onclick="switchMTab(\'journal\')" '
        'class="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '🔒 ジャーナリング</button>'
        '<button id="m-tab-training" onclick="switchMTab(\'training\')" '
        'class="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '💪 トレーニング</button>'
        '</div></div>'
        '<div id="m-panel-score">' + m_score_panel + '</div>'
        '<div id="m-panel-english" style="display:none">' + m_english_panel_html + '</div>'
        '<div id="m-panel-journal" style="display:none">' + m_journal_panel + '</div>'
        '<div id="m-panel-training" style="display:none">' + monthly_training_html + '</div>'
        '</div>'
        '<script>'
        'function switchMTab(t){'
        '  var ON="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border";'
        '  var OFF="m-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted";'
        '  document.getElementById("m-panel-score").style.display=t==="score"?"":"none";'
        '  document.getElementById("m-panel-english").style.display=t==="english"?"":"none";'
        '  document.getElementById("m-panel-journal").style.display=t==="journal"?"":"none";'
        '  document.getElementById("m-panel-training").style.display=t==="training"?"":"none";'
        '  document.getElementById("m-tab-score").className=t==="score"?ON:OFF;'
        '  document.getElementById("m-tab-english").className=t==="english"?ON:OFF;'
        '  document.getElementById("m-tab-journal").className=t==="journal"?ON:OFF;'
        '  document.getElementById("m-tab-training").className=t==="training"?ON:OFF;'
        '}'
        '</script>'
    )
else:
    monthly_comment_html = '<p class="text-xs text-ark-muted text-center py-4">月次分析データがありません</p>'

if w_score_total >= 80:
    w_judge_label, w_judge_color = "🏻絶好調", "green"
elif w_score_total >= 50:
    w_judge_label, w_judge_color = "📈成長中", "amber"
else:
    w_judge_label, w_judge_color = "🔧要改善", "red"

w_judge_colors = {
    "green": ("text-green-400", "border-green-500/25"),
    "amber": ("text-amber-300", "border-amber-500/25"),
    "red":   ("text-red-400",   "border-red-500/25"),
}
w_judge_text_c, w_judge_border = w_judge_colors[w_judge_color]

weekly_summaries, weekly_analysis = generate_weekly_comment(
    w_score_w, w_score_c, w_score_ca, w_score_i, w_score_total,
    w_weight_avg, w_sleep_avg, w_cond_summary, task_done_count,
    journal_entries=w_journal_entries,
    journal_weekly_entries=w_journal_weekly_entries,
    topic_cards=topic_cards,
    reuse_logs=weekly_reuse_logs,
)

weekly_comment_html = ""
if weekly_summaries or weekly_analysis:
    items = []
    for i, s in enumerate(weekly_summaries, 1):
        items.append(
            f'<div class="flex items-start gap-3 bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
            f'<span class="w-5 h-5 rounded-full bg-violet-500/25 border border-violet-500/35 text-[9px] font-black text-violet-300 flex items-center justify-center flex-shrink-0 mt-0.5">{i}</span>'
            f'<div><p class="text-xs font-black text-white">{s.get("title","")}</p>'
            f'<p class="text-[10px] text-ark-muted mt-0.5">{s.get("detail","")}</p></div>'
            f'</div>'
        )
    analysis_html = (
        f'<div class="bg-ark-dim/30 border border-ark-border rounded-xl px-3 py-3 mt-1">'
        f'<p class="text-[10px] font-black text-violet-400 mb-1.5">総合分析</p>'
        f'<p class="text-xs text-white/75 leading-relaxed">{weekly_analysis}</p>'
        f'</div>'
    ) if weekly_analysis else ""

    score_panel = (
        '<div class="flex flex-col gap-2">' + "\n".join(items) + analysis_html + '</div>'
    )

    journal_panel = (
        '<div class="flex flex-col gap-2">'
        '<p class="text-xs text-ark-muted text-center py-4">ジャーナリングデータがありません</p>'
        '</div>'
    )
    if w_journal_entries or w_journal_weekly_entries:
        j_items = []
        for e in (w_journal_weekly_entries or []):
            if e.get("emotion_pattern"):
                j_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">感情パターン</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["emotion_pattern"]}</p>'
                    f'</div>'
                )
            if e.get("needs"):
                j_items.append(
                    f'<div class="bg-ark-dim/40 border border-ark-border rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">奥にあるニーズ</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["needs"]}</p>'
                    f'</div>'
                )
            if e.get("next_question"):
                j_items.append(
                    f'<div class="bg-ark-dim/40 border border-teal-500/20 rounded-xl px-3 py-2.5">'
                    f'<p class="text-[9px] font-black text-teal-400 mb-1">来週への問い</p>'
                    f'<p class="text-xs text-white/80 leading-relaxed">{e["next_question"]}</p>'
                    f'</div>'
                )
        if j_items:
            journal_panel = '<div class="flex flex-col gap-2">' + "\n".join(j_items) + '</div>'

    weekly_comment_html = (
        '<div class="stripe bg-ark-card border border-violet-500/20 rounded-2xl p-4 glow-violet">'
        '<div class="flex items-center justify-between mb-4">'
        '<div class="inline-flex bg-ark-dim rounded-full p-0.5 gap-0.5">'
        '<button id="w-tab-score" onclick="switchWTab(\'score\')" '
        'class="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border">'
        'AI分析</button>'
        '<button id="w-tab-english" onclick="switchWTab(\'english\')" '
        'class="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '📊 英語分析</button>'
        '<button id="w-tab-journal" onclick="switchWTab(\'journal\')" '
        'class="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '🔒 ジャーナリング</button>'
        '<button id="w-tab-training" onclick="switchWTab(\'training\')" '
        'class="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted">'
        '💪 トレーニング</button>'
        '</div></div>'
        '<div id="w-panel-score">' + score_panel + '</div>'
        '<div id="w-panel-english" style="display:none">' + w_english_panel_html + '</div>'
        '<div id="w-panel-journal" style="display:none">' + journal_panel + '</div>'
        '<div id="w-panel-training" style="display:none">' + weekly_training_html + '</div>'
        '</div>'
        '<script>'
        'function switchWTab(t){'
        '  var ON="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border";'
        '  var OFF="w-tab-btn text-[10px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted";'
        '  document.getElementById("w-panel-score").style.display=t==="score"?"":"none";'
        '  document.getElementById("w-panel-english").style.display=t==="english"?"":"none";'
        '  document.getElementById("w-panel-journal").style.display=t==="journal"?"":"none";'
        '  document.getElementById("w-panel-training").style.display=t==="training"?"":"none";'
        '  document.getElementById("w-tab-score").className=t==="score"?ON:OFF;'
        '  document.getElementById("w-tab-english").className=t==="english"?ON:OFF;'
        '  document.getElementById("w-tab-journal").className=t==="journal"?ON:OFF;'
        '  document.getElementById("w-tab-training").className=t==="training"?ON:OFF;'
        '}'
        '</script>'
    )
else:
    weekly_comment_html = '<p class="text-xs text-ark-muted text-center py-4">週次分析データがありません</p>'


def weekly_task_card(name, subtitle, icon_svg, color, score, task_rows_list):
    color_map = {
        "green": ("text-green-400", "bg-green-500/10 border-green-500/20", "border-ark-border",   "from-green-600 to-emerald-400"),
        "amber": ("text-amber-400", "bg-amber-500/10 border-amber-500/20", "border-amber-500/20", "from-amber-500 to-yellow-400"),
        "rose":  ("text-rose-400",  "bg-rose-500/10 border-rose-500/20",   "border-rose-500/25",  "from-rose-600 to-red-400"),
        "sky":   ("text-sky-400",   "bg-sky-500/10 border-sky-500/20",     "border-sky-500/20",   "from-sky-500 to-cyan-400"),
    }
    text_c, icon_wrap, card_border, bar_grad = color_map[color]
    items_html = ""
    for task_name, cat_key in task_rows_list:
        cnt = task_done_count.get((task_name, cat_key), 0)
        if cnt == 0:
            continue
        items_html += (
            f'<div class="flex items-center gap-1.5 py-[3px]">'
            f'<div class="w-3.5 h-3.5 rounded-full flex-shrink-0 bg-green-500/25 border border-green-400/60 flex items-center justify-center">'
            f'<span class="text-[7px] font-black text-green-400">{cnt}</span></div>'
            f'<span class="text-xs flex-1 leading-tight text-white/80">{task_name}</span>'
            f'</div>'
        )
    if not items_html:
        rows_html = '<p class="text-xs italic py-1" style="color:rgba(74,90,114,0.7)">今週の実績なし</p>'
    else:
        rows_html = '<div class="grid grid-cols-2 gap-x-3 gap-y-0.5">' + items_html + '</div>'
    return (
        '<div class="ark-card bg-ark-card border ' + card_border + ' rounded-2xl p-4 min-h-[120px]">'
        '<div class="flex items-start justify-between mb-3">'
        '<div class="flex items-center gap-2.5">'
        '<div class="w-8 h-8 rounded-xl ' + icon_wrap + ' border flex items-center justify-center flex-shrink-0">'
        '<span class="' + text_c + '">' + icon_svg + '</span>'
        '</div>'
        '<div>'
        '<p class="text-xs font-black ' + text_c + ' tracking-[.15em]">' + name + '</p>'
        '<p class="text-xs text-ark-muted">' + subtitle + '</p>'
        '</div></div>'
        '<p class="text-xl font-black ' + text_c + '">' + str(score) + '<span class="text-sm text-ark-muted font-normal">/100点</span></p>'
        '</div>'
        '<div class="mb-3"><div class="h-1.5 bg-ark-dim rounded-full overflow-hidden">'
        '<div class="h-full rounded-full bg-gradient-to-r ' + bar_grad + ' bar" style="width:' + str(score) + '%"></div>'
        '</div></div>'
        + rows_html
        + '</div>'
    )

weekly_cards_html = (
    weekly_task_card("WELLNESS",      "運動・食事・精神",  ICON_W,  "green", w_score_w,  weekly_task_rows["W"],  ) +
    weekly_task_card("COMMUNICATION", "英語学習・実践",    ICON_C,  "amber", w_score_c,  weekly_task_rows["C"],  ) +
    weekly_task_card("CAREER",        "AI・ビジネス・CPA", ICON_CA, "rose",  w_score_ca, weekly_task_rows["Ca"], ) +
    weekly_task_card("INPUT",         "読書・NewsPicks",   ICON_I,  "sky",   w_score_i,  weekly_task_rows["I"],  )
)

monthly_cards_html = (
    weekly_task_card("WELLNESS",      "運動・食事・精神",  ICON_W,  "green", m_score_w,  monthly_task_rows["W"],  ) +
    weekly_task_card("COMMUNICATION", "英語学習・実践",    ICON_C,  "amber", m_score_c,  monthly_task_rows["C"],  ) +
    weekly_task_card("CAREER",        "AI・ビジネス・CPA", ICON_CA, "rose",  m_score_ca, monthly_task_rows["Ca"], ) +
    weekly_task_card("INPUT",         "読書・NewsPicks",   ICON_I,  "sky",   m_score_i,  monthly_task_rows["I"],  )
)

cards_html = (
    category_card("WELLNESS",      "運動・食事・精神",  ICON_W,  "green", score_w,  plan_w,  done_w)  +
    category_card("COMMUNICATION", "英語学習・実践",    ICON_C,  "amber", score_c,  plan_c,  done_c)  +
    category_card("CAREER",        "AI・ビジネス・CPA", ICON_CA, "rose",  score_ca, plan_ca, done_ca) +
    category_card("INPUT",         "読書・NewsPicks",   ICON_I,  "sky",   score_i,  plan_i,  done_i)
)

# ── HTML組み立て ──────────────────────────────────
html = (
    "<!DOCTYPE html>\n"
    '<html lang="ja">\n'
    "<head>\n"
    '  <meta charset="UTF-8">\n'
    '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    "  <title>SPRING ARK — Daily Dashboard</title>\n"
    '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900'
    '&family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">\n'
    '  <script src="https://cdn.tailwindcss.com"></script>\n'
    "  <script>\n"
    "    tailwind.config = {\n"
    "      theme: {\n"
    "        extend: {\n"
    "          fontFamily: { sans: ['Inter', '\"Noto Sans JP\"', 'sans-serif'] },\n"
    "          colors: {\n"
    "            ark: {\n"
    "              bg: '#07090F', card: '#0F1623',\n"
    "              border: '#1B2A40', muted: '#4A5A72', dim: '#1E2C42',\n"
    "            }\n"
    "          }\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "  </script>\n"
    "  <style>\n"
    "    body { background: #07090F; }\n"
    "    ::-webkit-scrollbar { width: 0; }\n"
    "    .glow-amber { box-shadow: 0 0 28px rgba(251,191,36,.14); }\n"
    "    .glow-violet{ box-shadow: 0 0 20px rgba(139,92,246,.12); }\n"
    "    .bar { transition: width 1.4s cubic-bezier(.4,0,.2,1); }\n"
    "    .ark-card { transition: border-color .2s; }\n"
    "    .ark-card:hover { border-color: #2D4060; }\n"
    "    .stripe {\n"
    "      background: repeating-linear-gradient(\n"
    "        -45deg, transparent, transparent 14px,\n"
    "        rgba(139,92,246,.025) 14px, rgba(139,92,246,.025) 28px\n"
    "      );\n"
    "    }\n"
    "    .priority-row {\n"
    "      background: linear-gradient(90deg, rgba(251,191,36,.05) 0%, transparent 100%);\n"
    "      border-left: 2px solid rgba(251,191,36,.45);\n"
    "      padding-left: 6px;\n"
    "      border-radius: 4px;\n"
    "    }\n"
    "    @keyframes pulse-slow { 0%,100%{opacity:1} 50%{opacity:.4} }\n"
    "    .animate-pulse-slow { animation: pulse-slow 3s ease-in-out infinite; }\n"
    "  </style>\n"
    "</head>\n"
    '<body class="min-h-screen text-white antialiased">\n'
    '<div class="max-w-5xl mx-auto px-4 py-6 flex flex-col gap-5">\n'

    "\n  <header class=\"flex items-start justify-between\">\n"
    "    <div>\n"
    "      <div class=\"flex items-baseline gap-2.5 mb-1\">\n"
    "        <h1 class=\"text-2xl font-black tracking-tight\">SPRING ARK</h1>\n"
    "<div class=\"inline-flex bg-ark-dim rounded-full p-0.5 gap-0.5\"><button id=\"tab-daily\" onclick=\"switchTab('daily')\" class=\"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border\">Daily</button><button id=\"tab-weekly\" onclick=\"switchTab('weekly')\" class=\"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted\">Weekly</button><button id=\"tab-monthly\" onclick=\"switchTab('monthly')\" class=\"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted\">Monthly</button></div>\n"
    "      </div>\n"
    f"      <p class=\"text-xs text-ark-muted\">{header_date}</p>\n"
    "    </div>\n"
    + '<div id="badge-daily">' + load_badge_html + '</div>'
    + '<div id="badge-weekly" style="display:none">' + w_badge_html + '</div>'
    + '<div id="badge-monthly" style="display:none">' + m_badge_html + '</div>'
    + "  </header>\n"

    + '<div id="daily-view">'

    "\n  <section>\n"
    "    <span class=\"text-[10px] font-bold text-ark-muted tracking-[.2em] uppercase block mb-2\">Today's Condition</span>\n"
    f"    <div class=\"bg-ark-card border {judge_border} rounded-2xl p-5 glow-amber\">\n"
    "      <div class=\"flex flex-col sm:flex-row sm:items-center gap-5\">\n"
    "        <div class=\"flex items-center gap-4\">\n"
    "          <div class=\"flex items-end gap-2.5\">\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{good_dot_size} rounded-full {good_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {good_text_style}\">良好</span>\n"
    "            </div>\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{caution_dot_size} rounded-full {caution_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {caution_text_style}\">要注意</span>\n"
    "            </div>\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{alert_dot_size} rounded-full {alert_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {alert_text_style}\">危険</span>\n"
    "            </div>\n"
    "          </div>\n"
    "          <div class=\"w-px h-12 bg-ark-border\"></div>\n"
    "          <div>\n"
    f"            <p class=\"text-4xl font-black {judge_text_c} leading-none mb-1\">{judge_label}</p>\n"
    "          </div>\n"
    "        </div>\n"
    "        <div class=\"flex gap-3 sm:ml-auto\">\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-xs text-ark-muted mb-1\">体重</p>\n"
    f"            <p class=\"text-xl font-black text-white\">{weight}<span class=\"text-xs font-normal text-ark-muted\">kg</span></p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-xs text-ark-muted mb-1\">睡眠</p>\n"
    f"            <p class=\"text-xl font-black {sleep_c}\">{sleep}<span class=\"text-xs font-normal\">h</span></p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-xs text-ark-muted mb-1\">体調</p>\n"
    f"            <p class=\"text-xl font-black {cond_text_c}\">{condition}</p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-xs text-ark-muted mb-1\">総合</p>\n"
    f"            <p class=\"text-xl font-black {judge_text_c}\">{score_total}<span class=\"text-xs font-normal text-ark-muted\">点</span></p>\n"
    "          </div>\n"
    "        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n"

    "\n  <div class=\"grid grid-cols-1 md:grid-cols-2 gap-5\">\n"
    "    <div class=\"flex flex-col gap-3\">\n"
    + cards_html
    + today_training_html +
    "    </div>\n"
    "    <div class=\"flex flex-col gap-4\">\n"
    + calendar_html +
    "      <div class=\"stripe bg-ark-card border border-violet-500/20 rounded-2xl p-4 glow-violet flex-1\">\n"
    "        <div class=\"flex items-center gap-2 mb-5\">\n"
    "          <div class=\"w-7 h-7 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center\">\n"
    "            <svg class=\"w-4 h-4 text-violet-400\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\">"
    "<path d=\"M8 4 L7.5 7\"/><path d=\"M16 4 L16.5 7\"/>"
    "<path d=\"M7.5 7 Q5 10 5 14 Q5 21 12 21 Q19 21 19 14 Q19 10 16.5 7 Z\"/>"
    "<circle cx=\"9.5\" cy=\"12\" r=\"2.2\"/><circle cx=\"14.5\" cy=\"12\" r=\"2.2\"/>"
    "<circle cx=\"9.5\" cy=\"12\" r=\".75\" fill=\"currentColor\" stroke=\"none\"/>"
    "<circle cx=\"14.5\" cy=\"12\" r=\".75\" fill=\"currentColor\" stroke=\"none\"/>"
    "<path d=\"M11 14.5 L12 16 L13 14.5\"/></svg>\n"
    "          </div>\n"
    "          <div>\n"
    "            <p class=\"text-[10px] font-black text-violet-400 tracking-[.15em]\">AI AGENT</p>\n"
    "            <p class=\"text-[9px] text-ark-muted\">昨日の未達 → 今日の作戦</p>\n"
    "          </div>\n"
    "        </div>\n"
    "        <div class=\"flex flex-col gap-2\">\n"
    + ai_section_inner
    + strategy_html
    + system_trigger_html
    + priority_candidates_html +
    "\n        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </div>\n"
    + '</div>'

    + '<div id="weekly-view" style="display:none" class="flex flex-col gap-5">'
    + f'<section><div class="flex items-baseline gap-3 mb-2"><span class="text-[10px] font-bold text-ark-muted tracking-[.2em] uppercase">Weekly Condition</span><span class="text-[10px] text-ark-muted">{w_period}</span></div>'
    + f'<div class="bg-ark-card border ' + w_judge_border + ' rounded-2xl p-5 glow-amber"><div class="flex flex-col sm:flex-row sm:items-center gap-5">'
    + '<div class="flex items-center gap-4"><div class="flex items-end gap-2.5">'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if w_judge_label == "🏻絶好調" else "w-5 h-5"} rounded-full {"bg-green-400 shadow-[0_0_14px_rgba(34,197,94,.75)]" if w_judge_label == "🏻絶好調" else "bg-green-500/15 border border-green-500/20"}"></div><span class="text-[8px] {"text-green-400 font-black" if w_judge_label == "🏻絶好調" else "text-green-500/40 font-bold"}">絶好調</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if w_judge_label == "📈成長中" else "w-5 h-5"} rounded-full {"bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,.75)]" if w_judge_label == "📈成長中" else "bg-amber-500/15 border border-amber-500/20"}"></div><span class="text-[8px] {"text-amber-400 font-black" if w_judge_label == "📈成長中" else "text-amber-500/40 font-bold"}">成長中</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if w_judge_label == "🔧要改善" else "w-5 h-5"} rounded-full {"bg-red-400 shadow-[0_0_14px_rgba(239,68,68,.75)]" if w_judge_label == "🔧要改善" else "bg-red-500/15 border border-red-500/20"}"></div><span class="text-[8px] {"text-red-400 font-black" if w_judge_label == "🔧要改善" else "text-red-500/40 font-bold"}">要改善</span></div>'
    + '</div><div class="w-px h-12 bg-ark-border"></div>'
    + f'<div><p class="text-2xl font-black {w_judge_text_c} leading-none">{w_judge_label}</p></div></div>'
    + f'<div class="flex gap-3 sm:ml-auto"><div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">体重平均</p><p class="text-base font-black text-white">' + str(w_weight_avg) + '<span class="text-xs font-normal text-ark-muted">kg</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">睡眠平均</p><p class="text-base font-black text-amber-300">' + str(w_sleep_avg) + '<span class="text-xs font-normal">h</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[70px]"><p class="text-[9px] text-ark-muted mb-1">体調</p><p class="text-base font-black text-white">' + w_cond_summary + '</p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">総合</p><p class="text-base font-black ' + w_judge_text_c + '">' + str(w_score_total) + '<span class="text-xs font-normal text-ark-muted">点</span></p></div>'
    + '</div></div></div></section>'
    + '<div class="grid grid-cols-1 md:grid-cols-2 gap-5"><div class="flex flex-col gap-3">'
    + weekly_cards_html
    + '</div><div class="flex flex-col gap-4">'
    + weekly_comment_html
    + '</div></div></div>'

    + '<div id="monthly-view" style="display:none" class="flex flex-col gap-5">'
    + f'<section><div class="flex items-baseline gap-3 mb-2"><span class="text-[10px] font-bold text-ark-muted tracking-[.2em] uppercase">Monthly Condition</span><span class="text-[10px] text-ark-muted">{m_period}</span></div>'
    + f'<div class="bg-ark-card border ' + m_judge_border + ' rounded-2xl p-5 glow-amber"><div class="flex flex-col sm:flex-row sm:items-center gap-5">'
    + '<div class="flex items-center gap-4"><div class="flex items-end gap-2.5">'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if m_judge_label == "🏅絶好調" else "w-5 h-5"} rounded-full {"bg-green-400 shadow-[0_0_14px_rgba(34,197,94,.75)]" if m_judge_label == "🏅絶好調" else "bg-green-500/15 border border-green-500/20"}"></div><span class="text-[8px] {"text-green-400 font-black" if m_judge_label == "🏅絶好調" else "text-green-500/40 font-bold"}">絶好調</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if m_judge_label == "📊成長中" else "w-5 h-5"} rounded-full {"bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,.75)]" if m_judge_label == "📊成長中" else "bg-amber-500/15 border border-amber-500/20"}"></div><span class="text-[8px] {"text-amber-400 font-black" if m_judge_label == "📊成長中" else "text-amber-500/40 font-bold"}">成長中</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-8 h-8" if m_judge_label == "🔄要改善" else "w-5 h-5"} rounded-full {"bg-red-400 shadow-[0_0_14px_rgba(239,68,68,.75)]" if m_judge_label == "🔄要改善" else "bg-red-500/15 border border-red-500/20"}"></div><span class="text-[8px] {"text-red-400 font-black" if m_judge_label == "🔄要改善" else "text-red-500/40 font-bold"}">要改善</span></div>'
    + '</div><div class="w-px h-12 bg-ark-border"></div>'
    + f'<div><p class="text-2xl font-black {m_judge_text_c} leading-none">{m_judge_label}</p></div></div>'
    + f'<div class="flex gap-3 sm:ml-auto"><div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">体重平均</p><p class="text-base font-black text-white">' + str(m_weight_avg) + '<span class="text-xs font-normal text-ark-muted">kg</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">睡眠平均</p><p class="text-base font-black text-amber-300">' + str(m_sleep_avg) + '<span class="text-xs font-normal">h</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[70px]"><p class="text-[9px] text-ark-muted mb-1">体調</p><p class="text-base font-black text-white">' + m_cond_summary + '</p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">総合</p><p class="text-base font-black ' + m_judge_text_c + '">' + str(m_score_total) + '<span class="text-xs font-normal text-ark-muted">点</span></p></div>'
    + '</div></div></div></section>'
    + '<div class="grid grid-cols-1 md:grid-cols-2 gap-5"><div class="flex flex-col gap-3">'
    + monthly_cards_html
    + '</div><div class="flex flex-col gap-4">'
    + monthly_comment_html
    + '</div></div></div>'

    + '<script>var ON="tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border";var OFF="tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted";function switchTab(t){document.getElementById("daily-view").style.display=t==="daily"?"":"none";document.getElementById("weekly-view").style.display=t==="weekly"?"":"none";document.getElementById("monthly-view").style.display=t==="monthly"?"":"none";document.getElementById("badge-daily").style.display=t==="daily"?"":"none";document.getElementById("badge-weekly").style.display=t==="weekly"?"":"none";document.getElementById("badge-monthly").style.display=t==="monthly"?"":"none";document.getElementById("tab-daily").className=t==="daily"?ON:OFF;document.getElementById("tab-weekly").className=t==="weekly"?ON:OFF;document.getElementById("tab-monthly").className=t==="monthly"?ON:OFF;}</script>'

    "\n  <footer class=\"flex items-center justify-between pt-1 pb-3\">\n"
    "    <p class=\"text-[9px] text-ark-muted\">SPRING ARK &copy; 2026</p>\n"
    f"    <p class=\"text-[9px] text-ark-muted\">Generated at {generated_at} SGT</p>\n"
    "  </footer>\n"

    "</div>\n"
    "</body>\n"
    "</html>\n"
)

# ── HTMLをファイルに保存 ──────────────────────────
output_path = "/tmp/dashboard/index.html"
os.makedirs("/tmp/dashboard", exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[OK] HTML generated: {output_path} ({len(html)} bytes)")

# ── Surgeにデプロイ ────────────────────────────────
result = subprocess.run(
    ["npx", "surge", "/tmp/dashboard", SURGE_DOMAIN, "--token", SURGE_TOKEN],
    capture_output=True,
    text=True,
)
if result.returncode == 0:
    print(f"[OK] Deployed to https://{SURGE_DOMAIN}")
else:
    print(f"[ERROR] Surge deploy failed:\n{result.stderr}")
    exit(1)
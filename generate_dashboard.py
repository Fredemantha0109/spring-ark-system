"""
generate_dashboard.py — Notionからデータを取得してHTMLダッシュボードを生成し、Surgeにデプロイする

実行タイミング:
    GitHub Actions内でcalc_score.pyの後に実行される
"""

import os
import json
import subprocess
import requests
from datetime import datetime, timezone, timedelta

# ── 環境変数 ──────────────────────────────────────
NOTION_TOKEN        = os.environ["NOTION_TOKEN"]
DATABASE_ID         = os.environ["DATABASE_ID"]
SURGE_TOKEN         = os.environ["SURGE_TOKEN"]
SURGE_DOMAIN        = os.environ["SURGE_DOMAIN"]
CALENDAR_DATABASE_ID = os.environ.get("CALENDAR_DATABASE_ID", "")

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

# ── 今日のページ（体重・睡眠・体調）+ 昨日のページ（スコア・タスク）──
today_page_id,     props_today     = fetch_page(today)
yesterday_page_id, props_yesterday = fetch_page(yesterday)

if not props_yesterday:
    print(f"[WARN] {yesterday} のページが見つかりません")
    exit(1)

# 今日のページが未作成の場合は昨日で代用
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

# 体重・睡眠・体調は今日のページから
weight    = props_today.get("体重", {}).get("number") or "-"
sleep     = props_today.get("睡眠時間", {}).get("number") or "-"
condition = (props_today.get("体調", {}).get("select") or {}).get("name", "-")
# ── Claude APIで推奨作戦を生成 ──────────────────────
import json as _json

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def generate_strategy(sleep_val, cond, judge, scores, missed_tasks, weight_val="-"):
    """Claude APIで今日の推奨作戦を3つ生成"""
    if not ANTHROPIC_API_KEY:
        return []
    missed_str = "\n".join([f"\u30fb{cat}: {task}" for task, cat in missed_tasks]) or "\u306a\u3057"
    score_str  = f"W:{scores[0]} / C:{scores[1]} / Ca:{scores[2]} / I:{scores[3]}"
    prompt = (
        "\u3042\u306a\u305f\u306fSpring Ark\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u306e\u30d1\u30fc\u30bd\u30ca\u30eb\u30b3\u30fc\u30c1\u3067\u3059\u3002\n"
        "\u4ee5\u4e0b\u306e\u30c7\u30fc\u30bf\u3092\u3082\u3068\u306b\u3001\u4eca\u65e5\u306e\u5177\u4f53\u7684\u306a\u63a8\u5968\u4f5c\u6226\u30923\u3064\u3001JSON\u5f62\u5f0f\u3067\u51fa\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\n\n"
        f"\u3010\u4eca\u65e5\u306e\u30b3\u30f3\u30c7\u30a3\u30b7\u30e7\u30f3\u3011\n"
        f"- \u7751\u7720: {sleep_val}h\n"
        f"- \u4f53\u8abf: {cond}\n"
        f"- \u4f53\u91cd: {weight_val}kg\n"
        f"- \u7dcf\u5408\u5224\u5b9a: {judge}\n"
        f"- \u30b9\u30b3\u30a2: {score_str}\n\n"
        f"\u3010\u6628\u65e5\u306e\u672a\u9054\u30bf\u30b9\u30af\u3011\n{missed_str}\n\n"
        "\u3010\u51fa\u529b\u5f62\u5f0f\u3011\u5fc5\u305aJSON\u914d\u5217\u306e\u307f\u51fa\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u4ed6\u306e\u30c6\u30ad\u30b9\u30c8\u306f\u4e00\u5207\u4e0d\u8981\u3002\n"
        '[\n'
        '  {"title": "\u4f5c\u6226\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u306a\u884c\u52d5\uff0830\u6587\u5b57\u4ee5\u5185\uff09"},\n'
        '  {"title": "\u4f5c\u6226\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u306a\u884c\u52d5\uff0830\u6587\u5b57\u4ee5\u5185\uff09"},\n'
        '  {"title": "\u4f5c\u6226\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u306a\u884c\u52d5\uff0830\u6587\u5b57\u4ee5\u5185\uff09"}\n'
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
            return _j.loads(text[start:end])
    except Exception as e:
        print(f"[WARN] Claude API error: {e}")
    return []

plan_w  = get_tasks("【W】予定タスク")
plan_c  = get_tasks("【C】予定タスク")
plan_ca = get_tasks("【Ca】予定タスク")
plan_i  = get_tasks("【I】予定タスク")
done_w  = get_tasks("【W】実績")
done_c  = get_tasks("【C】実績")
done_ca = get_tasks("【Ca】実績")
done_i  = get_tasks("【I】実績")

# 未達タスクを収集（昨日）
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
    # 🟢 良好
    if (s >= 7 and cond in ("好調", "普通")) or (5.5 <= s < 7 and cond == "好調"):
        return "良好", "green"
    # 🔴 危険
    if (5.5 <= s < 7 and cond == "不調") or (s < 5.5 and cond in ("普通", "不調")):
        return "危険", "red"
    # 🟡 要注意（残り全パターン）
    return "要注意", "amber"

judge_label, judge_color = calc_judge(sleep, condition)

ai_note = ""  # 後方互換のため残す
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
    """過去n日分のページを取得（今日を除く）"""
    pages_data = []
    for i in range(1, n + 1):
        d = (datetime.now(sgt) - timedelta(days=i)).strftime("%Y-%m-%d")
        _, p = fetch_page(d)
        if p:
            pages_data.append((d, p))
    return pages_data

past_pages = fetch_past_pages(5)

# ① 過去5日で未達回数が最多のタスク
miss_count = {}   # {(task_name, category): 未達回数}
for date_str, p in past_pages:
    for cat, (plan_key, done_key) in CATEGORIES.items():
        plan = [t["name"] for t in p.get(plan_key, {}).get("multi_select", [])]
        done = [t["name"] for t in p.get(done_key, {}).get("multi_select", [])]
        # 🔥を除いた名前で比較
        plan_clean = [t.lstrip("🔥") for t in plan]
        done_clean = [t.lstrip("🔥") for t in done]
        for task in plan_clean:
            if task not in done_clean:
                key = (task, cat)
                miss_count[key] = miss_count.get(key, 0) + 1

candidate_1 = None  # (task_name, category, miss_count)
if miss_count:
    top = sorted(miss_count.items(), key=lambda x: -x[1])[0]
    candidate_1 = (top[0][0], top[0][1], top[1])

# ② 最後に完了した日が最も遠いタスク（過去5日に予定があったもの）
last_done = {}  # {(task_name, category): 最後に完了した日付文字列}
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

candidate_2 = None  # (task_name, category, last_done_date)
if last_done:
    # "never" > 日付文字列 なので最も遠い = 最も小さい日付 or never
    def sort_key(x):
        return x[1] if x[1] != "never" else "0000-00-00"
    oldest = sorted(last_done.items(), key=lambda x: sort_key(x))[0]
    # candidate_1と同じタスクの場合は次点を取得
    for item in sorted(last_done.items(), key=lambda x: sort_key(x)):
        if candidate_1 is None or item[0][0] != candidate_1[0]:
            candidate_2 = (item[0][0], item[0][1], item[1])
            break
    if candidate_2 is None and last_done:
        candidate_2 = (oldest[0][0], oldest[0][1], oldest[1])


# ── タスク行HTML生成 ──────────────────────────────
def task_rows_html(plan_tasks, done_tasks):
    rows = []
    for task in plan_tasks:
        done = task in done_tasks
        if done:
            icon = (
                '<div class="w-4 h-4 rounded-full flex-shrink-0 bg-green-500/20 border border-green-500/50'
                ' flex items-center justify-center">'
                '<svg class="w-2.5 h-2.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                '<polyline stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="20 6 9 17 4 12"/>'
                '</svg></div>'
            )
        else:
            icon = '<div class="w-4 h-4 rounded-full flex-shrink-0 border border-ark-border bg-ark-dim"></div>'
        name_class = "text-white/55 line-through" if done else "text-white/80"
        row_class  = "priority-row" if "🔥" in task else ""
        rows.append(
            '<div class="flex items-center gap-2 py-0.5 ' + row_class + '">'
            + icon
            + '<span class="text-xs flex-1 ' + name_class + '">' + task + '</span>'
            + '</div>'
        )
    return "\n".join(rows)

# ── カテゴリカードHTML ────────────────────────────
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
        '<div class="ark-card bg-ark-card border ' + card_border + ' rounded-2xl p-4">'
        '<div class="flex items-start justify-between mb-3">'
        '<div class="flex items-center gap-2.5">'
        '<div class="w-8 h-8 rounded-xl ' + icon_wrap + ' border flex items-center justify-center flex-shrink-0">'
        '<span class="' + text_c + '">' + icon_svg + '</span>'
        '</div>'
        '<div>'
        '<p class="text-[10px] font-black ' + text_c + ' tracking-[.15em]">' + name + '</p>'
        '<p class="text-[9px] text-ark-muted">' + subtitle + '</p>'
        '</div></div>'
        '<p class="text-xl font-black ' + text_c + '">' + str(score)
        + '<span class="text-sm text-ark-muted font-normal">/100点</span></p>'
        '</div>'
        '<div class="mb-3">'
        '<div class="h-1.5 bg-ark-dim rounded-full overflow-hidden">'
        '<div class="h-full rounded-full bg-gradient-to-r ' + bar_grad + ' bar" style="width:' + str(score) + '%"></div>'
        '</div></div>'
        '<div class="space-y-1.5">' + rows + '</div>'
        '</div>'
    )

# アイコンSVG
ICON_W  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/></svg>'
ICON_C  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
ICON_CA = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>'
ICON_I  = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'

# AI提案テキスト整形
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

# ── 推奨作戦パネルHTML ────────────────────────────
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

# ── SYSTEM TRIGGER（危険時のみ表示）────────────────
# ── カレンダーDB取得 ──────────────────────────────
calendar_events = []
if CALENDAR_DATABASE_ID:
    try:
        cal_res = requests.post(
            f"https://api.notion.com/v1/databases/{CALENDAR_DATABASE_ID}/query",
            headers=HEADERS,
            json={
                "filter": {
                    "property": "\u65e5\u4ed8",
                    "date": {"on_or_after": today, "on_or_before": today}
                },
                "sorts": [{"property": "\u65e5\u4ed8", "direction": "ascending"}]
            }
        )
        for page in cal_res.json().get("results", []):
            props = page["properties"]
            name = ""
            name_prop = props.get("\u540d\u524d", {})
            if name_prop.get("title"):
                name = name_prop["title"][0].get("plain_text", "")
            date_prop = props.get("\u65e5\u4ed8", {}).get("date", {}) or {}
            start = date_prop.get("start", "")
            end   = date_prop.get("end", "")
            # 時刻部分だけ抽出（日付のみの場合はスキップ）
            if "T" in start:
                start_time = start[11:16]  # HH:MM
                end_time   = end[11:16] if end and "T" in end else ""
                if name:
                    calendar_events.append({"name": name, "start": start_time, "end": end_time})
    except Exception as e:
        print(f"[WARN] Calendar fetch error: {e}")

# カレンダーHTML
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
                duration = f"{mins}\u5206" if mins > 0 else ""
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

# ── 優先タスク候補パネルHTML ──────────────────────────
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
        f'<button onclick="{fn}()" class="flex-shrink-0 bg-amber-500/15 hover:bg-amber-500/30 border border-amber-500/30 text-amber-300 text-[10px] font-black rounded-lg px-3 py-1.5 transition-all cursor-pointer">'
        f'\U0001f525 \u512a\u5148\u8a2d\u5b9a</button>'
        f'</div></div>'
        f'<script>'
        f'async function {fn}(){{'
        f'  const btn=event.target;btn.textContent="\u9001\u4fe1\u4e2d...";btn.disabled=true;'
        f'  try{{'
        f'    const r=await fetch("https://api.github.com/repos/{gh_repo}/dispatches",{{'
        f'      method:"POST",'
        f'      headers:{{"Authorization":"Bearer {gh_pat}","Accept":"application/vnd.github+json","Content-Type":"application/json"}},'
        f'      body:JSON.stringify({{"event_type":"force_priority","client_payload":{{"task_name":"{task_name}","category":"{category}"}}}}),'
        f'    }});'
        f'    if(r.status===204){{btn.textContent="\u2705 \u8ffd\u52a0\u5b8c\u4e86";btn.style.borderColor="#22c55e";btn.style.color="#4ade80";}}'
        f'    else{{btn.textContent="\u274c \u30a8\u30e9\u30fc";btn.disabled=false;}}'
        f'  }}catch(e){{btn.textContent="\u274c \u30a8\u30e9\u30fc";btn.disabled=false;}}'
        f'}}</script>'
    )

priority_candidates_html = ""
cards = []
if candidate_1:
    reason1 = f"\u904e\u53bb5\u65e5\u9593\u3067{candidate_1[2]}\u56de\u672a\u9054"
    cards.append(make_candidate_card(1, candidate_1[0], candidate_1[1], reason1, GH_PAT, GH_REPO))
if candidate_2:
    last = candidate_2[2] if candidate_2[2] != "never" else "\u671f\u9593\u5185\u672a\u5b8c\u4e86"
    reason2 = f"\u6700\u7d42\u5b8c\u4e86\u65e5: {last}"
    cards.append(make_candidate_card(2, candidate_2[0], candidate_2[1], reason2, GH_PAT, GH_REPO))

if cards:
    priority_candidates_html = (
        '<div class="bg-ark-card border border-amber-500/20 rounded-2xl p-4 mt-4">'
        '<div class="flex items-center gap-2 mb-3">'
        '<svg class="w-4 h-4 text-amber-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>'
        '<p class="text-[10px] font-black text-amber-400 tracking-[.15em]">PRIORITY CANDIDATES</p>'
        '</div>'
        '<div class="flex flex-col gap-2">'
        + "\n".join(cards) +
        '</div></div>'
    )

# 判定カラー設定
judge_colors = {
    "green": ("text-green-400", "border-green-500/25"),
    "amber": ("text-amber-300", "border-amber-500/25"),
    "red":   ("text-red-400",   "border-red-500/25"),
}
judge_text_c, judge_border = judge_colors[judge_color]
cond_text_c = {"好調": "text-green-400", "普通": "text-amber-400", "不調": "text-red-400"}.get(condition, "text-amber-400")
sleep_c = "text-amber-300" if isinstance(sleep, float) and sleep < 7 else "text-white"

# インジケータードット設定
good_dot_size     = "w-6 h-6" if judge_label == "\u826f\u597d"   else "w-4 h-4"
caution_dot_size  = "w-6 h-6" if judge_label == "\u8981\u6ce8\u610f" else "w-4 h-4"
alert_dot_size    = "w-6 h-6" if judge_label == "\u5371\u967a"   else "w-4 h-4"
good_dot_style    = "bg-green-400 shadow-[0_0_14px_rgba(34,197,94,.75)]"    if judge_label == "\u826f\u597d"   else "bg-green-500/15 border border-green-500/20"
caution_dot_style = "bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,.75)]"   if judge_label == "\u8981\u6ce8\u610f" else "bg-amber-500/15 border border-amber-500/20"
alert_dot_style   = "bg-red-400 shadow-[0_0_14px_rgba(239,68,68,.75)]"      if judge_label == "\u5371\u967a"   else "bg-red-500/15 border border-red-500/20"
good_text_style    = "text-green-400 font-black"  if judge_label == "\u826f\u597d"   else "text-green-500/40 font-bold"
caution_text_style = "text-amber-400 font-black"  if judge_label == "\u8981\u6ce8\u610f" else "text-amber-500/40 font-bold"
alert_text_style   = "text-red-400 font-black"    if judge_label == "\u5371\u967a"   else "text-red-500/40 font-bold"

generated_at = datetime.now(sgt).strftime("%H:%M")

# ── Week番号・Q表示 ───────────────────────────────
# Spring Ark Week1開始日: 2026-04-06（月）
PROJECT_START = datetime(2026, 4, 6, tzinfo=sgt)
target_date   = datetime.strptime(yesterday, "%Y-%m-%d").replace(tzinfo=sgt)
delta_days    = (target_date - PROJECT_START).days
week_num      = max(1, delta_days // 7 + 1)

# 四半期
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

# 日付表示フォーマット（例: 2026-04-21 · Week 3 · Q2-Day 16）
header_date = f"{yesterday}\u00a0\u00b7\u00a0Week\u00a0{week_num}\u00a0\u00b7\u00a0Q{quarter}-Day\u00a0{q_day}"


# ── Weekly集計（過去7日）────────────────────────
weekly_pages = []
for i in range(1, 8):
    d = (datetime.now(sgt) - timedelta(days=i)).strftime("%Y-%m-%d")
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

# 体重・睡眠・体調の週平均
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

# タスク実施回数集計
task_done_count = {}  # {(task_name, category): count}
cat_map = {
    "W":  ("【W】実績",  "Wellness"),
    "C":  ("【C】実績",  "Communication"),
    "Ca": ("【Ca】実績", "Career"),
    "I":  ("【I】実績",  "Input"),
}
import re as _re
TASK_ALIASES = {
    "\u30e9\u30a4\u30a2\u30f3": "\u52d5\u753b\u8996\u8074",
    "Soccer":    "\u52d5\u753b\u8996\u8074",
    "Scrambled": "\u52d5\u753b\u8996\u8074",
    "Youtube":   "\u52d5\u753b\u8996\u8074",
}
def normalize_task(name):
    """括弧内（曜日・定着など）を除いてタスク名を正規化、エイリアスを統合"""
    base = _re.sub(r"\uff08[^\uff09]*\uff09", "", name).strip()
    return TASK_ALIASES.get(base, base)

for _, p in weekly_pages:
    for cat_key, (done_key, cat_name) in cat_map.items():
        tasks = [t["name"].lstrip("🔥") for t in p.get(done_key, {}).get("multi_select", [])]
        for task in tasks:
            normalized = normalize_task(task)
            k = (normalized, cat_key)
            task_done_count[k] = task_done_count.get(k, 0) + 1

# カテゴリ別にソート（回数多い順）
weekly_task_rows = {}
for cat_key in ["W", "C", "Ca", "I"]:
    rows = [(t, c) for (t, c), cnt in sorted(task_done_count.items(), key=lambda x: -x[1]) if c == cat_key]
    weekly_task_rows[cat_key] = rows

# Weekly判定
if w_score_total >= 80:
    w_judge_label, w_judge_color = "\U0001f3fb\u7d76\u597d\u8abf", "green"
elif w_score_total >= 50:
    w_judge_label, w_judge_color = "\U0001f4c8\u6210\u9577\u4e2d", "amber"
else:
    w_judge_label, w_judge_color = "\U0001f527\u8981\u6539\u5584", "red"

w_judge_colors = {
    "green": ("text-green-400", "border-green-500/25"),
    "amber": ("text-amber-300", "border-amber-500/25"),
    "red":   ("text-red-400",   "border-red-500/25"),
}
w_judge_text_c, w_judge_border = w_judge_colors[w_judge_color]

# Weekly AIコメント生成
def generate_weekly_comment(w_score_w, w_score_c, w_score_ca, w_score_i, w_score_total,
                              w_weight_avg, w_sleep_avg, w_cond_summary, task_done_count):
    if not ANTHROPIC_API_KEY:
        return [], ""
    top_tasks = sorted(task_done_count.items(), key=lambda x: -x[1])[:10]
    done_str = "\n".join([f"\u30fb{t}({c}): {cnt}\u56de" for (t, c), cnt in top_tasks]) or "\u306a\u3057"
    missed_tasks_w = []
    for _, p in weekly_pages:
        for cat_key, (done_key, cat_name) in cat_map.items():
            plan_key = f"\u3010{cat_key}\u3011\u4e88\u5b9a\u30bf\u30b9\u30af"
            plan = [t["name"].lstrip("\U0001f525") for t in p.get(plan_key, {}).get("multi_select", [])]
            done = [t["name"].lstrip("\U0001f525") for t in p.get(done_key, {}).get("multi_select", [])]
            for task in plan:
                if task not in done:
                    missed_tasks_w.append(f"{cat_name}: {task}")
    missed_str = "\n".join(list(dict.fromkeys(missed_tasks_w))[:8]) or "\u306a\u3057"
    prompt = (
        "\u3042\u306a\u305f\u306fSpring Ark\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u306e\u30d1\u30fc\u30bd\u30ca\u30eb\u30b3\u30fc\u30c1\u3067\u3059\u3002\n"
        "\u4ee5\u4e0b\u306e\u9031\u6b21\u30c7\u30fc\u30bf\u3092\u3082\u3068\u306b\u3001\u5206\u6790\u30ec\u30dd\u30fc\u30c8\u3092JSON\u5f62\u5f0f\u3067\u51fa\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\n\n"
        f"\u3010\u4eca\u9031\u306e\u30b3\u30f3\u30c7\u30a3\u30b7\u30e7\u30f3\u3011\n"
        f"- \u4f53\u91cd\u5e73\u5747: {w_weight_avg}kg\n"
        f"- \u7751\u7720\u5e73\u5747: {w_sleep_avg}h\n"
        f"- \u4f53\u8abf: {w_cond_summary}\n"
        f"- \u9031\u5e73\u5747\u30b9\u30b3\u30a2: W:{w_score_w} / C:{w_score_c} / Ca:{w_score_ca} / I:{w_score_i} / \u7dcf\u5408:{w_score_total}\n\n"
        f"\u3010\u5b9f\u65bd\u3067\u304d\u305f\u4e3b\u306a\u30bf\u30b9\u30af\u3011\n{done_str}\n\n"
        f"\u3010\u672a\u9054\u304c\u591a\u304b\u3063\u305f\u30bf\u30b9\u30af\u3011\n{missed_str}\n\n"
        "\u3010\u51fa\u529b\u5f62\u5f0f\u3011\u5fc5\u305aJSON\u30aa\u30d6\u30b8\u30a7\u30af\u30c8\u306e\u307f\u51fa\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u4ed6\u306e\u30c6\u30ad\u30b9\u30c8\u306f\u4e00\u5207\u4e0d\u8981\u3002\n"
        "{\n"
        '  "summaries": [\n'
        '    {"title": "\u8981\u70b9\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u5206\u6790\uff0840\u6587\u5b57\u4ee5\u5185\uff09"},\n'
        '    {"title": "\u8981\u70b9\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u5206\u6790\uff0840\u6587\u5b57\u4ee5\u5185\uff09"},\n'
        '    {"title": "\u8981\u70b9\u30bf\u30a4\u30c8\u30eb\uff0815\u6587\u5b57\u4ee5\u5185\uff09", "detail": "\u5177\u4f53\u7684\u5206\u6790\uff0840\u6587\u5b57\u4ee5\u5185\uff09"}\n'
        "  ],\n"
        '  "analysis": "\u4f53\u91cd\u30fb\u7751\u7720\u30fb\u4f53\u8abf\u30fb\u5b8c\u4e86\u30bf\u30b9\u30af\u30fb\u672a\u9054\u30bf\u30b9\u30af\u3092\u7d5c\u5408\u7684\u306b\u8e0f\u307e\u3048\u305f\u4eca\u9031\u306e\u7dcf\u5408\u8a55\u4fa1\u30fb\u8003\u5bdf\u30fb\u6539\u5584\u63d0\u6848\u3092200\u5b57\u7a0b\u5ea6\u3067\u8a18\u8f09\u3002\u6b21\u9031\u3078\u306e\u5177\u4f53\u7684\u30a2\u30af\u30b7\u30e7\u30f3\u3082\u542b\u3081\u308b\u3053\u3068\u3002"\n'
        "}"
    )
    import json as _j
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        text = res.json()["content"][0]["text"].strip()
        start_j, end_j = text.find("{"), text.rfind("}") + 1
        if start_j >= 0 and end_j > start_j:
            parsed = _j.loads(text[start_j:end_j])
            return parsed.get("summaries", []), parsed.get("analysis", "")
    except Exception as e:
        print(f"[WARN] Weekly Claude API error: {e}")
    return [], ""

weekly_summaries, weekly_analysis = generate_weekly_comment(
    w_score_w, w_score_c, w_score_ca, w_score_i, w_score_total,
    w_weight_avg, w_sleep_avg, w_cond_summary, task_done_count
)

# Weekly右側コメントHTML
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
    weekly_comment_html = (
        '<div class="stripe bg-ark-card border border-violet-500/20 rounded-2xl p-4 glow-violet">'
        '<div class="flex items-center gap-2 mb-4">'
        '<svg class="w-4 h-4 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>'
        '<p class="text-[10px] font-black text-violet-400 tracking-[.15em]">AI 週次分析</p>'
        '</div>'
        '<div class="flex flex-col gap-2">' + "\n".join(items) + analysis_html + '</div>'
        '</div>'
    )
else:
    weekly_comment_html = '<p class="text-xs text-ark-muted text-center py-4">週次分析データがありません</p>'

# Weeklyカテゴリカード
def weekly_task_card(name, subtitle, icon_svg, color, score, task_rows_list):
    color_map = {
        "green": ("text-green-400", "bg-green-500/10 border-green-500/20", "border-ark-border",   "from-green-600 to-emerald-400"),
        "amber": ("text-amber-400", "bg-amber-500/10 border-amber-500/20", "border-amber-500/20", "from-amber-500 to-yellow-400"),
        "rose":  ("text-rose-400",  "bg-rose-500/10 border-rose-500/20",   "border-rose-500/25",  "from-rose-600 to-red-400"),
        "sky":   ("text-sky-400",   "bg-sky-500/10 border-sky-500/20",     "border-sky-500/20",   "from-sky-500 to-cyan-400"),
    }
    text_c, icon_wrap, card_border, bar_grad = color_map[color]
    rows_html = ""
    for task_name, cat_key in task_rows_list:
        cnt = task_done_count.get((task_name, cat_key), 0)
        if cnt == 0:
            continue
        rows_html += (
            f'<div class="flex items-center gap-2 py-0.5">'
            f'<div class="w-4 h-4 rounded-full flex-shrink-0 bg-green-500/20 border border-green-500/50 flex items-center justify-center">'
            f'<span class="text-[8px] font-black text-green-400">{cnt}</span></div>'
            f'<span class="text-xs flex-1 text-white/80">{task_name}</span>'
            f'</div>'
        )
    return (
        '<div class="ark-card bg-ark-card border ' + card_border + ' rounded-2xl p-4">'
        '<div class="flex items-start justify-between mb-3">'
        '<div class="flex items-center gap-2.5">'
        '<div class="w-8 h-8 rounded-xl ' + icon_wrap + ' border flex items-center justify-center flex-shrink-0">'
        '<span class="' + text_c + '">' + icon_svg + '</span>'
        '</div>'
        '<div>'
        '<p class="text-[10px] font-black ' + text_c + ' tracking-[.15em]">' + name + '</p>'
        '<p class="text-[9px] text-ark-muted">' + subtitle + '</p>'
        '</div></div>'
        '<p class="text-xl font-black ' + text_c + '">' + str(score) + '<span class="text-sm text-ark-muted font-normal">/100点</span></p>'
        '</div>'
        '<div class="mb-3"><div class="h-1.5 bg-ark-dim rounded-full overflow-hidden">'
        '<div class="h-full rounded-full bg-gradient-to-r ' + bar_grad + ' bar" style="width:' + str(score) + '%"></div>'
        '</div></div>'
        '<div class="space-y-1.5">' + rows_html + '</div>'
        '</div>'
    )

weekly_cards_html = (
    weekly_task_card("WELLNESS",      "運動・食事・精神",  ICON_W,  "green", w_score_w,  weekly_task_rows["W"],  ) +
    weekly_task_card("COMMUNICATION", "英語学習・実践",        ICON_C,  "amber", w_score_c,  weekly_task_rows["C"],  ) +
    weekly_task_card("CAREER",        "AI・ビジネス・CPA",         ICON_CA, "rose",  w_score_ca, weekly_task_rows["Ca"], ) +
    weekly_task_card("INPUT",         "読書・NewsPicks",                        ICON_I,  "sky",   w_score_i,  weekly_task_rows["I"],  )
)

cards_html = (
    category_card("WELLNESS",      "運動・食事・精神",  ICON_W,  "green", score_w,  plan_w,  done_w)  +
    category_card("COMMUNICATION", "英語学習・実践",    ICON_C,  "amber", score_c,  plan_c,  done_c)  +
    category_card("CAREER",        "AI・ビジネス・CPA", ICON_CA, "rose",  score_ca, plan_ca, done_ca) +
    category_card("INPUT",         "読書・NewsPicks",   ICON_I,  "sky",   score_i,  plan_i,  done_i)
)

# ── HTML組み立て（文字列結合、三重クォートf-string不使用）──
html = (
    "<!DOCTYPE html>\n"
    '<html lang="ja">\n'
    "<head>\n"
    '  <meta charset="UTF-8">\n'
    '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    "  <title>SPRING ARK \u2014 Daily Dashboard</title>\n"
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

    # ヘッダー
    "\n  <header class=\"flex items-start justify-between\">\n"
    "    <div>\n"
    "      <div class=\"flex items-baseline gap-2.5 mb-1\">\n"
    "        <h1 class=\"text-2xl font-black tracking-tight\">SPRING ARK</h1>\n"
    "<div class=\"inline-flex bg-ark-dim rounded-full p-0.5 gap-0.5\"><button id=\"tab-daily\" onclick=\"switchTab(\'daily\')\" class=\"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border\">Daily</button><button id=\"tab-weekly\" onclick=\"switchTab(\'weekly\')\" class=\"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted\">Weekly</button></div>\n"
    "      </div>\n"
    f"      <p class=\"text-xs text-ark-muted\">{header_date}</p>\n"
    "    </div>\n"
    f"    <div class=\"inline-flex items-center gap-1.5 bg-{judge_color}-500/10 border border-{judge_color}-500/30 rounded-full px-3 py-1.5\">\n"
    f"      <div class=\"w-1.5 h-1.5 rounded-full bg-{judge_color}-400 animate-pulse-slow\"></div>\n"
    f"      <span class=\"text-[11px] font-bold text-{judge_color}-400 tracking-wider uppercase\">{judge_label}</span>\n"
    "    </div>\n"
    "  </header>\n"

    # Daily view wrapper
    '<div id="daily-view">'

    # コンディションセクション
    "\n  <section>\n"
    "    <span class=\"text-[10px] font-bold text-ark-muted tracking-[.2em] uppercase block mb-2\">Today's Condition</span>\n"
    f"    <div class=\"bg-ark-card border {judge_border} rounded-2xl p-5 glow-amber\">\n"
    "      <div class=\"flex flex-col sm:flex-row sm:items-center gap-5\">\n"
    "        <div class=\"flex items-center gap-4\">\n"
    "          <div class=\"flex items-end gap-2.5\">\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{good_dot_size} rounded-full {good_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {good_text_style}\">\u826f\u597d</span>\n"
    "            </div>\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{caution_dot_size} rounded-full {caution_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {caution_text_style}\">\u8981\u6ce8\u610f</span>\n"
    "            </div>\n"
    "            <div class=\"flex flex-col items-center gap-1.5\">\n"
    f"              <div class=\"{alert_dot_size} rounded-full {alert_dot_style}\"></div>\n"
    f"              <span class=\"text-[8px] {alert_text_style}\">\u5371\u967a</span>\n"
    "            </div>\n"
    "          </div>\n"
    "          <div class=\"w-px h-12 bg-ark-border\"></div>\n"
    "          <div>\n"
    f"            <p class=\"text-2xl font-black {judge_text_c} leading-none mb-1\">{judge_label}</p>\n"

    "          </div>\n"
    "        </div>\n"
    "        <div class=\"flex gap-3 sm:ml-auto\">\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-[9px] text-ark-muted mb-1\">体重</p>\n"
    f"            <p class=\"text-base font-black text-white\">{weight}<span class=\"text-[9px] font-normal text-ark-muted\">kg</span></p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-[9px] text-ark-muted mb-1\">睡眠</p>\n"
    f"            <p class=\"text-base font-black {sleep_c}\">{sleep}<span class=\"text-[9px] font-normal\">h</span></p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-[9px] text-ark-muted mb-1\">体調</p>\n"
    f"            <p class=\"text-base font-black {cond_text_c}\">{condition}</p>\n"
    "          </div>\n"
    "          <div class=\"bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]\">\n"
    "            <p class=\"text-[9px] text-ark-muted mb-1\">総合</p>\n"
    f"            <p class=\"text-base font-black {judge_text_c}\">{score_total}<span class=\"text-[9px] font-normal text-ark-muted\">点</span></p>\n"
    "          </div>\n"
    "        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n"

    # カテゴリ + AIエージェント + スコアバー
    "\n  <div class=\"grid grid-cols-1 md:grid-cols-2 gap-5\">\n"
    "    <div class=\"flex flex-col gap-3\">\n"
    + cards_html +
    "    </div>\n"

    "    <div class=\"flex flex-col gap-4\">\n"
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
    + calendar_html
    + system_trigger_html
    + priority_candidates_html +
    "\n        </div>\n"
    "      </div>\n"

    "    </div>\n"  
    "  </div>\n"

    # Daily view wrapper end
    + '</div>'

    # Weekly view
    + '<div id="weekly-view" style="display:none" class="flex flex-col gap-5">'
    + f'<section><span class="text-[10px] font-bold text-ark-muted tracking-[.2em] uppercase block mb-2">Weekly Condition</span>'
    + f'<div class="bg-ark-card border ' + w_judge_border + ' rounded-2xl p-5 glow-amber"><div class="flex flex-col sm:flex-row sm:items-center gap-5">'
    + '<div class="flex items-center gap-4">'
    + '<div class="flex items-end gap-2.5">'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-6 h-6" if w_judge_label == "🏻絶好調" else "w-4 h-4"} rounded-full {"bg-green-400 shadow-[0_0_14px_rgba(34,197,94,.75)]" if w_judge_label == "🏻絶好調" else "bg-green-500/15 border border-green-500/20"}"></div><span class="text-[8px] {"text-green-400 font-black" if w_judge_label == "🏻絶好調" else "text-green-500/40 font-bold"}">絶好調</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-6 h-6" if w_judge_label == "📈成長中" else "w-4 h-4"} rounded-full {"bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,.75)]" if w_judge_label == "📈成長中" else "bg-amber-500/15 border border-amber-500/20"}"></div><span class="text-[8px] {"text-amber-400 font-black" if w_judge_label == "📈成長中" else "text-amber-500/40 font-bold"}">成長中</span></div>'
    + f'<div class="flex flex-col items-center gap-1.5"><div class="{"w-6 h-6" if w_judge_label == "🔧要改善" else "w-4 h-4"} rounded-full {"bg-red-400 shadow-[0_0_14px_rgba(239,68,68,.75)]" if w_judge_label == "🔧要改善" else "bg-red-500/15 border border-red-500/20"}"></div><span class="text-[8px] {"text-red-400 font-black" if w_judge_label == "🔧要改善" else "text-red-500/40 font-bold"}">要改善</span></div>'
    + '</div>'
    + '<div class="w-px h-12 bg-ark-border"></div>'
    + f'<div><p class="text-2xl font-black {w_judge_text_c} leading-none">{w_judge_label}</p></div>'
    + '</div>'
    + f'<div class="flex gap-3 sm:ml-auto"><div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">体重平均</p><p class="text-base font-black text-white">' + str(w_weight_avg) + '<span class="text-[9px] font-normal text-ark-muted">kg</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">睡眠平均</p><p class="text-base font-black text-amber-300">' + str(w_sleep_avg) + '<span class="text-[9px] font-normal">h</span></p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[70px]"><p class="text-[9px] text-ark-muted mb-1">体調</p><p class="text-base font-black text-white">' + w_cond_summary + '</p></div>'
    + f'<div class="bg-ark-dim/60 rounded-xl px-4 py-2.5 text-center min-w-[60px]"><p class="text-[9px] text-ark-muted mb-1">総合</p><p class="text-base font-black ' + w_judge_text_c + '">' + str(w_score_total) + '<span class="text-[9px] font-normal text-ark-muted">点</span></p></div>'
    + '</div></div></div></section>'
    + '<div class="grid grid-cols-1 md:grid-cols-2 gap-5"><div class="flex flex-col gap-3">'
    + weekly_cards_html
    + '</div><div class="flex flex-col gap-4">'
    + weekly_comment_html
    + '</div></div></div>'

    # タブJS
    + '<script>function switchTab(t){document.getElementById("daily-view").style.display=t==="daily"?"":"none";document.getElementById("weekly-view").style.display=t==="weekly"?"":"none";var da=t==="daily";document.getElementById("tab-daily").className=da?"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border":"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted";document.getElementById("tab-weekly").className=!da?"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all bg-ark-card text-white border border-ark-border":"tab-btn text-[11px] font-bold rounded-full px-3 py-1 transition-all text-ark-muted";}</script>'

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
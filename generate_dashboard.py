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
NOTION_TOKEN  = os.environ["NOTION_TOKEN"]
DATABASE_ID   = os.environ["DATABASE_ID"]
SURGE_TOKEN   = os.environ["SURGE_TOKEN"]
SURGE_DOMAIN  = os.environ["SURGE_DOMAIN"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ── 日付(SGT = UTC+8)で昨日を取得 ──────────────────
sgt       = timezone(timedelta(hours=8))
yesterday = (datetime.now(sgt) - timedelta(days=1)).strftime("%Y-%m-%d")

# ── Notionからページ取得 ───────────────────────────
res = requests.post(
    f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
    headers=HEADERS,
    json={"filter": {"property": "Date", "title": {"equals": yesterday}}}
)
pages = res.json().get("results", [])
if not pages:
    print(f"[WARN] {yesterday} のページが見つかりません")
    exit(1)

props = pages[0]["properties"]

# ── データ抽出 ────────────────────────────────────
def get_score(key):
    return props.get(key, {}).get("formula", {}).get("number", 0) or 0

def get_tasks(key):
    return [t["name"] for t in props.get(key, {}).get("multi_select", [])]

score_w  = get_score("【W】スコア")
score_c  = get_score("【C】スコア")
score_ca = get_score("【Ca】スコア")
score_i  = get_score("【I】スコア")
score_total = round((score_w + score_c + score_ca + score_i) / 4)

weight    = props.get("体重", {}).get("number") or "-"
sleep     = props.get("睡眠時間", {}).get("number") or "-"
condition = (props.get("体調", {}).get("select") or {}).get("name", "-")
ai_note   = ""
ai_blocks = props.get("AI提案・作戦", {}).get("rich_text", [])
if ai_blocks:
    ai_note = ai_blocks[0].get("plain_text", "")

plan_w  = get_tasks("【W】予定タスク")
plan_c  = get_tasks("【C】予定タスク")
plan_ca = get_tasks("【Ca】予定タスク")
plan_i  = get_tasks("【I】予定タスク")
done_w  = get_tasks("【W】実績")
done_c  = get_tasks("【C】実績")
done_ca = get_tasks("【Ca】実績")
done_i  = get_tasks("【I】実績")

# 判定
if score_total >= 80:
    judge_label = "良好"
    judge_color = "green"
elif score_total >= 50:
    judge_label = "要注意"
    judge_color = "amber"
else:
    judge_label = "危険"
    judge_color = "red"

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
    "        <span class=\"text-xs font-bold text-ark-muted tracking-[.2em] border border-ark-border rounded-full px-2.5 py-0.5\">Daily Dashboard</span>\n"
    "      </div>\n"
    f"      <p class=\"text-xs text-ark-muted\">{yesterday}</p>\n"
    "    </div>\n"
    f"    <div class=\"inline-flex items-center gap-1.5 bg-{judge_color}-500/10 border border-{judge_color}-500/30 rounded-full px-3 py-1.5\">\n"
    f"      <div class=\"w-1.5 h-1.5 rounded-full bg-{judge_color}-400 animate-pulse-slow\"></div>\n"
    f"      <span class=\"text-[11px] font-bold text-{judge_color}-400 tracking-wider uppercase\">{judge_label}</span>\n"
    "    </div>\n"
    "  </header>\n"

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
    "            <p class=\"text-xs text-ark-muted\">Spring Ark Daily Report</p>\n"
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
    "        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </section>\n"

    # カテゴリ + AIエージェント + スコアバー
    "\n  <div class=\"grid grid-cols-1 md:grid-cols-2 gap-5\">\n"
    "    <div class=\"flex flex-col gap-3\">\n"
    + cards_html +
    "\n      <div class=\"bg-ark-card border border-ark-border rounded-2xl px-4 py-3 flex items-center justify-between\">\n"
    "        <p class=\"text-[10px] text-ark-muted\">本日 総合スコア</p>\n"
    f"        <span class=\"text-2xl font-black\">{score_total}<span class=\"text-ark-muted text-base font-normal\">点</span></span>\n"
    "      </div>\n"
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
    + ai_section_inner +
    "\n        </div>\n"
    "      </div>\n"

    "      <div class=\"bg-ark-card border border-ark-border rounded-2xl p-4\">\n"
    "        <p class=\"text-[10px] font-black text-ark-muted tracking-[.15em] mb-3\">SCORE BREAKDOWN</p>\n"
    "        <div class=\"flex flex-col gap-2.5\">\n"
    "          <div class=\"flex items-center gap-3\">\n"
    "            <span class=\"text-[9px] text-green-400 w-24 flex-shrink-0\">WELLNESS</span>\n"
    "            <div class=\"flex-1 h-1.5 bg-ark-dim rounded-full overflow-hidden\">\n"
    f"              <div class=\"h-full rounded-full bg-gradient-to-r from-green-600 to-emerald-400 bar\" style=\"width:{score_w}%\"></div>\n"
    "            </div>\n"
    f"            <span class=\"text-xs font-black text-green-400 w-8 text-right\">{score_w}</span>\n"
    "          </div>\n"
    "          <div class=\"flex items-center gap-3\">\n"
    "            <span class=\"text-[9px] text-amber-400 w-24 flex-shrink-0\">COMMUNICATION</span>\n"
    "            <div class=\"flex-1 h-1.5 bg-ark-dim rounded-full overflow-hidden\">\n"
    f"              <div class=\"h-full rounded-full bg-gradient-to-r from-amber-500 to-yellow-400 bar\" style=\"width:{score_c}%\"></div>\n"
    "            </div>\n"
    f"            <span class=\"text-xs font-black text-amber-400 w-8 text-right\">{score_c}</span>\n"
    "          </div>\n"
    "          <div class=\"flex items-center gap-3\">\n"
    "            <span class=\"text-[9px] text-rose-400 w-24 flex-shrink-0\">CAREER</span>\n"
    "            <div class=\"flex-1 h-1.5 bg-ark-dim rounded-full overflow-hidden\">\n"
    f"              <div class=\"h-full rounded-full bg-gradient-to-r from-rose-600 to-red-400 bar\" style=\"width:{score_ca}%\"></div>\n"
    "            </div>\n"
    f"            <span class=\"text-xs font-black text-rose-400 w-8 text-right\">{score_ca}</span>\n"
    "          </div>\n"
    "          <div class=\"flex items-center gap-3\">\n"
    "            <span class=\"text-[9px] text-sky-400 w-24 flex-shrink-0\">INPUT</span>\n"
    "            <div class=\"flex-1 h-1.5 bg-ark-dim rounded-full overflow-hidden\">\n"
    f"              <div class=\"h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-400 bar\" style=\"width:{score_i}%\"></div>\n"
    "            </div>\n"
    f"            <span class=\"text-xs font-black text-sky-400 w-8 text-right\">{score_i}</span>\n"
    "          </div>\n"
    "        </div>\n"
    "      </div>\n"
    "    </div>\n"
    "  </div>\n"

    # フッター
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
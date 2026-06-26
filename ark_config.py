"""
ark_config.py — Summer Ark コンテンツ定数の一元管理

内部カテゴリキー (W / C / Ca / I) と Notion プロパティ名は変更しない。
表示名・絵文字・ミッション・プロジェクト起点など、コンテンツ面のみここで管理する。
"""

from datetime import datetime, timezone, timedelta

# ── タイムゾーン ─────────────────────────────────────────────────────────────
# Summer Ark は日本生活前提。日付境界・PROJECT_START はすべて JST で統一する。
JST = timezone(timedelta(hours=9))

# ── プロジェクト識別 ─────────────────────────────────────────────────────────
ARK_SEASON = "SUMMER"
ARK_NAME = "SUMMER ARK"

MISSION = (
    "シンガポール生活に区切りをつけ、独立とAIを軸にした新しいキャリアの土台を、"
    "新生活の中で着実に築く"
)

# Summer Ark 開始日（月曜）
PROJECT_START_DATE = "2026-07-13"
PROJECT_START = datetime(2026, 7, 13, tzinfo=JST)

# 完了定義（9月末時点）
COMPLETION_CRITERIA = [
    "新生活基盤完成",
    "収益基盤確保",
    "AI卒業制作完了＋frog定期活動確定",
    "トレーニング目標達成",
    "TOEIC日程確定・学習ルーティン定着",
    "振り返り＋Winter Ark準備完了",
]

# ── トレーニング目標（プレースホルダー）──────────────────────────────────────
# TODO: 別チャットで確定後に差し替え
TRAINING_TARGETS = {
    "bench_press_kg": None,
    "body_weight_kg": None,
}

# ── 4柱定義（キー・Notionプロパティ名は不変）────────────────────────────────
CATEGORIES = [
    {
        "key": "W",
        "label": "Routine",
        "emoji": "🔁",
        "subtitle": "トレーニング・TOEIC・振り返り",
        "badge": "ROUTINE",
        "color": "green",
        "plan_prop": "【W】予定タスク",
        "actual_prop": "【W】実績",
        "score_prop": "【W】スコア",
        "values": ["Forever Young", "English Hero", "Vision Builder"],
    },
    {
        "key": "C",
        "label": "Belonging",
        "emoji": "🏠",
        "subtitle": "新生活基盤・人間関係・家族",
        "badge": "BELONGING",
        "color": "amber",
        "plan_prop": "【C】予定タスク",
        "actual_prop": "【C】実績",
        "score_prop": "【C】スコア",
        "values": ["Private Spark", "Daddy Cool"],
    },
    {
        "key": "Ca",
        "label": "Career",
        "emoji": "💼",
        "subtitle": "収益基盤・起業の種まき",
        "badge": "CAREER",
        "color": "rose",
        "plan_prop": "【Ca】予定タスク",
        "actual_prop": "【Ca】実績",
        "score_prop": "【Ca】スコア",
        "values": ["Perfect Worker"],
    },
    {
        "key": "I",
        "label": "AI",
        "emoji": "🤖",
        "subtitle": "AIスクール・frog・卒業制作",
        "badge": "AI",
        "color": "sky",
        "plan_prop": "【I】予定タスク",
        "actual_prop": "【I】実績",
        "score_prop": "【I】スコア",
        "values": ["Future Tech Explorer"],
    },
]

# ── ルックアップ用 ───────────────────────────────────────────────────────────
CATEGORY_BY_KEY = {c["key"]: c for c in CATEGORIES}
LABEL_BY_KEY = {c["key"]: c["label"] for c in CATEGORIES}
BADGE_BY_KEY = {c["key"]: c["badge"] for c in CATEGORIES}
EMOJI_BY_KEY = {c["key"]: c["emoji"] for c in CATEGORIES}
SUBTITLE_BY_KEY = {c["key"]: c["subtitle"] for c in CATEGORIES}

# AIプロンプト用: "W=Routine、C=Belonging、Ca=Career、I=AI"
CATEGORY_PROMPT_LEGEND = "、".join(
    f'{c["key"]}={c["label"]}' for c in CATEGORIES
)

# 表示用: "🔁 Routine"
def category_display(key: str) -> str:
    c = CATEGORY_BY_KEY[key]
    return f'{c["emoji"]} {c["label"]}'


def now_jst() -> datetime:
    """現在日時（JST）。"""
    return datetime.now(JST)


def today_jst() -> str:
    """今日の日付文字列 YYYY-MM-DD（JST）。"""
    return now_jst().strftime("%Y-%m-%d")


def yesterday_jst() -> str:
    """昨日の日付文字列 YYYY-MM-DD（JST）。"""
    return (now_jst() - timedelta(days=1)).strftime("%Y-%m-%d")

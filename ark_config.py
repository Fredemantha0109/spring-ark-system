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

# ── シーズン目標（Summer Ark）──────────────────────────────────────────────
TRAINING_TARGETS = {
    "bench_press_kg": {"label": "ベンチプレス", "target": 70, "stretch": 72.5, "unit": "kg"},
    "squat_kg": {"label": "スクワット", "target": 105, "stretch": 110, "unit": "kg"},
    "pullup_reps": {"label": "懸垂", "target": 8, "stretch": 10, "unit": "回", "higher_is_better": True},
    "body_weight_kg": {"label": "体重", "target": 62.9, "stretch": 61.9, "unit": "kg", "higher_is_better": False},
    "body_fat_pct": {"label": "体脂肪率", "target": 18.9, "stretch": 15.9, "unit": "%", "higher_is_better": False},
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

# ── Routine サブカテゴリ（表示用。Notionデータ構造は変更しない）────────────
ROUTINE_SUBCATEGORIES = {
    "トレーニング": ["ジム", "ウォーキング"],
    "英語学習": [
        "SB", "OP", "語彙", "リスニング", "瞬間英作文", "英会話",
        "英会話振り返り", "Reuse", "Soccer", "Youtube", "定着学習",
        "Scrambled", "シャドーイング", "ライアン", "動画視聴",
    ],
    "インプット": ["NewsPicks"],
    "内省": ["瞑想", "ジャーナリング", "Shakti"],
}

ROUTINE_SUBCATEGORY_ORDER = ["トレーニング", "英語学習", "インプット", "内省", "未分類"]

ROUTINE_SUBCATEGORY_EMOJI = {
    "トレーニング": "🏋️",
    "英語学習": "📖",
    "インプット": "📰",
    "内省": "🧘",
    "未分類": "❓",
}


def classify_routine_subcategory(task_name: str) -> str:
    """タスク名を Routine サブカテゴリに分類する（部分一致）。"""
    base = task_name.lstrip("🔥").strip()
    for subcat in ROUTINE_SUBCATEGORY_ORDER:
        if subcat == "未分類":
            continue
        for keyword in ROUTINE_SUBCATEGORIES[subcat]:
            if keyword in base:
                return subcat
    return "未分類"


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

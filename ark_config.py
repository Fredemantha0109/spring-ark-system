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


# ── Daily タブ用 習慣4分類（表示・オンザフライスコア。Notionスキーマは不変）──
HABIT_CATEGORIES = [
    {
        "key": "mind",
        "label": "MIND",
        "subtitle": "瞑想・ジャーナリング・Shakti",
        "subcategory": "内省",
        "emoji": "🧘",
        "color": "purple",
    },
    {
        "key": "physical",
        "label": "PHYSICAL",
        "subtitle": "ジム・ウォーキング",
        "subcategory": "トレーニング",
        "emoji": "🏋️",
        "color": "green",
    },
    {
        "key": "english",
        "label": "ENGLISH",
        "subtitle": "TOEIC・英会話",
        "subcategory": "英語学習",
        "emoji": "🇬🇧",
        "color": "blue",
    },
    {
        "key": "knowledge",
        "label": "KNOWLEDGE",
        "subtitle": "NewsPicks等",
        "subcategory": "インプット",
        "emoji": "📰",
        "color": "amber",
    },
]

HABIT_BY_KEY = {c["key"]: c for c in HABIT_CATEGORIES}

# AIプロンプト用: "MIND=瞑想・内省、PHYSICAL=運動、ENGLISH=英語学習、KNOWLEDGE=情報収集"
_HABIT_PROMPT_DESCRIPTIONS = {
    "mind": "瞑想・内省",
    "physical": "運動",
    "english": "英語学習",
    "knowledge": "情報収集",
}
HABIT_PROMPT_LEGEND = "、".join(
    f'{c["label"]}={_HABIT_PROMPT_DESCRIPTIONS[c["key"]]}' for c in HABIT_CATEGORIES
)


def filter_tasks_by_subcategory(tasks, subcategory):
    return [t for t in tasks if classify_routine_subcategory(t) == subcategory]


def compute_habit_scores(plan_tasks, done_tasks):
    """【W】タスクを習慣4分類に振り分け、オンザフライでスコア算出。"""
    from calc_score import calculate_category_score

    scores, plans, dones = {}, {}, {}
    for cat in HABIT_CATEGORIES:
        plan = filter_tasks_by_subcategory(plan_tasks, cat["subcategory"])
        done = filter_tasks_by_subcategory(done_tasks, cat["subcategory"])
        plans[cat["key"]] = plan
        dones[cat["key"]] = done
        scores[cat["key"]] = calculate_category_score(plan, done)
    valid = [s for s in scores.values() if s is not None]
    total = round(sum(valid) / len(valid)) if valid else 0
    return scores, plans, dones, total


def build_missed_habit_tasks(plan_tasks, done_tasks):
    """【W】タスクの未達を習慣4分類ラベル付きで返す。"""
    done_clean = {d.lstrip("🔥") for d in done_tasks}
    subcat_to_label = {c["subcategory"]: c["label"] for c in HABIT_CATEGORIES}
    missed = []
    for task in plan_tasks:
        clean = task.lstrip("🔥")
        if clean not in done_clean:
            subcat = classify_routine_subcategory(clean)
            label = subcat_to_label.get(subcat, "未分類")
            missed.append((clean, label))
    return missed


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

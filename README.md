# spring-ark-system

日次/週次の習慣トラッキング自動化システム。Notionをデータの入力元として、
スコア計算・ダッシュボード生成・LINE通知までを自動化する。

> AI Driven School 4月課題として開発。プロジェクト概要・デザイン意図・開発で得た学びは `index.html`（spring-ark.surge.shで公開）にまとまっている。

## 概要

ARK（Spring Ark）は4つのカテゴリで日々の習慣を計測する:

| カテゴリ | キー | 内容 |
|---|---|---|
| Wellness | W | 体調・運動・回復系の習慣 |
| Communication | C | コミュニケーション系の習慣 |
| Career | Ca | キャリア系の習慣 |
| Input | I | 学習・インプット系の習慣 |

Notionデータベース（体重・体調・睡眠・タスク実績・カレンダー・ジャーナリングを管理）の
各日付ページに「【X】予定タスク」「【X】実績」プロパティ(multi_select)があり、これを起点に全処理が動く。

## システムフロー
① トリガー

毎朝: iPhoneショートカット実行（体重計測直後のルーティン）
随時: Streamlitアプリでタスク完了チェック → Notionに即反映
毎週日曜5:00: GitHub Actions起動 → 翌週タスク自動生成

② ソース（Notion）

体重 / 体調 / 睡眠 / タスク実績 / カレンダー / ジャーナリング
③ 処理（GitHub Actions + Python）

スコア計算 → HTML生成 → Claude APIで推奨作戦を生成
④ 届け先（Surge + LINE）

Surge: HTMLダッシュボード公開

LINE: プッシュ通知

## 構成

### フロントエンド
- **app.py** — Streamlit製の日次タスク管理UI。今日のNotionページを取得し、
  カテゴリごとに予定タスクの追加/削除、実績のチェックを行い、Notionに保存する。
- **index.html** — プロジェクト紹介ページ（Daily/Weekly/Monthlyダッシュボードのプレビュー、
  システムフロー図、開発の振り返りを掲載。spring-ark.surge.shで公開）

### 自動化スクリプト（GitHub Actions経由）
- **force_priority.py** — 指定タスクに🔥マークを付けて該当カテゴリの予定タスクへ強制追加する。
  `client_payload`で`task_name`と`category`(W/C/Ca/I)を受け取り、`force_priority.yml`から呼ばれる。
  同名タスクがあれば置き換え、🔥済みなら何もしない(冪等)。
- **force_shakti.py** — force_priorityの仕組みを使い、毎日自動でWellnessカテゴリに
  「🔥シャクティマット昼寝25分」を強制追加する。シャクティマットでの昼寝による回復を習慣化する狙い。
- **scoring.py / calc_score.py** — 実績データからスコアを計算する。コンディション
  （良好／普通／要改善）は体調自己評価と睡眠時間から、多忙度（余裕日／普通日／多忙日）は
  カレンダーの合計時間から自動判定する。
- **generate_dashboard.py / generate_dashboard_english.py** — 日次ダッシュボードを生成する(日本語/英語版)。
  Claude APIによる推奨作戦の生成を含む。
- **generate_weekly.py** — 週次レポートを生成する。
- **send_line.py** — 生成したレポート/通知をLINEに送信する。

### スケジューリング
- **.github/workflows/** — 上記スクリプトを毎日/毎週、定期実行する(repository_dispatchトリガー中心)。

## 依存パッケージ

- `streamlit` — UI
- `requests` — Notion API呼び出し
- `google-auth` / `google-api-python-client` — Googleカレンダー連携（多忙度判定用）

## 環境変数

- `NOTION_API_TOKEN` / `NOTION_TOKEN`
- `NOTION_DATABASE_ID` / `DATABASE_ID`
- `TASK_NAME`, `CATEGORY`（force_priority.py用、GitHub Actions経由）

## デザイン上の工夫

- Daily / Weekly / Monthlyの3つの時間軸でタブ切り替え
- Weekly・Monthlyには英語学習・ジャーナル・筋トレなど個別トピックのAI分析タブ
- スコアはパーセントでなく点数表示（60%より60点の方が前向きになれる）

## 開発で得た学び

- 設計が先：バグ潰しより「何を表示すべきか」を問い直す方が近道
- 使うAIで体験が変わる：Gemini→Claude切り替えで作業時間が体感半分
- 足し算と引き算は同じくらい重要：何を入れないかが洗練を決める
- 自分専用が最強：自分の困りごとを自分専用アプリとして作ることが最大効果を生む

## 注意事項

- タイムゾーンは現在 `Asia/Singapore`(UTC+8)で固定。2026年7月の日本帰国後はJST(UTC+9)への変更が必要。

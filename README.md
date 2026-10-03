# Tech0 — 左レールの機能切り替え

Tech0 フロントエンドのうち、**左レールの機能切り替え部分のみ**を担当するリポジトリです。
右側のコンテンツ(検索画面 / レビュー画面)は同僚2名が別途実装します。

## 構成

```
app.py                        エントリポイント(レール描画 → 機能呼び出し)
shell/feature_switcher.py     ★左レールの機能切り替え(担当分)
shell/registry.py             機能キー → features/* の解決 + プレースホルダ
features/tech0_search.py      たくちゃんの実装スケルトン(render() を実装)
features/tech0_review.py      おのちゃんの実装スケルトン(render() を実装)
INTERFACE.md                  3人で共有する連携仕様
test_switcher.py              レールの自動検証(AppTest)
requirements.txt              依存パッケージ
.streamlit/config.toml        テーマ設定
```

## 実行

```bash
pip install -r requirements.txt
streamlit run app.py
```

左レールで **Tech0 Search / Tech0 Review** を切り替えます。
選択状態は URL に入るため、`?feature=review` のリンクをそのまま共有できます。

## 検証

```bash
python test_switcher.py
# → === RESULT: ALL PASS
```

## 同僚への依頼事項

`INTERFACE.md` を参照してください。要点だけ:

- `features/<モジュール>.py` に `render()` を1つ公開する(引数なし・戻り値なし)
- ウィジェットの `key` は `search_` / `review_` の接頭辞を付ける
- `shell/` 配下は編集しない(ラベル変更などは本担当へ依頼)

## 機能を増やすとき

1. `shell/feature_switcher.py` の `FEATURES` に1行追加
2. `shell/registry.py` の `MODULES` に `key → features.<モジュール>` を追加
3. `features/<モジュール>.py` に `render()` を用意

## Tech0 Review（担当: おのちゃん）

SI 工程ごとのレビュー項目（Excel）に照らして、提出文書を AI（gpt-4.1-mini）が項目ごとに OK/NG 判定します。

### 準備
- リポジトリ直下の `.env` に `OPENAI_API_KEY=…` を書く（Git には含めない）
- レビュワーを登録する（画面からは登録できません）
  `python create_reviewer.py <ユーザー名> --display-name 表示名`

### 使い方
1. **レビュー項目の登録(管理用)** タブ：ログイン → 工程を選ぶ → レビュー項目 Excel（No／チェック項目／観点）をアップロード → 登録
2. **ドキュメントレビュー実施** タブ：工程を選ぶ → 文書をアップロード（docx／xlsx／pptx／pdf／txt／csv）または Google ドキュメントの URL → 「AI でレビューする」→ 結果カードを確認 → Excel でダウンロード

### 補足
- レビュワーとレビュー項目は `data/review.db`（SQLite）に保存します。レビュー結果は保存しません
- 文書は先頭 10 万字までを評価します
- Google ドキュメントの取り込みには、リポジトリ直下の `credentials.json` が必要です（初回はブラウザで認証）
- テスト：`python -m pytest tests/test_review.py`

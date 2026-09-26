# 3人で共有するインターフェース取り決め

Tech0 のフロントエンドは **左レールの機能切り替え(本人担当)** と
**各機能の画面(同僚2名担当)** を分離して開発します。
この分離を壊さないための最小ルールだけをまとめます。

---

## 1. ファイルと担当

| ファイル | 担当 | 役割 |
|---|---|---|
| `app.py` | 本人 | エントリポイント。レール描画 → 機能の呼び出し |
| `shell/feature_switcher.py` | **本人(変更不可)** | 機能の定義・切り替えボタン・URL同期・レールCSS |
| `shell/registry.py` | 本人 | 機能キー → 同僚モジュールの解決。プレースホルダ表示 |
| `features/tech0_search.py` | 同僚A | `render()` を実装 |
| `features/tech0_review.py` | 同僚B | `render()` を実装 |

`shell/` 配下は本人が保守します。同僚は触らず、必要な変更は本人に依頼してください
(機能の追加・ラベルの変更は `FEATURES` の1行で済みます)。

---

## 2. 同僚側の契約(これだけ守れば大丈夫)

```python
# features/tech0_search.py
def render() -> None:
    ...
```

- **引数なし・戻り値なし**で `render()` を1つ公開する。
- `render()` は「左レールで自機能が選ばれているときに1回」呼ばれる。**再実行は何度も来る**ので、
  初期化は `st.session_state.setdefault(...)` で1回だけ行う。
- 画面の見出し・説明・本文は `render()` の中に書く(共有ヘッダーは現状なし)。

### ウィジェットの key は機能ごとに接頭辞を付ける

```python
st.text_input("キーワード", key="search_query")   # 同僚A
st.selectbox("項目", ITEMS, key="review_item")    # 同僚B
```

`session_state` とウィジェットIDはアプリ全体で1つの名前空間を共有します。
接頭辞がないと、機能をまたいだときに `DuplicateWidgetID` や
「値が意図せず保持される」不具合が起きます。

| 機能 | 接頭辞 |
|---|---|
| Tech0 Search | `search_` |
| Tech0 Review | `review_` |

### 触ってよい session_state / URL パラメータ

| 名前 | 所有者 | 意味 |
|---|---|---|
| `feature` / `?feature=` | **本人** | 選択中の機能キー(`search` / `review`)。同僚は読み取りのみ |
| `search_*` | 同僚A | 自由に利用 |
| `review_*` | 同僚B | 自由に利用 |

---

## 3. スタイル(CSS)の扱い

- 本人が `inject_rail_style()` で **左レール + 共通の下地**(背景色・フォント・`.stApp` など)を注入済み。
  `--canvas` `--panel` `--line` `--ink` `--muted` `--blue` の CSS 変数が使えます。
- 同僚は自分の画面用の CSS だけを、**自分の `render()` の中**に閉じて書く:

```python
def render() -> None:
    st.html("""
      <style>
        /* 他機能に漏れないよう、必ず自分のクラス名でスコープを切る */
        .search-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
      </style>
    """)
```

- Streamlit の内部クラス(`[data-testid="..."]`)を狙う場合は、`requirements.txt` で
  バージョンを固定したままにして、変更時は本人に一声かけてください。

---

## 4. 実行と確認

```bash
pip install -r requirements.txt
streamlit run app.py
# → 左レールで Tech0 Search / Tech0 Review を切り替え
# → URL に ?feature=review が付き、そのまま共有できる
```

- たくちゃん・おのちゃんのファイルが未実装でもアプリは起動し、その機能の位置に**プレースホルダ**が出ます。
  レール側の開発は同僚の進捗に依存しません。
- 検証スクリプト: `python test_switcher.py`(切り替え・URL同期・プレースホルダを自動確認)

---

## 5. 機能を増やすとき(本人向けメモ)

1. `shell/feature_switcher.py` の `FEATURES` に1行追加(`key` / `label` / `desc` / `icon`)
2. `shell/registry.py` の `MODULES` に `key → features.<モジュール>` を追加
3. `features/<モジュール>.py` に `render()` を用意

レールの UI・URL 同期・プレースホルダは自動でついてきます。

---

## 6. 引き継ぎ前チェックリスト

- [ ] `python test_switcher.py` が ALL PASS
- [ ] `?feature=review` を直接開いても Review が選択された状態で起動する
- [ ] `?feature=xxx`(不正値)でも既定機能で起動する(落ちない)
- [ ] たくちゃん・おのちゃんがファイルを削除してもアプリが起動する(プレースホルダ表示)
- [ ] レールのラベル・説明を変えたい場合は本人に依頼(同僚は `FEATURES` を触らない)

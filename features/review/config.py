"""Tech0 Review の設定値。"""

from pathlib import Path

# SI の 11 工程(画面の選択肢と、DB の phase 列に入る値)
PHASES = [
    "企画",
    "要求定義",
    "要件定義",
    "基本設計",
    "詳細設計",
    "実装",
    "単体テスト",
    "結合テスト",
    "システムテスト",
    "受入テスト",
    "運用・保守",
]

# リポジトリ直下の data/review.db。起動した場所(カレントディレクトリ)に左右されないよう、
# このファイルの位置から組み立てる。data/ は .gitignore 済み。
REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DB_PATH = REPO_ROOT / "data" / "review.db"

# 判定に使うモデル。gpt-4o-mini ではデモ文書の不備の見逃しが多かったため、gpt-4.1-mini に変更(10/2 チーム決定)。
# デモ文書での比較: 要件定義書の不備 gpt-4o-mini 6/7 → gpt-4.1-mini 7/7、基本設計書 1/8 → 3/8
MODEL = "gpt-4.1-mini"
BATCH_SIZE = 10  # 1 回の API 呼び出しで判定するレビュー項目の数

# 評価する本文の上限(文字数)。超えた分は切り捨て、画面と Excel にその旨を出す。
# モデルには全文が入る大きさなので、ベクトル検索での絞り込みはしない
# (レビューでは「書いていないこと」の検出が重要で、全文を渡すほうが確実なため)。
MAX_DOC_CHARS = 100_000

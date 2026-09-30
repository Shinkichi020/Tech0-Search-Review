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

MODEL = "gpt-4o-mini"
BATCH_SIZE = 10  # 1 回の API 呼び出しで判定するレビュー項目の数

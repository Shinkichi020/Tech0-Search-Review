"""review.db(SQLite)の読み書き。

どの関数も db_path を省略すると config.REVIEW_DB_PATH を使う。
テストでは一時フォルダの DB を渡して、本番の DB を汚さないようにする。
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from features.review.config import REVIEW_DB_PATH

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """DB に接続する。フォルダやテーブルがなければ作る。"""
    path = Path(db_path or REVIEW_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # 列名で値を取り出せるようにする
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


# ---------------------------------------------------------------- レビュワー

def add_reviewer(
    username: str,
    display_name: str | None,
    password_hash: str,
    salt: str,
    db_path: str | Path | None = None,
) -> None:
    """レビュワーを 1 人追加する。同じ username があれば sqlite3.IntegrityError。"""
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO reviewers (username, display_name, password_hash, salt) VALUES (?, ?, ?, ?)",
            (username, display_name, password_hash, salt),
        )


def get_reviewer(username: str, db_path: str | Path | None = None) -> dict | None:
    """username でレビュワーを 1 人取得する。いなければ None。"""
    with closing(get_connection(db_path)) as conn:
        row = conn.execute("SELECT * FROM reviewers WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- レビュー項目

def replace_review_items(
    phase: str,
    items: list[dict],
    uploaded_by: str,
    db_path: str | Path | None = None,
) -> int:
    """その工程のレビュー項目を丸ごと置き換え、登録した件数を返す。

    削除と追加を 1 つのトランザクションで行うので、途中で失敗しても
    「古い項目が消えて新しい項目が入っていない」状態にはならない。
    """
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute("DELETE FROM review_items WHERE phase = ?", (phase,))
        conn.executemany(
            "INSERT INTO review_items (phase, item_no, check_item, viewpoint, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            [(phase, it["item_no"], it["check_item"], it.get("viewpoint"), uploaded_by) for it in items],
        )
    return len(items)


def get_review_items(phase: str, db_path: str | Path | None = None) -> list[dict]:
    """その工程のレビュー項目を No 順に返す。"""
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            "SELECT item_no, check_item, viewpoint, uploaded_by, uploaded_at"
            " FROM review_items WHERE phase = ? ORDER BY item_no",
            (phase,),
        ).fetchall()
    return [dict(r) for r in rows]


def count_items_by_phase(db_path: str | Path | None = None) -> dict[str, int]:
    """工程 → 登録件数。登録のない工程は含まれない。"""
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute("SELECT phase, COUNT(*) AS n FROM review_items GROUP BY phase").fetchall()
    return {r["phase"]: r["n"] for r in rows}

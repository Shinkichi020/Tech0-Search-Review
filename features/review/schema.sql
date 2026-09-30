-- Tech0 Review のテーブル定義。db.get_connection() が接続のたびに実行する(IF NOT EXISTS なので何度実行しても安全)。

-- レビュワー(管理者が create_reviewer.py で登録する。パスワードはハッシュのみ保存)
CREATE TABLE IF NOT EXISTS reviewers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  display_name  TEXT,
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 工程ごとのレビュー項目(同じ工程を登録し直すと丸ごと置き換える)
CREATE TABLE IF NOT EXISTS review_items (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  phase       TEXT NOT NULL,
  item_no     INTEGER NOT NULL,
  check_item  TEXT NOT NULL,
  viewpoint   TEXT,
  uploaded_by TEXT,
  uploaded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  UNIQUE (phase, item_no)
);

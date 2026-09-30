"""Tech0 Review のテスト。

実行(リポジトリ直下で): python -m pytest tests/test_review.py
DB はテストごとの一時フォルダに作るので、本番の data/review.db は汚さない。
"""

import sqlite3
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features.review import auth, db  # noqa: E402
from features.review.checklist_loader import ChecklistError, import_checklist, parse_excel  # noqa: E402


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "review.db"


@pytest.fixture(autouse=True)
def fast_hash(monkeypatch):
    """本番の 60 万回だとテストが遅いので、繰り返し回数を減らす(仕組みは同じ)。"""
    monkeypatch.setattr(auth, "ITERATIONS", 1_000)


def make_excel(path: Path, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


# ---------------------------------------------------------------- ハッシュ・認証

def test_hash_is_reproducible_with_same_salt():
    h1, salt = auth.hash_password("secret-pass")
    h2, _ = auth.hash_password("secret-pass", salt)
    assert h1 == h2
    assert "secret-pass" not in h1


def test_hash_differs_by_salt():
    h1, s1 = auth.hash_password("secret-pass")
    h2, s2 = auth.hash_password("secret-pass")
    assert s1 != s2
    assert h1 != h2


def test_verify_login(db_path):
    auth.register_reviewer("reviewer1", "correct-pass", "レビュワー1", db_path=db_path)

    assert auth.verify_login("reviewer1", "correct-pass", db_path=db_path) == {
        "username": "reviewer1",
        "display_name": "レビュワー1",
    }
    assert auth.verify_login("reviewer1", "wrong-pass", db_path=db_path) is None
    assert auth.verify_login("nobody", "correct-pass", db_path=db_path) is None


def test_password_is_not_stored_in_plain_text(db_path):
    auth.register_reviewer("reviewer1", "correct-pass", db_path=db_path)
    row = db.get_reviewer("reviewer1", db_path=db_path)
    assert "correct-pass" not in row.values()


def test_duplicate_username_is_rejected(db_path):
    auth.register_reviewer("reviewer1", "pass-1", db_path=db_path)
    with pytest.raises(sqlite3.IntegrityError):
        auth.register_reviewer("reviewer1", "pass-2", db_path=db_path)


# ---------------------------------------------------------------- Excel 解析

def test_parse_excel_finds_header_and_skips_rows(tmp_path):
    path = make_excel(tmp_path / "items.xlsx", [
        ["基本設計レビュー項目シート"],               # タイトル行
        [],
        ["No.", "レビュー項目", "観点"],               # 見出しの表記ゆれ(No. / レビュー項目)
        [1, "画面遷移図が記載されている", "主要画面の遷移が図示されているか"],
        [],                                             # 空行
        [2, None, "チェック項目が空の行"],             # 無視される
        [3.0, "エラー処理が定義されている", None],      # No が 3.0、観点なし
    ])

    items, skipped = parse_excel(path)

    assert items == [
        {"item_no": 1, "check_item": "画面遷移図が記載されている", "viewpoint": "主要画面の遷移が図示されているか"},
        {"item_no": 3, "check_item": "エラー処理が定義されている", "viewpoint": ""},
    ]
    assert len(skipped) == 1 and "6 行目" in skipped[0]


def test_parse_excel_without_header_raises(tmp_path):
    path = make_excel(tmp_path / "no_header.xlsx", [["項目A", "説明"], ["x", "y"]])
    with pytest.raises(ChecklistError, match="見出し行"):
        parse_excel(path)


def test_parse_excel_duplicate_no_raises(tmp_path):
    path = make_excel(tmp_path / "dup.xlsx", [
        ["No", "チェック項目", "観点"],
        [1, "項目A", ""],
        [1, "項目B", ""],
    ])
    with pytest.raises(ChecklistError, match="重複"):
        parse_excel(path)


def test_parse_excel_invalid_no_raises(tmp_path):
    path = make_excel(tmp_path / "bad_no.xlsx", [
        ["No", "チェック項目", "観点"],
        ["一", "項目A", ""],
    ])
    with pytest.raises(ChecklistError, match="整数"):
        parse_excel(path)


def test_parse_excel_rejects_non_excel(tmp_path):
    path = tmp_path / "fake.xlsx"
    path.write_text("これは Excel ではない", encoding="utf-8")
    with pytest.raises(ChecklistError, match="読み込めません"):
        parse_excel(path)


# ---------------------------------------------------------------- 登録(置き換え)

def test_import_checklist_replaces_same_phase(db_path):
    first = [{"item_no": i, "check_item": f"項目{i}", "viewpoint": ""} for i in (1, 2, 3)]
    second = [{"item_no": 1, "check_item": "新しい項目", "viewpoint": "新しい観点"}]

    import_checklist("基本設計", first, "reviewer1", db_path=db_path)
    import_checklist("要件定義", first, "reviewer1", db_path=db_path)
    import_checklist("基本設計", second, "reviewer1", db_path=db_path)

    assert db.count_items_by_phase(db_path=db_path) == {"基本設計": 1, "要件定義": 3}
    stored = db.get_review_items("基本設計", db_path=db_path)
    assert stored[0]["check_item"] == "新しい項目"
    assert stored[0]["uploaded_by"] == "reviewer1"


def test_import_checklist_rejects_unknown_phase(db_path):
    with pytest.raises(ValueError):
        import_checklist("存在しない工程", [{"item_no": 1, "check_item": "x", "viewpoint": ""}], "r", db_path=db_path)


def test_failed_replace_keeps_old_items(db_path):
    """No が重複していて INSERT が失敗しても、元の項目は消えない(トランザクション)。"""
    import_checklist("基本設計", [{"item_no": 1, "check_item": "元の項目", "viewpoint": ""}], "r", db_path=db_path)
    broken = [{"item_no": 1, "check_item": "A", "viewpoint": ""}, {"item_no": 1, "check_item": "B", "viewpoint": ""}]

    with pytest.raises(sqlite3.IntegrityError):
        import_checklist("基本設計", broken, "r", db_path=db_path)

    assert [it["check_item"] for it in db.get_review_items("基本設計", db_path=db_path)] == ["元の項目"]

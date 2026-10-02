"""Tech0 Review のテスト。

実行(リポジトリ直下で): python -m pytest tests/test_review.py
DB はテストごとの一時フォルダに作るので、本番の data/review.db は汚さない。
"""

import io
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


# ---------------------------------------------------------------- 文書の読み込み(loader)

from docx import Document  # noqa: E402

from features.review import loader  # noqa: E402
from features.review.loader import LoaderError, load_bytes, parse_google_url  # noqa: E402


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-8", "cp932"])
def test_decode_text_detects_encoding(encoding):
    text = "要件定義書　第1章 はじめに"
    assert loader._decode_text(text.encode(encoding)) == text


def test_load_txt_in_shift_jis():
    assert load_bytes("memo.txt", "画面遷移図を以下に示す。".encode("cp932")) == "画面遷移図を以下に示す。"


def test_load_csv_joins_cells():
    data = "No,項目\n1,ログイン画面\n\n2,一覧画面\n".encode("utf-8-sig")
    assert load_bytes("list.csv", data) == "No | 項目\n1 | ログイン画面\n2 | 一覧画面"


def test_load_docx_reads_tables_in_order():
    doc = Document()
    doc.add_paragraph("1.2 システム化の方針")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "区分", "方針"
    table.cell(1, 0).text, table.cell(1, 1).text = "基盤方針", "クラウド上に構築する"
    doc.add_paragraph("1.3 設計対象範囲")
    buf = io.BytesIO()
    doc.save(buf)

    assert load_bytes("design.docx", buf.getvalue()) == (
        "1.2 システム化の方針\n区分 | 方針\n基盤方針 | クラウド上に構築する\n1.3 設計対象範囲"
    )


def test_load_normalizes_radicals():
    """PDF に混ざる部首文字(⽬ U+2F6C)は通常の漢字(目)にそろえる。"""
    assert load_bytes("a.txt", "⽬次".encode("utf-8")) == "目次"


def test_load_rejects_unsupported_and_empty():
    with pytest.raises(LoaderError, match="対応していません"):
        load_bytes("image.png", b"\x89PNG")
    with pytest.raises(LoaderError, match="抽出できませんでした"):
        load_bytes("empty.txt", b"  \n ")


def test_parse_google_url():
    assert parse_google_url("https://docs.google.com/document/d/abc_123-XYZ/edit?usp=sharing") == ("document", "abc_123-XYZ")
    assert parse_google_url("https://docs.google.com/spreadsheets/d/S1/edit#gid=0") == ("spreadsheets", "S1")
    with pytest.raises(LoaderError):
        parse_google_url("https://example.com/document/d/abc")


def test_fetch_google_doc_without_credentials(monkeypatch):
    import utils.google_drive as gd

    def no_credentials():
        raise FileNotFoundError("credentials.json")

    monkeypatch.setattr(gd, "get_drive_service", no_credentials)
    with pytest.raises(LoaderError, match="credentials.json"):
        loader.fetch_google_doc("https://docs.google.com/document/d/abc/edit")

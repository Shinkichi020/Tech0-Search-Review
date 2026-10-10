"""レビュー項目 Excel の解析と登録。

想定する形式: 1 枚目のシートに「No」「チェック項目」「観点」の見出し行がある一覧表。
  - 見出しは 1 行目とは限らない(タイトル行などがあってもよい)ので、上から探す
  - 見出しの表記ゆれ(「No.」「レビュー項目」など)は HEADER_ALIASES で吸収する
  - 空行は除外、「チェック項目」が空の行は無視(skipped として返す)
"""

import unicodedata
from pathlib import Path
from typing import BinaryIO

import openpyxl

from features.review import db
from features.review.config import PHASES

# 見出しの候補(比較は _normalize() した後の文字列で行う)
HEADER_ALIASES = {
    "item_no": {"no", "番号", "項番"},
    "check_item": {"チェック項目", "レビュー項目", "確認項目"},
    "viewpoint": {"観点", "確認観点", "チェック観点", "レビュー観点"},
}
HEADER_SEARCH_ROWS = 20  # 見出し行を探す範囲(上から何行目まで)


class ChecklistError(ValueError):
    """Excel の形式が想定と違うときのエラー。メッセージはそのまま画面に出す。"""


def _normalize(value) -> str:
    """全角/半角・大文字/小文字・空白・末尾の「.」をそろえて比較しやすくする。"""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return text.replace(" ", "").rstrip(".")


def _find_header(rows: list[tuple]) -> tuple[int, dict[str, int]]:
    """(見出し行の番号(0 始まり), {"item_no": 列番号, ...}) を返す。"""
    for r, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        columns = {}
        for c, cell in enumerate(row):
            if cell is None:
                continue
            name = _normalize(cell)
            for key, aliases in HEADER_ALIASES.items():
                if name in aliases and key not in columns:
                    columns[key] = c
        if "check_item" in columns:
            return r, columns
    raise ChecklistError(
        "見出し行が見つかりませんでした。1 枚目のシートに「No」「チェック項目」「観点」の見出しを入れてください。"
    )


def _cell_text(row: tuple, col: int | None) -> str:
    if col is None or col >= len(row) or row[col] is None:
        return ""
    return str(row[col]).strip()


def _to_item_no(value, excel_row: int) -> int:
    """No を整数にする(Excel では 1 が 1.0 で入っていることもある)。"""
    try:
        number = float(str(value).strip())
    except ValueError:
        number = None
    if number is None or not number.is_integer() or number < 1:
        raise ChecklistError(f"{excel_row} 行目の No「{value}」が 1 以上の整数ではありません。")
    return int(number)


def parse_excel(file: str | Path | BinaryIO) -> tuple[list[dict], list[str]]:
    """Excel を読み、(レビュー項目のリスト, 無視した行の説明のリスト) を返す。

    レビュー項目は {"item_no": int, "check_item": str, "viewpoint": str} の形。
    file にはパスでも、Streamlit のアップロードファイル(BytesIO など)でも渡せる。
    """
    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    except Exception as e:
        raise ChecklistError(f"Excel ファイルとして読み込めませんでした（{type(e).__name__}）。") from e
    try:
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
    finally:
        wb.close()

    header_idx, cols = _find_header(rows)
    items: list[dict] = []
    skipped: list[str] = []
    seen_nos: dict[int, int] = {}  # No → その No が最初に出た Excel の行番号

    for offset, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        excel_row = offset  # Excel 上の行番号(1 始まり)
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue  # 空行
        check_item = _cell_text(row, cols["check_item"])
        raw_no = _cell_text(row, cols.get("item_no"))
        if not check_item:
            label = f"No.{raw_no}" if raw_no else "No なし"
            skipped.append(f"{excel_row} 行目（{label}）：チェック項目が空のため無視しました")
            continue

        if "item_no" in cols:
            if not raw_no:
                raise ChecklistError(f"{excel_row} 行目の No が空です。")
            item_no = _to_item_no(raw_no, excel_row)
        else:
            item_no = len(items) + 1  # No 列がなければ上から連番を振る

        if item_no in seen_nos:
            raise ChecklistError(
                f"No.{item_no} が重複しています（{seen_nos[item_no]} 行目と {excel_row} 行目）。"
            )
        seen_nos[item_no] = excel_row
        items.append({
            "item_no": item_no,
            "check_item": check_item,
            "viewpoint": _cell_text(row, cols.get("viewpoint")),
        })

    if not items:
        raise ChecklistError("登録できるレビュー項目が 1 件もありませんでした。")
    return items, skipped


def import_checklist(
    phase: str,
    items: list[dict],
    db_path: str | Path | None = None,
) -> int:
    """その工程のレビュー項目を丸ごと置き換えて登録し、件数を返す。"""
    if phase not in PHASES:
        raise ValueError(f"未知の工程です: {phase}")
    if not items:
        raise ValueError("登録するレビュー項目がありません。")
    return db.replace_review_items(phase, items, db_path)

"""提出文書からテキストを取り出す。

  - .txt / .csv : 文字コードを自動判定して読む(_decode_text)
  - .docx       : 段落と表を文書の順番どおりに読む(utils/parser.py は表を読まないため自前で読む)
  - .xlsx / .pptx / .pdf : 一時ファイルに書き出して utils/parser.py に渡す
  - Google ドキュメント類 : URL からファイル ID を取り出し、Drive API の export でテキスト化する

取り出したテキストは NFKC で正規化する(PDF に混ざる「⽬」のような部首文字を「目」にそろえるため)。
AI に渡す本文と、根拠の照合に使う本文が同じになるよう、正規化はここで 1 回だけ行う。
"""

import csv
import io
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import BinaryIO

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from utils.parser import extract_text_from_file

SUPPORTED_EXTS = (".txt", ".csv", ".docx", ".xlsx", ".pptx", ".pdf")

# 試す順番。UTF-8(BOM 付き → なし)で読めなければ Windows の日本語(CP932 → Shift_JIS)を試す。
ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis")

# Google ドキュメント類の URL → (種類, ファイル ID)
_GOOGLE_URL_RE = re.compile(
    r"https://docs\.google\.com/(document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)"
)
_EXPORT_MIME = {
    "document": "text/plain",
    "presentation": "text/plain",
    "spreadsheets": "text/csv",  # 1 枚目のシートだけが出力される(Drive API の仕様)
}


class LoaderError(ValueError):
    """文書を読めなかったときのエラー。メッセージはそのまま画面に出す。"""


# ---------------------------------------------------------------- ファイル

def load_uploaded(file: BinaryIO) -> str:
    """Streamlit のアップロードファイルからテキストを取り出す。"""
    return load_bytes(file.name, file.getvalue())


def load_bytes(file_name: str, data: bytes) -> str:
    """ファイル名(拡張子で形式を判断)と中身のバイト列から、テキストを取り出す。"""
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise LoaderError(f"{ext or '拡張子なし'} のファイルには対応していません。")

    if ext == ".txt":
        text = _decode_text(data)
    elif ext == ".csv":
        text = _csv_to_text(_decode_text(data))
    elif ext == ".docx":
        text = _docx_text(data)
    else:
        text = _extract_with_parser(ext, data)

    text = _clean(text)
    if not text:
        raise LoaderError(
            "文書からテキストを抽出できませんでした。画像だけの PDF やパスワード付きのファイルは読み取れません。"
        )
    return text


def _decode_text(data: bytes) -> str:
    """ENCODINGS の順に試し、最初に読めた文字コードで文字列にする。"""
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise LoaderError("文字コードを判定できませんでした（UTF-8 / Shift_JIS 以外の可能性があります）。")


def _csv_to_text(text: str) -> str:
    """CSV の各行を「 | 」区切りの 1 行にする(AI が列の区切りを読み取りやすいように)。"""
    rows = csv.reader(io.StringIO(text))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(c.strip() for c in row))


def _docx_text(data: bytes) -> str:
    """段落と表を、文書に出てくる順番どおりに読む。表は 1 行を「 | 」区切りの 1 行にする。"""
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise LoaderError(f"Word ファイルとして読み込めませんでした（{type(e).__name__}）。") from e

    lines: list[str] = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(block, doc).text)
        elif tag == "tbl":
            for row in Table(block, doc).rows:
                cells: list[str] = []
                for cell in row.cells:
                    value = cell.text.strip()
                    if not cells or cells[-1] != value:  # 結合セルは同じ値が続くので 1 つにまとめる
                        cells.append(value)
                if any(cells):
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_with_parser(ext: str, data: bytes) -> str:
    """一時ファイルに書き出して utils/parser.py に渡す(parser はパスしか受け取らないため)。

    Windows では開いたままのファイルを別の処理から開けないので、書き込んで閉じてから渡し、
    最後に必ず削除する。一時ファイルは OS の一時フォルダに作られる(リポジトリには作らない)。
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        return extract_text_from_file(path)  # 失敗しても例外は出さず空文字を返す
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# NFKC では普通の文字にならないが、PDF から取り出すと混ざりやすい文字
# (CJK 部首補助の「⻑」など、英語用の中点「‧」、割り算の斜線「∕」)
_EXTRA_NORMALIZE = str.maketrans({
    "⻑": "長", "⻄": "西", "⻘": "青", "⻝": "食", "⻤": "鬼", "⻣": "骨",
    "⻩": "黄", "⻭": "歯", "⻆": "角", "⻁": "虎", "⻌": "辶", "‧": "・", "∕": "/",
})


def normalize_text(text: str) -> str:
    """NFKC 正規化に加えて、NFKC で直らない文字もそろえる(根拠の照合でも同じ関数を使う)。"""
    return unicodedata.normalize("NFKC", text).translate(_EXTRA_NORMALIZE)


def _clean(text: str) -> str:
    """文字の正規化・改行コードの統一・行末の空白除去・3 行以上の空行を 1 行にまとめる。"""
    text = normalize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------------------------------------------------------------- Google ドキュメント類

def parse_google_url(url: str) -> tuple[str, str]:
    """Google ドキュメント類の URL から (種類, ファイル ID) を取り出す。"""
    match = _GOOGLE_URL_RE.search(url.strip())
    if not match:
        raise LoaderError(
            "Google ドキュメント／スプレッドシート／スライドの URL を貼ってください"
            "（https://docs.google.com/document/d/… の形）。"
        )
    return match.group(1), match.group(2)


def fetch_google_doc(url: str) -> tuple[str, str]:
    """URL の文書を Drive API で取り出し、(ファイル名, テキスト) を返す。

    認証は utils/google_drive.py(たくちゃん担当)を使う。token.json がなければ、
    初回だけブラウザで Google の認証画面が開く。
    """
    kind, file_id = parse_google_url(url)

    # Google のライブラリは使うときだけ読み込む(この画面を開いただけで Google に接続しないため)
    from googleapiclient.errors import HttpError

    from utils.google_drive import get_drive_service

    try:
        service = get_drive_service()
        name = service.files().get(fileId=file_id, fields="name").execute()["name"]
        data = service.files().export(fileId=file_id, mimeType=_EXPORT_MIME[kind]).execute()
    except FileNotFoundError as e:
        raise LoaderError(
            "Google の認証ファイル（credentials.json）がありません。リポジトリ直下に置いてから、もう一度お試しください。"
        ) from e
    except HttpError as e:
        if e.resp.status in (403, 404):
            raise LoaderError("文書が見つからないか、閲覧する権限がありません。URL と共有設定を確認してください。") from e
        raise LoaderError(f"Google ドライブから文書を取得できませんでした（HTTP {e.resp.status}）。") from e

    text = _decode_text(data)
    if kind == "spreadsheets":
        text = _csv_to_text(text)
    text = _clean(text)
    if not text:
        raise LoaderError("文書が空のため、テキストを取り出せませんでした。")
    return name, text

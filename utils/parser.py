"""各種ファイル（txt, pdf, docx, xlsx, pptx）から本文テキストを抽出するモジュール"""

import os
from pathlib import Path
from pypdf import PdfReader
from docx import Document
import openpyxl
from pptx import Presentation

def extract_text_from_file(file_path: str) -> str:
    """指定されたパスのファイルからテキストを読み出して返す"""
    path = Path(file_path)
    ext = path.suffix.lower()
    text = ""

    try:
        # テキストファイル (.txt)
        if ext == ".txt":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        # PDF ファイル (.pdf)
        elif ext == ".pdf":
            reader = PdfReader(path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

        # Word ファイル (.docx)
        elif ext == ".docx":
            doc = Document(path)
            text = "\n".join([p.text for p in doc.paragraphs if p.text])

        # Excel ファイル (.xlsx)
        elif ext == ".xlsx":
            wb = openpyxl.load_workbook(path, data_only=True)
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                for row in ws.iter_rows(values_only=True):
                    row_text = " ".join([str(cell) for cell in row if cell is not None])
                    if row_text.strip():
                        text += row_text + "\n"

        # PowerPoint ファイル (.pptx)
        elif ext == ".pptx":
            prs = Presentation(path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text += shape.text + "\n"

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return text.strip()


def load_all_documents(folder_path: str = "dummy_data") -> list[dict]:
    """指定フォルダ内の全サポートファイルを一括読み込みしてリストで返す"""
    documents = []
    folder = Path(folder_path)

    if not folder.exists():
        return documents

    supported_exts = {".txt", ".pdf", ".docx", ".xlsx", ".pptx"}

    for file_p in folder.rglob("*"):
        if file_p.is_file() and file_p.suffix.lower() in supported_exts:
            content = extract_text_from_file(str(file_p))
            if content:
                documents.append({
                    "id": file_p.name,
                    "filename": file_p.name,
                    "content": content,
                    "path": str(file_p)
                })

    return documents
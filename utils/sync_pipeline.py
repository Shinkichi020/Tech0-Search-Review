"""
Google Drive からファイルを取得し、テキスト抽出〜チャンク分割〜ChromaDBへのインデックス化を一括で行う同期パイプライン
"""

import os
from pathlib import Path
from utils.chroma_handler import get_chroma_collection
from utils.google_drive import download_file, list_files_in_folder
from utils.parser import extract_text_from_file


def split_text_into_chunks(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """長文テキストを、一定の文字数（チャンク）に分割する関数。

    - 改行1つ（docx・pdf の段落区切り）でも区切れるよう、行単位で積み上げる
    - chunk_size を超える長い行は、強制的に分割する
    - 文脈が途切れないよう、直前のチャンクの末尾 overlap 文字を次のチャンクの先頭に重ねる
    """
    if not text:
        return []

    # 行単位に分解し、長すぎる行は chunk_size ごとに切る
    units = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        while len(line) > chunk_size:
            units.append(line[:chunk_size])
            line = line[chunk_size:]
        units.append(line)

    chunks = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) + 1 > chunk_size:
            chunks.append(current)
            # 重なり部分を引き継いで次のチャンクを開始
            current = current[-overlap:] + "\n" + unit if overlap > 0 else unit
        else:
            current = current + "\n" + unit if current else unit

    if current.strip():
        chunks.append(current)

    return chunks


def sync_drive_to_chromadb(folder_id: str = None) -> int:
    """指定した Google Drive フォルダの全ファイルを ChromaDB に同期する関数"""
    print("=== Google Drive データの同期を開始します ===")

    files = list_files_in_folder(folder_id) if folder_id else list_files_in_folder()
    if not files:
        print("同期対象のファイルが見つかりませんでした。")
        return 0

    collection = get_chroma_collection()

    documents = []
    metadatas = []
    ids = []

    temp_dir = Path("temp_drive_files")
    temp_dir.mkdir(exist_ok=True)

    for f in files:
        file_id = f["id"]
        file_name = f["name"]
        mime_type = f["mimeType"]

        print(f"処理中: {file_name}...")
        temp_file_path = temp_dir / file_name

        try:
            content_bytes = download_file(file_id, mime_type=mime_type)
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(content_bytes)

            text = extract_text_from_file(str(temp_file_path))

            if not text or not text.strip():
                print(f"  -> スキップ: {file_name} からテキストを抽出できませんでした。")
            else:
                # テキストを小分け（チャンク分割）する
                chunks = split_text_into_chunks(text, chunk_size=400, overlap=80)

                for idx, chunk in enumerate(chunks):
                    # 各チャンクに固有の ID を割り当てる (例: file_id_chunk_0)
                    chunk_id = f"{file_id}_chunk_{idx}"
                    ids.append(chunk_id)
                    # どの文書の一部かが検索でもわかるよう、先頭にファイル名を付ける
                    documents.append(f"【{file_name}】\n{chunk}")
                    metadatas.append(
                        {
                            "filename": file_name,
                            "file_id": file_id,
                            "mime_type": mime_type,
                            "chunk_index": idx,
                            "path": f"Google Drive / {file_name}",
                        }
                    )
                print(f"  -> 成功: {len(chunks)} チャンクに分割して登録")

        except Exception as e:
            print(f"  -> エラー発生 ({file_name}): {e}")

        finally:
            if temp_file_path.exists():
                os.remove(temp_file_path)

    try:
        temp_dir.rmdir()
    except OSError:
        pass

    # ChromaDB への一括登録/更新 (upsert)
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        print(f"\n=== 同期完了: 合計 {len(files)} ファイルから {len(ids)} チャンクを ChromaDB に保存・更新しました ===")
        return len(ids)
    else:
        print("\n=== 保存対象の有効なテキストデータがありませんでした ===")
        return 0


if __name__ == "__main__":
    sync_drive_to_chromadb()
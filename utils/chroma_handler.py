"""ChromaDB の初期化・文書登録・ベクター検索を行うモジュール"""

import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from utils.parser import load_all_documents

# プロジェクトルート直下の .env を読み込む（OPENAI_API_KEY を使うため）
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# コレクション（DBのテーブルのようなもの）の名前
# 埋め込みモデルを変えるとベクトルの形式が変わるため、旧データと混ざらないよう名前を変えている
COLLECTION_NAME = "tech0_search_db_v2"

# 日本語に対応した多言語の埋め込みモデル（OpenAI）
EMBEDDING_MODEL = "text-embedding-3-small"


def get_chroma_client():
    """ChromaDB の PersistentClient インスタンスを取得する"""
    return chromadb.PersistentClient(path="./chroma_db")


def get_embedding_function():
    """テキストをベクトルに変換する埋め込み関数を返す"""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            ".env ファイルに OPENAI_API_KEY が設定されていません。確認してください。"
        )
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key_env_var="OPENAI_API_KEY",
        model_name=EMBEDDING_MODEL,
    )


def get_chroma_collection():
    """ChromaDB のクライアントとコレクションを取得する"""
    client = get_chroma_client()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=get_embedding_function()
    )
    return collection


def sync_dummy_data_to_chroma(folder_path: str = "dummy_data") -> int:
    """dummy_data フォルダ内の全文書を、チャンクに分割して ChromaDB に登録/更新する

    Returns:
        int: 登録したチャンクの数
    """
    # sync_pipeline は chroma_handler を import しているため、
    # 循環 import にならないよう関数の中で import する
    from utils.sync_pipeline import split_text_into_chunks

    docs = load_all_documents(folder_path)
    if not docs:
        return 0

    collection = get_chroma_collection()

    documents = []
    metadatas = []
    ids = []

    for doc in docs:
        chunks = split_text_into_chunks(doc["content"], chunk_size=400, overlap=80)
        for idx, chunk in enumerate(chunks):
            ids.append(f"{doc['id']}_chunk_{idx}")
            # Drive 同期と同じく、先頭にファイル名を付ける
            documents.append(f"【{doc['filename']}】\n{chunk}")
            metadatas.append(
                {
                    "filename": doc["filename"],
                    "path": doc["path"],
                    "chunk_index": idx,
                }
            )

    if not ids:
        return 0

    # upsert (すでに存在するIDは更新、なければ新規追加)
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(ids)


def search_similar_documents(query: str, top_k: int = 5) -> list[dict]:
    """検索クエリに対して類似度の高い文書（チャンク）を上位 top_k 件返す"""
    if not query.strip():
        return []

    collection = get_chroma_collection()

    results = collection.query(query_texts=[query], n_results=top_k)

    search_results = []
    if results and results["documents"]:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = (
            results["distances"][0]
            if "distances" in results and results["distances"]
            else []
        )

        for i in range(len(docs)):
            search_results.append(
                {
                    "filename": metas[i]["filename"],
                    "content": docs[i],
                    "score": distances[i] if i < len(distances) else None,
                }
            )

    return search_results


def reset_chroma_collection():
    """ChromaDB のコレクションをリセット（全削除）する"""
    client = get_chroma_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"Collection reset notice: {e}")
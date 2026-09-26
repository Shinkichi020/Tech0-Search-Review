"""ChromaDB の初期化・文書登録・ベクター検索を行うモジュール"""

import chromadb
from chromadb.utils import embedding_functions
from utils.parser import load_all_documents

# コレクション（DBのテーブルのようなもの）の名前
COLLECTION_NAME = "tech0_search_db"

def get_chroma_collection():
    """ChromaDB のクライアントとコレクションを取得する"""
    # 永続化（ローカルディスクに保存）する設定
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # デフォルトの埋め込み関数（テキストをベクトル変換する処理）
    emb_fn = embedding_functions.DefaultEmbeddingFunction()
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn
    )
    return collection


def sync_dummy_data_to_chroma(folder_path: str = "dummy_data") -> int:
    """dummy_data フォルダ内の全文書を ChromaDB に登録/更新する"""
    docs = load_all_documents(folder_path)
    if not docs:
        return 0

    collection = get_chroma_collection()

    documents = []
    metadatas = []
    ids = []

    for doc in docs:
        ids.append(doc["id"])
        documents.append(doc["content"])
        metadatas.append({"filename": doc["filename"], "path": doc["path"]})

    # upsert (すでに存在するIDは更新、なければ新規追加)
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return len(ids)


def search_similar_documents(query: str, top_k: int = 3) -> list[dict]:
    """検索クエリに対して類似度の高い文書を上位 top_k 件返す"""
    if not query.strip():
        return []

    collection = get_chroma_collection()
    
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )

    search_results = []
    if results and results["documents"]:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else []

        for i in range(len(docs)):
            search_results.append({
                "filename": metas[i]["filename"],
                "content": docs[i],
                "score": distances[i] if i < len(distances) else None
            })

    return search_results
from utils.chroma_handler import sync_dummy_data_to_chroma, search_similar_documents

print("=== 1. dummy_data を ChromaDB へ同期中... ===")
count = sync_dummy_data_to_chroma("dummy_data")
print(f"登録・更新完了: {count} 件の文書\n")

print("=== 2. 検索テスト実行 ===")
test_query = "セキュリティ リモートワーク パスワード"
print(f"検索クエリ: 「{test_query}」\n")

results = search_similar_documents(test_query, top_k=2)

for i, res in enumerate(results):
    print(f"【結果 {i+1}】 ファイル名: {res['filename']}")
    print(f"本文抜粋:\n{res['content'][:120]}...")
    print("-" * 50)
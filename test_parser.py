from utils.parser import load_all_documents

docs = load_all_documents("dummy_data")
print(f"読み込み成功ファイル数: {len(docs)} 件\n")

for i, doc in enumerate(docs[:3]):  # 最初の3件だけ表示
    print(f"--- [{i+1}] {doc['filename']} ---")
    print(doc['content'][:150])  # 先頭150文字を表示
    print("\n")
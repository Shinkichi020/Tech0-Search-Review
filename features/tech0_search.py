"""Tech0 Search — 担当: たくちゃん"""

import streamlit as st
from utils.chroma_handler import search_similar_documents, sync_dummy_data_to_chroma

FEATURE_KEY = "search"


def render() -> None:
    """左レールでこの機能が選ばれているときに呼ばれる。"""

    # --- 1. タイトル & ヘッダー ---
    st.markdown("## ◧ Tech0 Search")
    st.caption("Googleドライブ等の社内ドキュメントをベクター検索・セマンティック検索します。")

    # --- 2. セッション状態の初期化 ---
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "last_query" not in st.session_state:
        st.session_state.last_query = ""

    # --- 3. 操作エリア（検索窓 & 今すぐ同期ボタン） ---
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # ※ ウィジェットの key には必ず "search_" を付与
        query = st.text_input(
            "何をお探しですか？",
            key="search_input_query",
            placeholder="例: セキュリティ リモートワーク パスワード"
        )

    with col2:
        st.write("")  # レイアウト高さ調整用の余白
        if st.button("今すぐ同期", key="search_btn_sync", use_container_width=True):
            with st.spinner("dummy_data を同期中..."):
                count = sync_dummy_data_to_chroma("dummy_data")
            st.toast(f"同期完了: {count} 件の文書を更新しました！", icon="✅")

    # --- 4. 検索処理の実行 ---
    if query and query != st.session_state.last_query:
        st.session_state.last_query = query
        with st.spinner("社内ドキュメントを検索中..."):
            st.session_state.search_results = search_similar_documents(query, top_k=3)

    # --- 5. 検索結果の描画 ---
    if st.session_state.search_results:
        st.markdown("---")
        st.markdown(f"### 🔍 検索結果: 「{st.session_state.last_query}」")

        for i, res in enumerate(st.session_state.search_results):
            with st.container(border=True):
                col_title, col_score = st.columns([4, 1])
                with col_title:
                    st.markdown(f"**📄 {i+1}. {res['filename']}**")
                with col_score:
                    if res["score"] is not None:
                        st.caption(f"距離スコア: {res['score']:.4f}")

                # 本文抜粋を表示（初期表示はアコーディオン形式で折りたたみ）
                with st.expander("本文テキストを表示・確認"):
                    st.text(res["content"])

    elif query:
        st.info("該当するドキュメントが見つかりませんでした。")
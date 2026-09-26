"""Tech0 Search — 担当: たくちゃん用(スケルトン)

実装するのは `render()` だけ。左レールは shell/feature_switcher.py が担当するので
このファイルからは触らない。
"""

import streamlit as st

# この機能のメタ情報(レールと二重管理にしないため、表示名の変更は
# shell/feature_switcher.py の FEATURES を正とする)
FEATURE_KEY = "search"


def render() -> None:
    """左レールでこの機能が選ばれているときに呼ばれる。"""
    # ---- ここから同僚Aの実装 ----
    st.markdown("### Tech0 Search")
    st.caption("この画面は同僚Aの担当領域です。`features/tech0_search.py` の `render()` を実装してください。")

    with st.container(border=True):
        st.markdown("**実装メモ**")
        st.markdown(
            "- 画面全体の見出し・説明・本文はこの関数の中に書く\n"
            "- ウィジェットの `key` は `search_` で始める(他機能との衝突回避)\n"
            "- 状態は `st.session_state` に保持する(毎回リセットされるため)\n"
            "- スタイルは自分のブロック内に `st.html('<style>…</style>')` で閉じて書く"
        )

    # 実装例(消してOK)
    with st.container(border=True):
        st.text_input("検索キーワード", key="search_q_example", placeholder="例: 契約書")
        st.caption("入力欄・結果一覧・ページャなどはここに実装します。")
    # ---- ここまで同僚Aの実装 ----

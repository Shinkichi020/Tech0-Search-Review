"""Tech0 Review — 担当: おのちゃん用(スケルトン)

実装するのは `render()` だけ。左レールは shell/feature_switcher.py が担当するので
このファイルからは触らない。
"""

import streamlit as st

FEATURE_KEY = "review"


def render() -> None:
    """左レールでこの機能が選ばれているときに呼ばれる。"""
    # ---- ここから同僚Bの実装 ----
    st.markdown("### Tech0 Review")
    st.caption("この画面は同僚Bの担当領域です。`features/tech0_review.py` の `render()` を実装してください。")

    with st.container(border=True):
        st.markdown("**実装メモ**")
        st.markdown(
            "- ファイルアップロードや項目選択はこの関数の中に書く\n"
            "- ウィジェットの `key` は `review_` で始める(他機能との衝突回避)\n"
            "- レビュー結果の表示レイアウトは自由。ただし列分割の中で描画される点に注意"
        )

    # 実装例(消してOK)
    with st.container(border=True):
        st.file_uploader("対象ファイル", type=["pptx", "pdf", "docx", "md"], key="review_file_example")
        st.caption("アップロード UI と結果表示はここに実装します。")
    # ---- ここまで同僚Bの実装 ----

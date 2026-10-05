"""Tech0 Search — 担当: たくちゃん (対話文脈を考慮した Query Rewriting 機能付き)"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st

from utils.chroma_handler import search_similar_documents, reset_chroma_collection
from utils.sync_pipeline import sync_drive_to_chromadb

FEATURE_KEY = "search"


def render() -> None:
    """左レールでこの機能が選ばれているときに呼ばれる。"""

    # プロジェクトルート直下の .env を指定して読み込む
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("OPENAI_API_KEY")

    # --- 1. タイトル & ヘッダー ---
    st.markdown("## ◧ Tech0 Search Chat")
    st.caption(
        "Googleドライブ等の社内ドキュメントを参照しながらAIと対話できます。"
    )

    if not api_key:
        st.error(
            ".env ファイルに OPENAI_API_KEY が設定されていません。確認してください。"
        )
        return

    client = OpenAI(api_key=api_key)

    # --- 2. セッション状態（チャット履歴）の初期化 ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- 3. 同期＆リセットエリア ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.caption(
            "Google Drive の最新ファイルを取得し、ベクトルデータベースを再構築します。"
        )
    with col2:
        if st.button(
            "🔄 DBリセット & 再同期", key="search_btn_sync", use_container_width=True, type="primary"
        ):
            with st.spinner("DBをリセットして Drive からデータを同期中..."):
                try:
                    reset_chroma_collection()
                    count = sync_drive_to_chromadb()
                    st.session_state.messages = []
                    st.toast(
                        f"同期完了: {count} チャンクの文書を更新しました！",
                        icon="✅",
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"同期中にエラーが発生しました: {e}")

    st.divider()

    # --- 4. チャット履歴の描画 ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📚 参照したドキュメント"):
                    for idx, doc in enumerate(msg["sources"], 1):
                        st.markdown(f"**{idx}. {doc['filename']}**")
                        st.caption(doc["content"][:200] + "...")

    # --- 5. チャット入力・AI処理 ---
    if prompt := st.chat_input("質問を入力してください（例: テレワークの手当はいくら？ / 対象外になる人は？）"):
        # ユーザーの発言を表示＆保存
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AIの回答領域を表示
        with st.chat_message("assistant"):
            with st.spinner("思考中 & 社内ドキュメントを検索中..."):
                
                # --- Step 1: 会話履歴を踏まえた検索クエリの書き換え (Query Rewriting) ---
                search_query = prompt
                if len(st.session_state.messages) > 1:
                    # 直近の会話履歴からコンテキストを抽出
                    history_summary = ""
                    for m in st.session_state.messages[-5:-1]:
                        history_summary += f"{m['role']}: {m['content']}\n"
                    
                    rewrite_prompt = (
                        "あなたは社内検索システムのクエリ生成アシスタントです。\n"
                        "以下の会話履歴を踏まえて、ユーザーの最新の質問に対する検索精度を最大化するための単一の独立した検索クエリを作成してください。\n"
                        "主語や代名詞（それ、また、など）を補完し、社内文書検索に最も適したキーワードを含めてください。検索クエリの文字列のみを出力してください。\n\n"
                        f"【会話履歴】\n{history_summary}\n"
                        f"【最新の質問】\n{prompt}"
                    )
                    try:
                        rewrite_res = client.chat.completions.create(
                            model="gpt-4.1-mini",
                            messages=[{"role": "user", "content": rewrite_prompt}],
                            temperature=0.0,
                        )
                        search_query = rewrite_res.choices[0].message.content.strip()
                    except Exception:
                        search_query = prompt

                # --- Step 2: 書き換えたクエリで ChromaDB 検索 ---
                docs = search_similar_documents(search_query, top_k=5)

                # コンテキストの組み立て
                context_text = ""
                if docs:
                    for i, doc in enumerate(docs, 1):
                        context_text += f"【参照ドキュメント {i}: {doc['filename']}】\n{doc['content']}\n\n"
                else:
                    context_text = "該当するドキュメントは見つかりませんでした。"

                # システムプロンプトの設定
                system_prompt = (
                    "あなたは社内文書の検索・回答をアシストするAIアシスタントです。\n"
                    "以下の【参照ドキュメント】の情報のみに基づいて、ユーザーの質問に分かりやすく根拠を示しながら回答してください。\n"
                    "参照ドキュメントに記載がない情報については『該当する情報が見つかりませんでした』と回答してください。\n\n"
                    f"【参照ドキュメント】\n{context_text}"
                )

                # OpenAI API へ送信するメッセージ構築
                api_messages = [{"role": "system", "content": system_prompt}]
                for msg in st.session_state.messages[-10:]:
                    api_messages.append({"role": msg["role"], "content": msg["content"]})

                try:
                    response = client.chat.completions.create(
                        model="gpt-4.1-mini",
                        messages=api_messages,
                        temperature=0.2,
                    )
                    answer = response.choices[0].message.content

                    # 回答の表示
                    st.markdown(answer)

                    # 参照ドキュメントの表示
                    if docs:
                        with st.expander("📚 参照したドキュメント"):
                            for idx, doc in enumerate(docs, 1):
                                st.markdown(f"**{idx}. {doc['filename']}**")
                                st.caption(doc["content"][:200] + "...")

                    # 履歴に保存
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                            "sources": docs if docs else [],
                        }
                    )

                except Exception as e:
                    st.error(f"OpenAI API 呼び出しエラー: {e}")
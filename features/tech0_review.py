"""Tech0 Review — 担当: おのちゃん

画面は 2 タブ:
  レビュワー: ログイン → 工程を選ぶ → レビュー項目 Excel を登録
  レビューイ: 工程を選ぶ → 文書を提出 → AI が評価

このファイルは画面だけを担当し、処理は features/review/ にまとめる。
import した時点では DB にも OpenAI にも接続しない(test_switcher.py が import するため)。
"""

import html
import io
import sqlite3

import streamlit as st

from features.review import db
from features.review.auth import verify_login
from features.review.checklist_loader import ChecklistError, import_checklist, parse_excel
from features.review.config import MAX_DOC_CHARS, PHASES
from features.review.exporter import build_result_xlsx, result_file_name
from features.review.loader import LoaderError, fetch_google_doc, load_uploaded

FEATURE_KEY = "review"

_DOC_TYPES = ["docx", "xlsx", "pptx", "pdf", "txt", "csv"]

# 画面用 CSS。他機能に漏れないよう .review- で始まるクラスだけに当てる。
# 色は shell が用意した CSS 変数(--panel / --line / --ink / --muted / --blue)を使う。
_CSS = """
<style>
  .review-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 12px; }
  .review-chip {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--ink); background: var(--panel);
    border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px;
  }
  .review-chip b { font-weight: 600; color: var(--blue); }
  .review-chip.is-empty { color: var(--muted); }
  .review-chip.is-empty b { font-weight: 400; color: var(--muted); }
  .review-user { font-size: 13px; color: var(--muted); margin: 6px 0 0; }
  .review-user b { color: var(--ink); margin-left: 4px; }
  /* 入力欄の背景が下地(--canvas)と同色で見えにくいので、各タブの中身を白いパネルに載せる。
     「st-key-キー名」は st.container(key=...) に Streamlit が付けるクラス。 */
  [class*="st-key-review_panel_"] { background: var(--panel); }

  /* レビュー結果 */
  .review-badge {
    display: inline-block; min-width: 34px; text-align: center;
    font-size: 11.5px; font-weight: 700; border-radius: 999px; padding: 1px 9px;
  }
  .review-badge.is-ok { background: #E2F4EA; color: #23804F; }
  .review-badge.is-ng { background: #FBE6E3; color: #B93A2E; }
  .review-summary { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 2px 0 8px; font-size: 14px; }
  .review-summary b { font-size: 18px; margin-right: 10px; }
  .review-summary-meta { color: var(--muted); font-size: 12.5px; }
  .review-card {
    background: var(--panel); border: 1px solid var(--line); border-left-width: 4px;
    border-radius: 8px; padding: 10px 14px; margin: 0 0 10px; font-size: 13.5px; color: var(--ink);
  }
  .review-card.is-ok { border-left-color: #23804F; }
  .review-card.is-ng { border-left-color: #B93A2E; }
  .review-card-head { display: flex; align-items: baseline; gap: 8px; }
  .review-card-no { color: var(--muted); font-size: 12px; white-space: nowrap; }
  .review-card-title { font-weight: 700; }
  .review-card-vp { color: var(--muted); font-size: 12.5px; margin-top: 4px; }
  .review-card-label { color: var(--muted); font-size: 11.5px; font-weight: 700; margin-top: 8px; }
  .review-card-quote { background: #FAFAFA; border-left: 3px solid var(--line); padding: 4px 10px; margin-top: 2px; }
  .review-card-text { margin-top: 2px; }
  .review-card-note {
    display: inline-block; margin-top: 6px; font-size: 12px; color: #8A6200;
    background: #FFF6DC; border-radius: 4px; padding: 1px 8px;
  }
</style>
"""


def _init_state() -> None:
    """render() は再実行のたびに呼ばれるので、初期化は setdefault で 1 回だけ。"""
    st.session_state.setdefault("review_reviewer", None)   # ログイン中のレビュワー(パスワードは持たない)
    st.session_state.setdefault("review_text", "")         # 提出文書から抽出したテキスト
    st.session_state.setdefault("review_file_sig", None)   # 提出ファイルの「名前+サイズ」(再抽出の抑制用)
    st.session_state.setdefault("review_file_name", None)  # 提出ファイルの名前(結果と Excel に載せる)
    st.session_state.setdefault("review_load_error", None) # 抽出に失敗したときのメッセージ
    st.session_state.setdefault("review_result", None)     # 評価結果の JSON
    st.session_state.setdefault("review_upload_ver", 0)    # 登録後にアップローダーを空に戻すための番号
    st.session_state.setdefault("review_flash", None)      # 再実行をまたいで出す完了メッセージ


def render() -> None:
    """左レールでこの機能が選ばれているときに呼ばれる。"""
    st.html(_CSS)
    _init_state()

    st.markdown("## ◫ Tech0 Review")
    st.caption("SI 工程ごとのレビュー項目に照らして、提出された文書を AI が項目ごとに判定します。")

    tab_reviewer, tab_reviewee = st.tabs(["レビュワー", "レビューイ"])
    with tab_reviewer, st.container(border=True, key="review_panel_reviewer"):
        _render_reviewer_tab()
    with tab_reviewee, st.container(border=True, key="review_panel_reviewee"):
        _render_reviewee_tab()


# ---------------------------------------------------------------- 共通部品

def _load_counts() -> dict[str, int] | None:
    """工程ごとの登録件数。DB を開けなければエラーを出して None。"""
    try:
        return db.count_items_by_phase()
    except sqlite3.Error as e:
        st.error(f"レビュー項目の DB を開けませんでした（{e}）。")
        return None


def _render_phase_counts(counts: dict[str, int]) -> None:
    chips = "".join(
        f'<span class="review-chip{"" if counts.get(p) else " is-empty"}">{p}<b>{counts.get(p, 0)}</b></span>'
        for p in PHASES
    )
    st.markdown(f'<div class="review-chips">{chips}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- レビュワー

def _render_reviewer_tab() -> None:
    reviewer = st.session_state.review_reviewer
    if reviewer is None:
        _render_login()
        return

    col_user, col_logout = st.columns([5, 1])
    with col_user:
        st.markdown(
            f'<p class="review-user">ログイン中：<b>{reviewer["display_name"]}</b></p>',
            unsafe_allow_html=True,
        )
    with col_logout:
        if st.button("ログアウト", key="review_logout", use_container_width=True):
            st.session_state.review_reviewer = None
            st.rerun()

    if st.session_state.review_flash:
        st.success(st.session_state.review_flash)
        st.session_state.review_flash = None

    counts = _load_counts()
    if counts is None:
        return
    st.markdown("**工程ごとの登録件数**")
    _render_phase_counts(counts)

    phase = st.selectbox("登録する工程", PHASES, key="review_reg_phase")
    existing = counts.get(phase, 0)
    if existing:
        with st.expander(f"「{phase}」に登録済みの項目（{existing} 件）を見る"):
            _show_items_table(db.get_review_items(phase))

    ver = st.session_state.review_upload_ver
    uploaded = st.file_uploader(
        "レビュー項目 Excel（.xlsx）",
        type=["xlsx"],
        key=f"review_checklist_file_{ver}",
        help="1 枚目のシートに「No」「チェック項目（またはレビュー項目）」「観点」の見出しがある一覧表",
    )
    if uploaded is None:
        return

    try:
        items, skipped = parse_excel(io.BytesIO(uploaded.getvalue()))
    except ChecklistError as e:
        st.error(str(e))
        return

    st.markdown(f"**プレビュー**：{len(items)} 件")
    if skipped:
        st.warning("次の行は登録しません。\n\n" + "\n".join(f"- {s}" for s in skipped))
    _show_items_table(items)

    confirmed = True
    if existing:
        st.warning(f"「{phase}」には登録済みの項目が {existing} 件あります。登録すると、すべて新しい内容に置き換わります。")
        confirmed = st.checkbox("置き換えてよいことを確認しました", key=f"review_reg_confirm_{ver}_{phase}")

    if st.button(
        f"「{phase}」に {len(items)} 件を登録",
        key="review_reg_submit",
        type="primary",
        disabled=not confirmed,
    ):
        try:
            n = import_checklist(phase, items, reviewer["username"])
        except (sqlite3.Error, ValueError) as e:
            st.error(f"登録できませんでした（{e}）。")
            return
        st.session_state.review_flash = f"「{phase}」に {n} 件のレビュー項目を登録しました。"
        st.session_state.review_upload_ver += 1  # key が変わるのでアップローダーが空に戻る
        st.rerun()


def _render_login() -> None:
    st.caption("レビュー項目の登録には、レビュワーのログインが必要です。アカウントは管理者が発行します。")
    col_form, _ = st.columns([2, 3])
    with col_form:
        with st.form("review_login_form", border=False):
            username = st.text_input("ユーザー名", key="review_login_username")
            password = st.text_input("パスワード", type="password", key="review_login_password")
            submitted = st.form_submit_button("ログイン", type="primary")

    if not submitted:
        return
    if not username or not password:
        st.error("ユーザー名とパスワードを入力してください。")
        return
    try:
        reviewer = verify_login(username, password)
    except sqlite3.Error as e:
        st.error(f"レビュワーの DB を開けませんでした（{e}）。")
        return
    if reviewer is None:
        st.error("ユーザー名またはパスワードが違います。")
        return
    st.session_state.review_reviewer = reviewer
    st.rerun()


def _show_items_table(items: list[dict]) -> None:
    st.dataframe(
        [{"No": it["item_no"], "チェック項目": it["check_item"], "観点": it["viewpoint"]} for it in items],
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------- レビューイ

_SOURCE_FILE = "ファイルをアップロード"
_SOURCE_URL = "Google ドキュメントの URL"

def _render_reviewee_tab() -> None:
    counts = _load_counts()
    if counts is None:
        return

    phase = st.selectbox("レビューを受ける工程", PHASES, key="review_phase")
    n = counts.get(phase, 0)
    if n:
        st.caption(f"この工程のレビュー項目：{n} 件")
    else:
        st.warning("この工程にはまだレビュー項目が登録されていません。レビュワーに登録を依頼してください。")

    source = st.radio(
        "提出方法",
        [_SOURCE_FILE, _SOURCE_URL],
        horizontal=True,
        key="review_source",
        on_change=_reset_document,  # 提出方法を切り替えたら、読み込んだ文書と結果を消す
    )
    if source == _SOURCE_FILE:
        uploaded = st.file_uploader(
            "レビューを受ける文書",
            type=_DOC_TYPES,
            key="review_doc_file",
            help="Word・Excel・PowerPoint・PDF・テキスト・CSV に対応しています。",
        )
        _sync_document(uploaded)
    else:
        _render_url_input()

    if st.session_state.review_load_error:
        st.error(st.session_state.review_load_error)
        return
    text = st.session_state.review_text
    if not text:
        return

    st.markdown(f"**抽出したテキスト**：{len(text):,} 字（{st.session_state.review_file_name}）")
    with st.container(height=280, border=True):
        st.text(text)
    if len(text) > MAX_DOC_CHARS:
        st.warning(f"文書が長いため（{len(text):,} 字）、先頭 {MAX_DOC_CHARS:,} 字までを評価します。")

    if st.button(
        f"AI でレビューする（{n} 項目）" if n else "AI でレビューする",
        key="review_run",
        type="primary",
        disabled=n == 0,  # レビュー項目が 0 件の工程では実行できない
    ):
        st.info("AI による評価は次のステップで実装します。")

    result = st.session_state.review_result
    if result and result["phase"] == phase:  # 工程を切り替えたら、別工程の結果は出さない
        _render_result(result)


def _reset_document() -> None:
    st.session_state.review_file_sig = None
    st.session_state.review_text = ""
    st.session_state.review_file_name = None
    st.session_state.review_load_error = None
    st.session_state.review_result = None


def _sync_document(uploaded) -> None:
    """アップロードが変わったときだけテキストを抽出し直す。

    Streamlit はボタンを押すたびに全体を再実行するので、毎回抽出すると遅い。
    「名前+サイズ」を review_file_sig に覚えておき、変わったときだけ読み直す。
    文書が変わったら、前の文書の評価結果は消す。
    """
    sig = (uploaded.name, uploaded.size) if uploaded is not None else None
    if sig == st.session_state.review_file_sig:
        return
    _reset_document()
    st.session_state.review_file_sig = sig
    if uploaded is None:
        return
    try:
        with st.spinner("文書を読み込んでいます…"):
            st.session_state.review_text = load_uploaded(uploaded)
        st.session_state.review_file_name = uploaded.name
    except LoaderError as e:
        st.session_state.review_load_error = str(e)


def _render_url_input() -> None:
    col_url, col_btn = st.columns([5, 1], vertical_alignment="bottom")
    with col_url:
        url = st.text_input(
            "Google ドキュメント／スプレッドシート／スライドの URL",
            key="review_doc_url",
            placeholder="https://docs.google.com/document/d/…",
        )
    with col_btn:
        clicked = st.button("取り込む", key="review_fetch", use_container_width=True, disabled=not url.strip())
    if not clicked:
        return
    _reset_document()
    try:
        with st.spinner("Google ドライブから文書を取り込んでいます…"):
            name, text = fetch_google_doc(url)
    except LoaderError as e:
        st.session_state.review_load_error = str(e)
        return
    st.session_state.review_file_sig = ("url", url.strip())
    st.session_state.review_text = text
    st.session_state.review_file_name = name


# ---------------------------------------------------------------- 結果の表示

def _render_result(result: dict) -> None:
    summary = result["summary"]
    st.markdown("#### レビュー結果")
    st.markdown(
        '<div class="review-summary">'
        f'<span class="review-badge is-ok">OK</span><b>{summary["ok"]}</b>件'
        f'<span class="review-badge is-ng">NG</span><b>{summary["ng"]}</b>件'
        f'<span class="review-summary-meta">{_esc(result["phase"])}／{_esc(result.get("file_name") or "")}</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    if result.get("truncated"):
        st.warning(f"文書が長いため（{result['original_chars']:,} 字）、先頭 {MAX_DOC_CHARS:,} 字までを評価しました。")
    st.caption("AI による一次レビューの結果です。最終判断は品質保証部の品質チェック会議で行ってください。")

    col_filter, col_dl = st.columns([3, 2], vertical_alignment="center")
    with col_filter:
        shown = st.segmented_control(
            "表示する項目",
            ["すべて", "NG のみ", "OK のみ"],
            default="すべて",
            key="review_result_filter",
            label_visibility="collapsed",
        )
    with col_dl:
        st.download_button(
            "結果を Excel でダウンロード",
            data=build_result_xlsx(result),
            file_name=result_file_name(result),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="review_download",
            use_container_width=True,
        )

    wanted = {"NG のみ": {"NG"}, "OK のみ": {"OK"}}.get(shown or "すべて", {"OK", "NG"})
    cards = [_card_html(r) for r in result["results"] if r["status"] in wanted]
    if cards:
        st.markdown("".join(cards), unsafe_allow_html=True)
    else:
        st.caption("該当する項目はありません。")


def _card_html(r: dict) -> str:
    """結果 1 件分のカード。本文や AI の回答はそのまま HTML に入れず、必ずエスケープする。"""
    status_class = "is-ok" if r["status"] == "OK" else "is-ng"
    parts = [
        f'<div class="review-card {status_class}">',
        '<div class="review-card-head">'
        f'<span class="review-badge {status_class}">{r["status"]}</span>'
        f'<span class="review-card-no">No.{r["item_no"]}</span>'
        f'<span class="review-card-title">{_esc(r["check_item"])}</span></div>',
    ]
    if r.get("viewpoint"):
        parts.append(f'<div class="review-card-vp">観点：{_esc(r["viewpoint"])}</div>')
    parts.append(
        '<div class="review-card-label">根拠（本文からの抜粋）</div>'
        f'<div class="review-card-quote">{_esc(r["evidence"])}</div>'
    )
    if not r.get("evidence_found", True):
        parts.append('<div class="review-card-note">根拠を本文で確認できませんでした</div>')
    if r["status"] == "NG" and r.get("suggestion"):
        parts.append(
            '<div class="review-card-label">改善提案</div>'
            f'<div class="review-card-text">{_esc(r["suggestion"])}</div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _esc(text) -> str:
    """HTML として解釈されないようにエスケープし、改行は <br> にする。"""
    return html.escape(str(text)).replace("\n", "<br>")

"""Tech0 Review — 担当: おのちゃん

画面は 2 タブ:
  レビュワー: ログイン → 工程を選ぶ → レビュー項目 Excel を登録
  レビューイ: 工程を選ぶ → 文書を提出 → AI が評価(提出と評価は今後実装)

このファイルは画面だけを担当し、処理は features/review/ にまとめる。
import した時点では DB にも OpenAI にも接続しない(test_switcher.py が import するため)。
"""

import io
import sqlite3

import streamlit as st

from features.review import db
from features.review.auth import verify_login
from features.review.checklist_loader import ChecklistError, import_checklist, parse_excel
from features.review.config import PHASES

FEATURE_KEY = "review"

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
</style>
"""


def _init_state() -> None:
    """render() は再実行のたびに呼ばれるので、初期化は setdefault で 1 回だけ。"""
    st.session_state.setdefault("review_reviewer", None)   # ログイン中のレビュワー(パスワードは持たない)
    st.session_state.setdefault("review_text", "")         # 提出文書から抽出したテキスト
    st.session_state.setdefault("review_file_sig", None)   # 提出ファイルの「名前+サイズ」(再抽出の抑制用)
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

    st.info("文書の提出と AI による評価は準備中です。")

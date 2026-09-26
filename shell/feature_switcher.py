"""左レールの機能切り替え(★本人担当)。

責務はこのファイルだけ:
  - 機能の一覧(FEATURES)を定義する
  - 左レールに切り替えボタンを描画する
  - 選択中の機能キーを session_state と URL に保持する
  - レール関連の CSS を注入する

コンテンツ(検索/レビューの画面本体)には一切関与しない。
"""

import os

import streamlit as st

# ---------------------------------------------------------------------------
# 機能の定義 — 機能を増やすときはここに1行足すだけ
#   key   : URL (?feature=...) と session_state['feature'] に入る識別子
#   label : 左レールのボタン表示名
#   desc  : ボタン直下に出す一行説明
#   icon  : グリフ(1〜2文字)。絵文字ではなく幾何記号で揃える
# ---------------------------------------------------------------------------
FEATURES: list[dict] = [
    {"key": "search", "label": "Tech0 Search", "desc": "社内データを横断検索", "icon": "◧"},
    {"key": "review", "label": "Tech0 Review", "desc": "資料レビューを表示", "icon": "◫"},
]

DEFAULT_FEATURE = FEATURES[0]["key"]

# 接続中アカウントの表示。SSO 導入後は st.user などから差し替える。
ACCOUNT_EMAIL = os.getenv("TECH0_USER_EMAIL", "jsrb106@example.co.jp")
ACCOUNT_BADGE = os.getenv("TECH0_USER_BADGE", "SSO 認証済み")

_RAIL_CSS = """
<style>
  /* --- 共通の下地(同僚が上書きしてよい) --- */
  :root {
    --canvas: #F5F5F5; --panel: #FFFFFF; --line: #E6E6E6;
    --ink: #1E1E1E; --muted: #7A7A7A; --blue: #0D99FF;
  }
  html, body, [class*="css"] {
    font-family: Inter, "Hiragino Kaku Gothic ProN", "Noto Sans JP",
                 -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .stApp { background: var(--canvas); }
  .block-container { padding: 1.1rem 1.6rem 2rem; max-width: 1560px; }

  /* ヘッダーは「消す」のではなく透明化する。
     サイドバーを畳んだ後に開き直すボタン(stExpandSidebarButton)はヘッダー内に
     描画されるため、display:none にすると畳んだサイドバーを復帰できなくなる。 */
  header[data-testid="stHeader"] {
    background: transparent;
    box-shadow: none;
  }
  /* 邪魔なもの(Deploy ボタン等)だけを隠し、開閉ボタンは残す */
  header[data-testid="stHeader"] [data-testid="stToolbar"] { visibility: hidden; }
  header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none; }
  [data-testid="stExpandSidebarButton"] { visibility: visible !important; }

  /* --- 左レール(ここから下が担当範囲) --- */
  [data-testid="stSidebar"] {
    background: var(--panel);
    border-right: 1px solid var(--line);
    min-width: 216px;
  }
  [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1rem; }
  .rail-label {
    font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase;
    color: var(--muted); margin: 0 0 8px 3px;
  }
  /* レール内のボタンを「選択中/未選択」で塗り分ける */
  [data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start; text-align: left; height: 42px;
    padding: 0 12px; border-radius: 6px; font-weight: 600;
  }
  [data-testid="stSidebar"] .stButton > button p { font-size: 13.5px; }
  [data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: #FFFFFF; border: 1px solid var(--line); color: #3D3D3D;
  }
  [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    border-color: #C9E7FF; color: #0B7FCF; background: #F7FCFF;
  }
  [data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #EAF6FF; border: 1px solid #9AD4FF; color: #0B7FCF;
  }
  .rail-desc { font-size: 11px; color: var(--muted); margin: -4px 0 12px 4px; }
  .rail-acct { margin-top: 24px; padding-top: 14px; border-top: 1px solid var(--line); }
  .rail-mail { font-size: 12px; color: var(--ink); margin: 4px 0 8px 3px; }
  .rail-badge {
    display: inline-block; font-size: 10.5px; color: var(--blue); background: #EAF6FF;
    border: 1px solid #CDE9FF; border-radius: 999px; padding: 2px 9px;
  }
</style>
"""


def inject_rail_style() -> None:
    """左レールと共通の下地の CSS を注入する(1回だけ呼ぶ)。"""
    st.html(_RAIL_CSS)


def current_feature() -> str:
    """選択中の機能キー。URL → session_state → 既定値 の順で解決する。

    URL に不正な値が入っていても既定値へ落とすので、共有リンクが壊れても起動する。
    """
    valid = {f["key"] for f in FEATURES}
    key = st.session_state.get("feature") or st.query_params.get("feature") or DEFAULT_FEATURE
    return key if key in valid else DEFAULT_FEATURE


def set_feature(key: str) -> None:
    """機能を切り替え、URL に反映する(切り替え状態をリンクで共有できる)。"""
    st.session_state.feature = key
    st.query_params["feature"] = key


def render_sidebar() -> str:
    """左レールを描画し、選択中の機能キーを返す。"""
    active = current_feature()
    st.session_state.feature = active  # 初回起動でも state を確定させておく

    with st.sidebar:
        st.markdown('<p class="rail-label">機能</p>', unsafe_allow_html=True)
        for f in FEATURES:
            is_active = f["key"] == active
            if st.button(
                f"{f['icon']}  {f['label']}",
                key=f"rail_{f['key']}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
                help=f["desc"],
            ):
                set_feature(f["key"])
                st.rerun()
            st.markdown(f'<div class="rail-desc">{f["desc"]}</div>', unsafe_allow_html=True)

        st.markdown(
            f'<div class="rail-acct">'
            f'<p class="rail-label">接続中</p>'
            f'<div class="rail-mail">{ACCOUNT_EMAIL}</div>'
            f'<span class="rail-badge">{ACCOUNT_BADGE}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
    return active

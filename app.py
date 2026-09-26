"""Tech0 シェル(最小構成) — 左レールの機能切り替えだけを担当する。

    app.py
      ├─ shell/feature_switcher.py   ★ 本人担当(左レールの機能切り替えのみ)
      ├─ shell/registry.py            機能キー → 同僚のモジュールを解決
      └─ features/tech0_*.py          たくちゃん・おのちゃんの担当領域(render() を実装する)

たくちゃん・おのちゃんのファイルが未実装/未配置でもこのアプリは起動します(プレースホルダを表示)。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from shell.feature_switcher import inject_rail_style, render_sidebar
from shell.registry import render_feature

st.set_page_config(
    page_title="Tech0",
    page_icon="◧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 左レールのスタイル(本人担当分)。同僚のコンテンツ用CSSは同居させない。
inject_rail_style()

# 左レールを描画し、選択中の機能キーを受け取る
feature_key = render_sidebar()

# ============================================================================
# ↓↓↓ ここから下はたくちゃん・おのちゃんの担当領域 ↓↓↓
# 何も書かなくても registry が features/<機能> の render() を呼びます。
# 同僚の進捗に合わせて、この下に共有ヘッダー等を足しても構いません。
# ============================================================================
render_feature(feature_key)

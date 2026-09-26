"""機能キー → 同僚のモジュールを解決して描画する。

取り決め(INTERFACE.md 参照):
  features/<モジュール> に `render()` を1つ置く。引数なし・戻り値なし。
  まだ実装されていなくてもここでプレースホルダを出すので、
  レール側の開発が止まらない。
"""

import importlib
import traceback

import streamlit as st

# 機能キー → モジュールパス(機能を増やすときは feature_switcher.py とここに追記)
MODULES: dict[str, str] = {
    "search": "features.tech0_search",
    "review": "features.tech0_review",
}

OWNERS: dict[str, str] = {
    "search": "担当: 同僚A",
    "review": "担当: 同僚B",
}


def _placeholder(key: str, message: str, detail: str = "") -> None:
    with st.container(border=True):
        st.markdown(f"#### 実装待ち: `{key}`")
        st.info(message)
        if detail:
            st.code(detail, language="text")


def render_feature(key: str) -> None:
    """選択中機能の render() を呼ぶ。未実装・エラー時はプレースホルダを表示。"""
    modpath = MODULES.get(key)
    if not modpath:
        _placeholder(key, "この機能は registry.MODULES に登録されていません。")
        return

    try:
        module = importlib.import_module(modpath)
    except ModuleNotFoundError:
        _placeholder(
            key,
            f"`{modpath}.py` がまだ配置されていません。"
            f"インターフェースに沿って実装すると、この枠がそのまま差し替わります。"
            f"（{OWNERS.get(key, '')}）",
            detail=f"features/{modpath.split('.')[-1]}.py\n\ndef render() -> None:\n    ...",
        )
        return
    except Exception:
        st.error(f"`{modpath}` の読み込みでエラーが発生しました。")
        st.code(traceback.format_exc(), language="text")
        return

    render = getattr(module, "render", None)
    if not callable(render):
        _placeholder(
            key,
            f"`{modpath}` に `render()` が定義されていません。",
            detail="def render() -> None:\n    ...",
        )
        return

    try:
        render()
    except Exception:
        st.error(f"`{modpath}.render()` の実行中にエラーが発生しました。")
        st.code(traceback.format_exc(), language="text")

"""左レールの機能切り替えの自動検証(AppTest)。

本人担当分(レール)の契約が守られているかを確認する。
  1. 機能が2つ描画される
  2. 既定は Tech0 Search
  3. クリックで切り替わり、URL に反映される
  4. URL から復元できる / 不正値は既定へ落ちる
  5. 同僚ファイルが未実装でもプレースホルダで起動する
  6. レールCSSが注入されている
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from streamlit.testing.v1 import AppTest  # noqa: E402

FAILS = []


def check(label, cond):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        FAILS.append(label)


def run(**qp):
    at = AppTest.from_file("app.py", default_timeout=90)
    for k, v in qp.items():
        at.query_params[k] = v
    at.run()
    return at


def body_text(at):
    parts = []
    for kind in ("markdown", "caption", "info", "warning", "error", "success", "text", "code", "title"):
        for el in getattr(at, kind, []):
            val = getattr(el, "value", None)
            if isinstance(val, str):
                parts.append(val)
    return "\n".join(parts)


# ---------------------------------------------------------------- 1, 2
at = run()
check("起動時に例外がない", not at.exception)
labels = [b.label for b in at.sidebar.button]
print("    rail buttons:", labels)
check("左レールに機能が2つ", len(at.sidebar.button) == 2)
check("Tech0 Search / Tech0 Review が並ぶ",
      any("Tech0 Search" in x for x in labels) and any("Tech0 Review" in x for x in labels))
check("既定は Tech0 Search", at.session_state["feature"] == "search")
kinds = [getattr(b.proto, "type", None) for b in at.sidebar.button]
check("選択中/未選択が視覚的に区別される", len(set(kinds)) == 2)
check("選択中の type が primary", "primary" in [str(k) for k in kinds])
text = body_text(at)
check("レールの説明文が出る", "社内データを横断検索" in text and "資料レビューを表示" in text)
check("接続中アカウントが出る", "接続済" in text or "@" in text)

# ---------------------------------------------------------------- 3
at.sidebar.button[1].click().run()
check("クリック切替で例外がない", not at.exception)
check("機能が review に切り替わる", at.session_state["feature"] == "review")
# AppTest は実行時の query_params 書き込みを公開しないため、
# 読み取り経路(下の復元テスト)＋実装の確認で代替する
check("切り替え時に URL を更新する実装になっている",
      "st.query_params" in Path("shell/feature_switcher.py").read_text(encoding="utf-8"))
kinds2 = [getattr(b.proto, "type", None) for b in at.sidebar.button]
check("選択中が入れ替わる", kinds2[0] != kinds2[1] and str(kinds2[1]) == "primary")
check("Review のプレースホルダ/実装が出る", "Tech0 Review" in body_text(at))

# ---------------------------------------------------------------- 4
at = run(feature="review")
check("URL から Review を復元できる", at.session_state["feature"] == "review")
at = run(feature="zzz-not-a-feature")
check("不正な feature でも落ちず既定へ落ちる",
      not at.exception and at.session_state["feature"] == "search")

# ---------------------------------------------------------------- 5
import features.tech0_review as mod  # noqa: E402

check("同僚モジュールが render() を公開している", callable(getattr(mod, "render", None)))
import re
src = Path("features/tech0_review.py").read_text(encoding="utf-8")
check("同僚ファイルが shell を import していない",
      not re.search(r"^\s*(from|import)\s+shell", src, re.M))
check("同僚ファイルが key 接頭辞ルールを守る例を持つ", "review_" in src)

# ---------------------------------------------------------------- 6
check("レールCSSが注入されている", "rail-label" in open("shell/feature_switcher.py", encoding="utf-8").read())

print("\n=== RESULT:", "ALL PASS" if not FAILS else f"{len(FAILS)} FAILED -> {FAILS}")
sys.exit(0 if not FAILS else 1)

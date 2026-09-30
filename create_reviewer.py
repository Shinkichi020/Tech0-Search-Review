"""レビュワーを登録する管理者用コマンド(画面からは登録できない)。

使い方(リポジトリ直下で):
    python create_reviewer.py <ユーザー名> [--display-name 表示名]

パスワードは画面に表示されない形で 2 回入力する(getpass)。
"""

import argparse
import sqlite3
import sys
from getpass import getpass

from features.review.auth import register_reviewer
from features.review.config import REVIEW_DB_PATH

MIN_PASSWORD_LENGTH = 8


def main() -> int:
    parser = argparse.ArgumentParser(description="Tech0 Review のレビュワーを登録します。")
    parser.add_argument("username", help="ログインに使うユーザー名")
    parser.add_argument("--display-name", help="画面に表示する名前(省略時はユーザー名)")
    args = parser.parse_args()

    password = getpass("パスワード: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"パスワードは {MIN_PASSWORD_LENGTH} 文字以上にしてください。", file=sys.stderr)
        return 1
    if getpass("パスワード（確認）: ") != password:
        print("パスワードが一致しません。", file=sys.stderr)
        return 1

    try:
        register_reviewer(args.username, password, args.display_name)
    except sqlite3.IntegrityError:
        print(f"ユーザー名「{args.username}」はすでに登録されています。", file=sys.stderr)
        return 1
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    print(f"レビュワー「{args.username}」を登録しました。（保存先: {REVIEW_DB_PATH}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

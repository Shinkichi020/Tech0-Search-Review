"""レビュワーのパスワードのハッシュ化と照合。

パスワードそのものは保存せず、「salt(ランダムな値)+ パスワード」を
PBKDF2-HMAC-SHA256 で何十万回もハッシュした値だけを保存する。
"""

import hashlib
import hmac
import secrets
from pathlib import Path

from features.review import db

# ハッシュの繰り返し回数。多いほど総当たり攻撃に強い(OWASP の推奨値)。
ITERATIONS = 600_000

# 存在しないユーザーでも照合と同じ時間をかけるためのダミー(応答時間からユーザーの有無を推測させない)
_DUMMY_SALT = "00" * 16


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """(ハッシュ, salt) を 16 進文字列で返す。salt を省略すると新しく作る。"""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS)
    return digest.hex(), salt


def register_reviewer(
    username: str,
    password: str,
    display_name: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    """レビュワーを登録する。同じ username があれば sqlite3.IntegrityError。"""
    username = username.strip()
    if not username or not password:
        raise ValueError("ユーザー名とパスワードは必須です。")
    password_hash, salt = hash_password(password)
    db.add_reviewer(username, display_name or None, password_hash, salt, db_path)


def verify_login(username: str, password: str, db_path: str | Path | None = None) -> dict | None:
    """照合に成功したら {"username", "display_name"} を返す。失敗したら None。"""
    reviewer = db.get_reviewer(username.strip(), db_path)
    salt = reviewer["salt"] if reviewer else _DUMMY_SALT
    candidate, _ = hash_password(password, salt)
    if reviewer and hmac.compare_digest(candidate, reviewer["password_hash"]):
        return {
            "username": reviewer["username"],
            "display_name": reviewer["display_name"] or reviewer["username"],
        }
    return None

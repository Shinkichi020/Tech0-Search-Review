"""
Google Drive API / OAuth 2.0 共通認証・操作モジュール
担当: たくちゃん (Tech0-Search-Review)
"""

import io
import os
from typing import Any, Dict, List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseDownload

# アクセス権限のスコープ（Driveの閲覧・読み取り権限）
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

# デフォルトの指定Google DriveフォルダID
DEFAULT_FOLDER_ID = "1FtwvZtg7MHxrrCj-mkRwEjhrWRTZYHva"


def get_drive_service() -> Resource:
    """Google Drive API サービスオブジェクトを取得する共通関数。

    初回呼び出し時にブラウザでOAuth認証を行い、token.json を保存・再利用します。
    おのちゃんさん・レージさん（Tech0 Review）側からも利用可能です。
    """
    creds = None

    # すでに保存された token.json があれば読み込む
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # 有効な認証情報がない場合は新規認証 flow を実行
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_PATH}' が見つかりません。ルートディレクトリに配置してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 次回以降のために token.json へ保存
        with open(TOKEN_PATH, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def list_files_in_folder(
    folder_id: str = DEFAULT_FOLDER_ID,
) -> List[Dict[str, Any]]:
    """指定されたフォルダID内のファイル一覧を取得する関数。

    Args:
        folder_id (str): Google Drive のフォルダID

    Returns:
        List[Dict[str, Any]]: ファイルのリスト [{'id': ..., 'name': ..., 'mimeType': ...}]
    """
    service = get_drive_service()

    # 指定フォルダ配下かつゴミ箱に入っていないファイルを検索するクエリ
    query = f"'{folder_id}' in parents and trashed = false"

    results = (
        service.files()
        .list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType, modifiedTime)",
        )
        .execute()
    )

    return results.get("files", [])


def download_file(file_id: str) -> bytes:
    """Google Drive 上のファイルをバイナリデータとしてダウンロードする関数。

    Args:
        file_id (str): Google Drive のファイルID

    Returns:
        bytes: ファイルのバイナリデータ
    """
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return file_stream.getvalue()
"""Google Drive API / OAuth 2.0 共通認証・操作モジュール
担当: たくちゃん (Tech0-Search-Review)
"""

import io
import os
from typing import Any, Dict, List
from google.auth.exceptions import RefreshError
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
    token.json の期限切れ・失効時（OAuth アプリが「テスト」状態だと7日で失効）は、
    token.json を破棄して自動的に再ログインを促します。
    おのちゃんさん・レージさん（Tech0 Review）側からも利用可能です。
    """
    creds = None

    # すでに保存された token.json があれば読み込む
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except ValueError:
            # token.json が壊れている・形式が古い場合は作り直す
            os.remove(TOKEN_PATH)
            creds = None

    # 期限切れならリフレッシュを試み、失敗したら token.json を捨てて再ログインへ
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # invalid_grant（期限切れ・失効・クライアントシークレット再発行など）
            os.remove(TOKEN_PATH)
            creds = None

    # 有効な認証情報がない場合は新規認証 flow を実行
    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"'{CREDENTIALS_PATH}' が見つかりません。ルートディレクトリに配置してください。"
            )
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    # 次回以降のために token.json へ保存（リフレッシュ後の新しいトークンも保存する）
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
        List[Dict[str, Any]]: ファイルのリスト [{'id': ..., 'name': ...,
        'mimeType': ...}]
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


def download_file(file_id: str, mime_type: str = None) -> bytes:
    """Google Drive 上のファイルをバイナリデータとしてダウンロードする関数。

    Google ドキュメント形式の場合はテキスト形式（text/plain）にエクスポートして取得します。

    Args:
        file_id (str): Google Drive のファイルID
        mime_type (str, optional): ファイルの MIME タイプ

    Returns:
        bytes: ファイルのバイナリ（またはテキスト）データ
    """
    service = get_drive_service()

    # Google ドキュメント（Google Docs）形式の場合
    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(
            fileId=file_id, mimeType="text/plain"
        )
    else:
        # 通常のバイナリファイル（PDF, docx, xlsx, pptx 等）
        request = service.files().get_media(fileId=file_id)

    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return file_stream.getvalue()
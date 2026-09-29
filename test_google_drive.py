"""指定Google Driveフォルダの接続テストスクリプト"""

from utils.google_drive import list_files_in_folder, DEFAULT_FOLDER_ID


def main():
    print(f"=== 指定フォルダ (ID: {DEFAULT_FOLDER_ID}) 内のファイル取得テスト ===")
    try:
        files = list_files_in_folder()

        if not files:
            print("指定されたフォルダ内にファイルが見つかりませんでした。")
            print(
                "※ フォルダの中にファイルが正しく配置されているか、アカウントの権限をご確認ください。"
            )
        else:
            print(f"取得成功！全 {len(files)} 件のファイルが見つかりました:")
            for f in files:
                print(
                    f"- {f['name']} (ID: {f['id']}, Type: {f['mimeType']})"
                )
    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()